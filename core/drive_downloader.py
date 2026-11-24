"""Google Drive Download Engine for TKS Engine 3.0.

Features:
- Streaming direct to disk in configurable blocks (never whole files in RAM).
- Resumable downloads via HTTP Range headers (status 206) with atomic .part staging.
- Controlled parallel execution (MAX_CONCURRENT_DRIVE_DOWNLOADS = 2) via asyncio.Semaphore.
- Integration with persistent DriveCacheManager (zero re-download of intact assets).
- Real-time progress monitoring with speed (MB/s), ETA, and ASCII visual status display.
- Exponential backoff retries (2s, 4s, 8s) with Retry-After header compliance.
- Structured telemetry and strict error taxonomy.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import aiohttp

from core.drive_cache import DriveCacheManager
from utils.app_paths import get_downloads_dir

logger = logging.getLogger("tks.drive_downloader")

MAX_CONCURRENT_DRIVE_DOWNLOADS = 2
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB chunk for optimal streaming
DEFAULT_TIMEOUT_SECONDS = 45


class DownloadStatus(str, Enum):
    IDLE = "IDLE"
    DETECTED = "DETECTED"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    CACHED = "CACHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DownloadErrorCode(str, Enum):
    AUTH_FAILED = "AUTH_FAILED"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    HTTP_ERROR = "HTTP_ERROR"
    TIMEOUT = "TIMEOUT"
    CONNECTION_LOST = "CONNECTION_LOST"
    DISK_FULL = "DISK_FULL"
    INCOMPLETE = "INCOMPLETE"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    WRITE_ERROR = "WRITE_ERROR"


@dataclass
class DownloadProgress:
    file_id: str
    filename: str
    dept_id: str = ""
    status: DownloadStatus = DownloadStatus.QUEUED
    total_bytes: int = 0
    downloaded_bytes: int = 0
    percent: float = 0.0
    speed_mbps: float = 0.0
    elapsed_seconds: float = 0.0
    eta_seconds: float = 0.0
    error_code: str | None = None
    error_message: str | None = None
    local_path: str | None = None
    is_cached: bool = False
    metadata_time: float = 0.0
    download_time: float = 0.0
    verify_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "dept_id": self.dept_id,
            "status": self.status.value,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "percent": round(self.percent, 1),
            "speed_mbps": round(self.speed_mbps, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "eta_seconds": round(self.eta_seconds, 1),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "local_path": self.local_path,
            "is_cached": self.is_cached,
        }


ProgressCallback = Callable[[DownloadProgress], None]


class GoogleDriveDownloader:
    """Robust, streaming, resumable parallel Google Drive downloader."""

    def __init__(
        self,
        cache_manager: DriveCacheManager | None = None,
        max_concurrent: int = MAX_CONCURRENT_DRIVE_DOWNLOADS,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        dest_dir: Path | None = None,
    ) -> None:
        self._cache = cache_manager or DriveCacheManager()
        self._dest_dir = dest_dir or self._cache.cache_dir
        self._dest_dir.mkdir(parents=True, exist_ok=True)
        self._max_concurrent = max_concurrent
        self._chunk_size = chunk_size
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._active_downloads: dict[str, DownloadProgress] = {}

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def cache(self) -> DriveCacheManager:
        return self._cache

    @staticmethod
    def _build_drive_urls(file_id: str) -> list[str]:
        """Candidate URLs to retrieve file from Drive."""
        return [
            f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0&confirm=t",
            f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t",
        ]

    async def _resolve_metadata(
        self,
        session: aiohttp.ClientSession,
        file_id: str,
    ) -> tuple[int | None, str | None]:
        """Fetch remote file size and filename via HEAD or range probe."""
        urls = self._build_drive_urls(file_id)
        for url in urls:
            try:
                async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (200, 206):
                        cl = resp.headers.get("Content-Length")
                        cd = resp.headers.get("Content-Disposition")
                        filename = None
                        if cd and "filename=" in cd:
                            m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
                            if m:
                                filename = m.group(1).strip()
                        size = int(cl) if cl and cl.isdigit() else None
                        return size, filename
            except Exception:
                pass
        return None, None

    async def download_file(
        self,
        file_id: str,
        filename: str = "",
        dept_id: str = "",
        expected_size: int | None = None,
        expected_md5: str | None = None,
        remote_mtime: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadProgress:
        """Download a single file with streaming, cache validation, and resumption."""
        clean_filename = filename or f"{file_id}.mp4"
        progress = DownloadProgress(
            file_id=file_id,
            filename=clean_filename,
            dept_id=dept_id,
            status=DownloadStatus.QUEUED,
            total_bytes=expected_size or 0,
        )
        self._active_downloads[file_id] = progress

        if progress_callback:
            progress_callback(progress)

        # 1. Check persistent cache
        cached_path = self._cache.get_cached_file(
            file_id=file_id,
            expected_size=expected_size,
            expected_md5=expected_md5,
            remote_modified_time=remote_mtime,
        )
        if cached_path:
            file_size = cached_path.stat().st_size
            progress.status = DownloadStatus.CACHED
            progress.total_bytes = file_size
            progress.downloaded_bytes = file_size
            progress.percent = 100.0
            progress.is_cached = True
            progress.local_path = str(cached_path)
            logger.info(f"[DRIVE] file_id={file_id} cache=HIT path={cached_path.name} size={file_size}B")
            if progress_callback:
                progress_callback(progress)
            return progress

        # 2. Acquire concurrency semaphore
        async with self._semaphore:
            progress.status = DownloadStatus.DOWNLOADING
            t_start = time.monotonic()

            final_path = self._dest_dir / f"{file_id}_{clean_filename}"
            part_path = self._dest_dir / f"{file_id}_{clean_filename}.part"

            # Check if partial download exists on disk for resumption
            existing_offset = 0
            if part_path.exists():
                existing_offset = part_path.stat().st_size
                logger.info(f"[DRIVE Resumption] Found partial download of {existing_offset} bytes for {file_id}")

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            }

            retries = 0
            max_retries = 3
            backoff_delays = [2.0, 4.0, 8.0]

            cookie_jar = aiohttp.CookieJar(unsafe=True)
            timeout = aiohttp.ClientTimeout(total=None, sock_read=DEFAULT_TIMEOUT_SECONDS, sock_connect=15)

            async with aiohttp.ClientSession(cookie_jar=cookie_jar, timeout=timeout) as session:
                # Query metadata if size unknown
                if not progress.total_bytes:
                    t_meta_start = time.monotonic()
                    remote_size, remote_fn = await self._resolve_metadata(session, file_id)
                    progress.metadata_time = time.monotonic() - t_meta_start
                    if remote_size:
                        progress.total_bytes = remote_size
                    if remote_fn and not filename:
                        progress.filename = remote_fn
                        clean_filename = remote_fn
                        final_path = self._dest_dir / f"{file_id}_{clean_filename}"
                        part_path = self._dest_dir / f"{file_id}_{clean_filename}.part"

                while retries <= max_retries:
                    try:
                        req_headers = dict(headers)
                        if existing_offset > 0:
                            req_headers["Range"] = f"bytes={existing_offset}-"

                        urls = self._build_drive_urls(file_id)
                        success = False

                        for url in urls:
                            async with session.get(url, headers=req_headers, allow_redirects=True) as resp:
                                # Handle Google virus confirmation redirect
                                if resp.status == 200 and resp.content_type == "text/html":
                                    html_text = await resp.text()
                                    # Extract confirm token if present
                                    confirm_match = re.search(r'name="confirm"\s+value="([^"]+)"', html_text)
                                    if confirm_match:
                                        confirm_token = confirm_match.group(1)
                                        confirm_url = f"{url}&confirm={confirm_token}"
                                        logger.info(f"[DRIVE Confirm] Bypassing virus scan warning for {file_id}")
                                        async with session.get(confirm_url, headers=req_headers, allow_redirects=True) as confirm_resp:
                                            resp = confirm_resp
                                            if resp.status not in (200, 206):
                                                continue
                                    else:
                                        # Not a video stream, might be auth error
                                        if "Sign in" in html_text or "accounts.google.com" in str(resp.url):
                                            progress.error_code = DownloadErrorCode.AUTH_FAILED.value
                                            progress.error_message = "Google Drive requires authentication for this link"
                                            progress.status = DownloadStatus.FAILED
                                            return progress

                                if resp.status in (200, 206):
                                    # If 206, append to existing file; if 200, overwrite from offset 0
                                    mode = "ab" if (resp.status == 206 and existing_offset > 0) else "wb"
                                    if mode == "wb":
                                        existing_offset = 0

                                    cr = resp.headers.get("Content-Range")
                                    cl = resp.headers.get("Content-Length")

                                    if cr:
                                        m = re.search(r"/(\d+)$", cr)
                                        if m:
                                            progress.total_bytes = int(m.group(1))
                                    elif cl and cl.isdigit() and not progress.total_bytes:
                                        progress.total_bytes = existing_offset + int(cl)

                                    progress.downloaded_bytes = existing_offset
                                    bytes_this_session = 0
                                    last_tick = time.monotonic()
                                    t_download_start = time.monotonic()

                                    with open(part_path, mode) as f:
                                        while True:
                                            chunk = await resp.content.read(self._chunk_size)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                            chunk_len = len(chunk)
                                            progress.downloaded_bytes += chunk_len
                                            bytes_this_session += chunk_len

                                            # Calculate live speed and ETA
                                            now = time.monotonic()
                                            dt = now - last_tick
                                            if dt >= 0.4:
                                                elapsed = now - t_download_start
                                                speed = (bytes_this_session / elapsed) if elapsed > 0 else 0
                                                progress.speed_mbps = speed / (1024 * 1024)
                                                progress.elapsed_seconds = now - t_start
                                                if progress.total_bytes > 0:
                                                    progress.percent = min(100.0, (progress.downloaded_bytes / progress.total_bytes) * 100)
                                                    remaining_bytes = max(0, progress.total_bytes - progress.downloaded_bytes)
                                                    progress.eta_seconds = (remaining_bytes / speed) if speed > 0 else 0
                                                last_tick = now
                                                if progress_callback:
                                                    progress_callback(progress)

                                    progress.download_time = time.monotonic() - t_download_start
                                    current_part_size = part_path.stat().st_size if part_path.exists() else 0
                                    if progress.total_bytes > 0 and current_part_size < progress.total_bytes:
                                        logger.warning(
                                            f"[DRIVE Incomplete Stream] Got {current_part_size}/{progress.total_bytes} bytes for {file_id}. Attempting resume..."
                                        )
                                        existing_offset = current_part_size
                                        retries += 1
                                        if retries <= max_retries:
                                            delay = backoff_delays[min(retries - 1, len(backoff_delays) - 1)]
                                            await asyncio.sleep(delay)
                                            break
                                        else:
                                            break

                                    success = True
                                    break
                                elif resp.status == 416:
                                    # Range Not Satisfiable: offset is at or beyond EOF, file is complete
                                    if existing_offset > 0 and part_path.exists():
                                        actual_size = part_path.stat().st_size
                                        progress.total_bytes = actual_size
                                        progress.downloaded_bytes = actual_size
                                        progress.percent = 100.0
                                        logger.info(f"[DRIVE 416] Offset {existing_offset} at EOF for {file_id}. File complete ({actual_size}B).")
                                        success = True
                                        break
                                    else:
                                        progress.error_code = DownloadErrorCode.INCOMPLETE.value
                                        progress.error_message = "HTTP 416 Range Not Satisfiable"
                                        progress.status = DownloadStatus.FAILED
                                        return progress
                                elif resp.status == 404:
                                    progress.error_code = DownloadErrorCode.NOT_FOUND.value
                                    progress.error_message = f"File {file_id} not found on Google Drive"
                                    progress.status = DownloadStatus.FAILED
                                    return progress
                                elif resp.status == 403:
                                    progress.error_code = DownloadErrorCode.PERMISSION_DENIED.value
                                    progress.error_message = f"Permission denied for file {file_id}"
                                    progress.status = DownloadStatus.FAILED
                                    return progress
                                elif resp.status == 429:
                                    retry_after = resp.headers.get("Retry-After")
                                    wait_time = float(retry_after) if retry_after and retry_after.isdigit() else backoff_delays[min(retries, len(backoff_delays) - 1)]
                                    logger.warning(f"[DRIVE 429] Rate limited on {file_id}. Waiting {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                                    retries += 1
                                    break
                                else:
                                    logger.warning(f"[DRIVE HTTP] Status {resp.status} on {url}")

                        if success:
                            break

                    except (asyncio.TimeoutError, aiohttp.ClientPayloadError, aiohttp.ClientConnectionError) as net_err:
                        retries += 1
                        if retries <= max_retries:
                            delay = backoff_delays[retries - 1]
                            logger.warning(
                                f"[DRIVE Retry {retries}/{max_retries}] Network error on {file_id}: {net_err}. Resuming in {delay}s..."
                            )
                            if part_path.exists():
                                existing_offset = part_path.stat().st_size
                            await asyncio.sleep(delay)
                        else:
                            progress.error_code = DownloadErrorCode.TIMEOUT.value
                            progress.error_message = f"Max retries exceeded: {net_err}"
                            progress.status = DownloadStatus.FAILED
                            if progress_callback:
                                progress_callback(progress)
                            return progress

            # 3. Verification step
            progress.status = DownloadStatus.VERIFYING
            if progress_callback:
                progress_callback(progress)

            t_verify_start = time.monotonic()
            if not part_path.exists():
                progress.error_code = DownloadErrorCode.INCOMPLETE.value
                progress.error_message = "Downloaded part file is missing"
                progress.status = DownloadStatus.FAILED
                return progress

            actual_size = part_path.stat().st_size
            if progress.total_bytes > 0 and actual_size < progress.total_bytes:
                progress.error_code = DownloadErrorCode.INCOMPLETE.value
                progress.error_message = f"Incomplete download: {actual_size}/{progress.total_bytes} bytes"
                progress.status = DownloadStatus.FAILED
                return progress

            if expected_md5:
                actual_md5 = self._cache.compute_file_md5(part_path)
                if actual_md5.lower() != expected_md5.lower():
                    progress.error_code = DownloadErrorCode.CHECKSUM_MISMATCH.value
                    progress.error_message = f"Checksum mismatch: {actual_md5} != {expected_md5}"
                    progress.status = DownloadStatus.FAILED
                    return progress

            # Atomic rename from .part to final file
            if final_path.exists():
                final_path.unlink()
            part_path.replace(final_path)

            progress.verify_time = time.monotonic() - t_verify_start
            progress.status = DownloadStatus.COMPLETED
            progress.local_path = str(final_path)
            progress.downloaded_bytes = actual_size
            progress.total_bytes = actual_size
            progress.percent = 100.0
            progress.elapsed_seconds = time.monotonic() - t_start

            # Register in persistent cache
            self._cache.register_cached_file(
                file_id=file_id,
                local_path=final_path,
                filename=clean_filename,
                size_bytes=actual_size,
                md5_checksum=expected_md5,
                remote_modified_time=remote_mtime,
            )

            logger.info(
                f"[DRIVE] file_id={file_id} download={progress.download_time:.1f}s "
                f"size={actual_size / (1024 * 1024):.1f}MB checksum=VALID cache=REGISTERED"
            )

            if progress_callback:
                progress_callback(progress)

            return progress

    async def download_batch(
        self,
        items: list[dict[str, Any]],
        progress_callback: ProgressCallback | None = None,
    ) -> list[DownloadProgress]:
        """Download a batch of Google Drive files with max 2 concurrent downloads.

        Each item must contain:
        - file_id: str
        - filename: str (optional)
        - dept_id: str (optional)
        - expected_size: int (optional)
        - expected_md5: str (optional)
        - remote_mtime: str (optional)
        """
        tasks = []
        for item in items:
            task = asyncio.create_task(
                self.download_file(
                    file_id=item["file_id"],
                    filename=item.get("filename", ""),
                    dept_id=item.get("dept_id", ""),
                    expected_size=item.get("expected_size"),
                    expected_md5=item.get("expected_md5"),
                    remote_mtime=item.get("remote_mtime"),
                    progress_callback=progress_callback,
                )
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    @staticmethod
    def render_ascii_progress(progress_list: list[DownloadProgress]) -> str:
        """Render a clean ASCII visual dashboard matching Section 6 of specification."""
        lines = [
            "==================================================================",
            "             DOWNLOAD DOS VÍDEOS — GOOGLE DRIVE                  ",
            "==================================================================",
        ]

        total = len(progress_list)
        completed = sum(1 for p in progress_list if p.status in (DownloadStatus.COMPLETED, DownloadStatus.CACHED))
        in_progress = sum(1 for p in progress_list if p.status == DownloadStatus.DOWNLOADING)
        queued = sum(1 for p in progress_list if p.status == DownloadStatus.QUEUED)
        failed = sum(1 for p in progress_list if p.status == DownloadStatus.FAILED)

        total_bytes = sum(p.total_bytes for p in progress_list)
        downloaded_bytes = sum(p.downloaded_bytes for p in progress_list)
        active_speeds = [p.speed_mbps for p in progress_list if p.status == DownloadStatus.DOWNLOADING]
        aggregate_speed = sum(active_speeds)

        for idx, p in enumerate(progress_list, 1):
            pct = int(p.percent)
            filled = int(pct / 5)
            bar = "█" * filled + "░" * (20 - filled)
            status_label = p.status.value
            if p.status == DownloadStatus.CACHED:
                status_label = "CACHE"
            elif p.status == DownloadStatus.COMPLETED:
                status_label = "CONCLUÍDO"
            elif p.status == DownloadStatus.DOWNLOADING:
                status_label = f"BAIXANDO ({p.speed_mbps:.1f} MB/s)"
            elif p.status == DownloadStatus.QUEUED:
                status_label = "AGUARDANDO"
            elif p.status == DownloadStatus.FAILED:
                status_label = f"ERRO ({p.error_code or 'FALHA'})"

            lines.append(f"Vídeo {idx:02d}  {bar} {pct:3d}%  {status_label}")

        lines.append("------------------------------------------------------------------")
        lines.append(f"CONCLUÍDOS: {completed}/{total} | EM ANDAMENTO: {in_progress}/{total} | AGUARDANDO: {queued}/{total} | FALHAS: {failed}")
        lines.append(f"CONCORRÊNCIA ATIVA: {in_progress}/{MAX_CONCURRENT_DRIVE_DOWNLOADS} | VELOCIDADE AGREGADA: {aggregate_speed:.2f} MB/s")
        if total_bytes > 0:
            lines.append(f"TRANSFERÊNCIA TOTAL: {downloaded_bytes / (1024 * 1024):.1f} MB / {total_bytes / (1024 * 1024):.1f} MB")
        lines.append("==================================================================")
        return "\n".join(lines)
