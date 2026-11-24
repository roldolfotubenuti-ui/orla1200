"""Google Drive Cache Manager for TKS Engine 3.0.

Provides persistent disk caching in %APPDATA%/TKS_Engine/downloads/ keyed by Google Drive file_id.
Verifies file existence, size, and MD5 checksum before reporting cache hits,
ensuring zero duplicate downloads and instantaneous reutilization of valid local assets.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.app_paths import get_downloads_dir

logger = logging.getLogger("tks.drive_cache")


class DriveCacheManager:
    """Manages persistent caching and integrity checks for Google Drive videos."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or get_downloads_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._cache_dir / "cache_manifest.json"
        self._manifest: dict[str, dict[str, Any]] = self._load_manifest()

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        """Load manifest from disk or initialize empty."""
        if self._manifest_path.exists():
            try:
                with open(self._manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read cache manifest, reinitializing: {e}")
        return {}

    def _save_manifest(self) -> None:
        """Persist manifest to disk atomically."""
        temp_path = self._cache_dir / "cache_manifest.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2, ensure_ascii=False)
            temp_path.replace(self._manifest_path)
        except Exception as e:
            logger.error(f"Failed to save cache manifest: {e}")

    @staticmethod
    def compute_file_md5(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
        """Compute MD5 hash in streaming chunks to avoid loading large files into RAM."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_cached_file(
        self,
        file_id: str,
        expected_size: int | None = None,
        expected_md5: str | None = None,
        remote_modified_time: str | None = None,
    ) -> Path | None:
        """Query cache for a file. Returns Path if valid and intact, None otherwise.

        Validates:
        1. File exists on disk.
        2. Size matches expected_size if specified.
        3. MD5 matches expected_md5 if specified.
        4. remote_modified_time matches if specified.
        """
        if not file_id:
            return None

        # Check standard filename pattern: <file_id>.mp4 or in manifest
        entry = self._manifest.get(file_id)
        candidate_paths: list[Path] = []

        if entry and entry.get("local_path"):
            candidate_paths.append(Path(entry["local_path"]))

        candidate_paths.append(self._cache_dir / f"{file_id}.mp4")

        # Also search for files matching <file_id>_*.mp4
        for existing in self._cache_dir.glob(f"{file_id}*.mp4"):
            if existing not in candidate_paths:
                candidate_paths.append(existing)

        for path in candidate_paths:
            if not path.exists() or not path.is_file():
                continue

            actual_size = path.stat().st_size
            if actual_size == 0:
                continue

            # Verify size if expected_size given
            if expected_size is not None and expected_size > 0:
                if actual_size != expected_size:
                    logger.debug(
                        f"[Cache Miss] Size mismatch for {file_id}: disk={actual_size}, expected={expected_size}"
                    )
                    continue

            # Verify modified time if tracked in entry
            if entry and remote_modified_time and entry.get("remote_modified_time"):
                if entry["remote_modified_time"] != remote_modified_time:
                    logger.info(
                        f"[Cache Miss] Remote file {file_id} modified on Drive ({remote_modified_time} != {entry['remote_modified_time']})"
                    )
                    continue

            # Verify MD5 if provided
            if expected_md5:
                actual_md5 = self.compute_file_md5(path)
                if actual_md5.lower() != expected_md5.lower():
                    logger.warning(
                        f"[Cache Miss] Checksum mismatch for {file_id}: disk={actual_md5}, expected={expected_md5}"
                    )
                    continue

            # Valid cached file found
            logger.info(f"[Cache Hit] Reusing cached file for {file_id}: {path.name} ({actual_size} bytes)")
            return path

        return None

    def register_cached_file(
        self,
        file_id: str,
        local_path: Path,
        filename: str,
        size_bytes: int | None = None,
        md5_checksum: str | None = None,
        remote_modified_time: str | None = None,
    ) -> dict[str, Any]:
        """Register a successfully downloaded and verified file into the manifest."""
        local_path = Path(local_path).resolve()
        if not local_path.exists():
            raise FileNotFoundError(f"Cannot register nonexistent file in cache: {local_path}")

        actual_size = local_path.stat().st_size
        checksum = md5_checksum or self.compute_file_md5(local_path)

        entry = {
            "file_id": file_id,
            "filename": filename,
            "local_path": str(local_path),
            "size_bytes": size_bytes or actual_size,
            "md5_checksum": checksum,
            "remote_modified_time": remote_modified_time,
            "cached_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_complete": True,
        }

        self._manifest[file_id] = entry
        self._save_manifest()
        logger.info(f"[Cache Registered] {file_id} -> {local_path.name} (MD5: {checksum})")
        return entry

    def invalidate(self, file_id: str) -> bool:
        """Remove an entry from the cache manifest and disk."""
        entry = self._manifest.pop(file_id, None)
        self._save_manifest()
        if entry and entry.get("local_path"):
            p = Path(entry["local_path"])
            if p.exists():
                try:
                    p.unlink()
                    return True
                except Exception as e:
                    logger.warning(f"Could not delete invalidated cache file {p}: {e}")
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate cache statistics."""
        total_files = len(self._manifest)
        total_bytes = sum(e.get("size_bytes", 0) for e in self._manifest.values())
        return {
            "cache_dir": str(self._cache_dir),
            "total_cached_files": total_files,
            "total_cached_bytes": total_bytes,
            "total_cached_mb": round(total_bytes / (1024 * 1024), 2),
        }
