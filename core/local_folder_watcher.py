"""LocalFolderWatcher service for TKS Engine 3.0 / Virtual Office.

Monitors local intake directories (E:\\ORLA1200\\1 through 6) continuously,
detects complete video files (verifying size stability), computes hashes,
registers jobs in SQLite, emits sanitized events to OfficeEventBridge for
physical 3D drawer animations, and manages atomic archival to _PROCESSADOS.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from core.account_manager import AccountManager
from core.daily_scheduler_rule import (
    DEFAULT_CAPTION,
    DEFAULT_SCHEDULE_TIME,
    DEFAULT_SCHEDULE_TIMEZONE,
    calculate_next_daily_slot,
)
from core.db_manager import DatabaseManager
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus, QueueManager

logger = logging.getLogger("tks.folder_watcher")

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".flv"}

# Exact folder mapping as mandated:
# Folder 1 -> Dept 01 (Instagram) -> employee-01 -> drawer-01 -> Account 01
# Folder 2 -> Dept 02 (Mercado Livre) -> employee-02 -> drawer-02 -> Account 02
# Folder 3 -> Dept 03 (Shorts) -> employee-03 -> drawer-03 -> Account 03
# Folder 4 -> Dept 04 (TikTok) -> employee-04 -> drawer-04 -> Account 04
# Folder 5 -> Dept 05 (TikTok Shop) -> employee-05 -> drawer-05 -> Account 05
# Folder 6 -> Dept 06 (YouTube) -> employee-06 -> drawer-06 -> Account 06

FOLDER_DEPT_MAPPING: dict[int, dict[str, Any]] = {
    1: {
        "folder_index": 1,
        "department_id": "dept_instagram",
        "department_name": "Instagram",
        "employee_id": "employee-01",
        "drawer_id": "drawer-01",
        "account_id": "10d617eb-e1a7-4ed7-b8b3-acda804f3f98",
        "account_username": "unamyti",
    },
    2: {
        "folder_index": 2,
        "department_id": "dept_mercadolivre",
        "department_name": "Mercado Livre",
        "employee_id": "employee-02",
        "drawer_id": "drawer-02",
        "account_id": "37bc39cd-077f-4920-95d1-b11746f0399f",
        "account_username": "valueini",
    },
    3: {
        "folder_index": 3,
        "department_id": "dept_shorts",
        "department_name": "Shorts",
        "employee_id": "employee-03",
        "drawer_id": "drawer-03",
        "account_id": "669df47e-4abf-4efd-a870-934295fa7a58",
        "account_username": "vinihack537",
    },
    4: {
        "folder_index": 4,
        "department_id": "dept_tiktok",
        "department_name": "TikTok",
        "employee_id": "employee-04",
        "drawer_id": "drawer-04",
        "account_id": "a874cfb3-700c-4b6f-aa3c-ba1e2856894e",
        "account_username": "vinihack979",
    },
    5: {
        "folder_index": 5,
        "department_id": "dept_tiktokshop",
        "department_name": "TikTok Shop",
        "employee_id": "employee-05",
        "drawer_id": "drawer-05",
        "account_id": "e7e6bd57-59de-4272-82b8-f20ce2487e83",
        "account_username": "vinihack120",
    },
    6: {
        "folder_index": 6,
        "department_id": "dept_youtube",
        "department_name": "YouTube",
        "employee_id": "employee-06",
        "drawer_id": "drawer-06",
        "account_id": "4baf0564-985f-4273-b559-9787cdd86c0d",
        "account_username": "viniciusferraz218",
    },
}


def compute_file_sha256(filepath: Path) -> str:
    """Calculate SHA-256 hash using streaming chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


class FolderChangeHandler(FileSystemEventHandler):
    """Watchdog event handler for intake directories."""

    def __init__(self, watcher: LocalFolderWatcher) -> None:
        super().__init__()
        self.watcher = watcher

    def on_created(self, event: Any) -> None:
        if not event.is_directory:
            self.watcher.on_file_detected(Path(event.src_path))

    def on_modified(self, event: Any) -> None:
        if not event.is_directory:
            self.watcher.on_file_detected(Path(event.src_path))


class LocalFolderWatcher:
    """Monitors E:\\ORLA1200 subdirectories and triggers Virtual Office drawers & pipeline."""

    def __init__(
        self,
        base_dir: Path | str = Path(r"E:\ORLA1200"),
        db_manager: DatabaseManager | None = None,
        queue_manager: QueueManager | None = None,
        bridge: OfficeEventBridge | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.processed_dir = self.base_dir / "_PROCESSADOS"
        self._db = db_manager or DatabaseManager.get_instance()
        self._queue = queue_manager or QueueManager(self._db)
        self._bridge = bridge or OfficeEventBridge.get_instance()

        self._observer: Observer | None = None
        self._is_running: bool = False
        self._detected_hashes: set[str] = set()
        self._processing_files: set[str] = set()
        self._lock = threading.Lock()

        self._ensure_directories()
        self._load_existing_hashes()

    def _ensure_directories(self) -> None:
        """Create E:\\ORLA1200\\1..6 and _PROCESSADOS\\1..6 if needed."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 7):
            (self.base_dir / str(i)).mkdir(parents=True, exist_ok=True)
            (self.processed_dir / str(i)).mkdir(parents=True, exist_ok=True)

    def _load_existing_hashes(self) -> None:
        """Cache known hashes from SQLite to prevent duplicate jobs."""
        try:
            with self._db.get_connection() as conn:
                cursor = conn.execute("SELECT sha256 FROM jobs WHERE sha256 IS NOT NULL")
                for row in cursor.fetchall():
                    if row["sha256"]:
                        self._detected_hashes.add(row["sha256"])
        except Exception as exc:
            logger.warning(f"Could not preload known hashes: {exc}")

    def get_folder_mapping(self, folder_idx: int) -> dict[str, Any] | None:
        return FOLDER_DEPT_MAPPING.get(folder_idx)

    def identify_folder_index(self, path: Path) -> int | None:
        """Identify which department folder (1 to 6) a file belongs to."""
        try:
            rel = path.resolve().relative_to(self.base_dir.resolve())
            parts = rel.parts
            if parts and parts[0] in {"1", "2", "3", "4", "5", "6"}:
                return int(parts[0])
        except ValueError:
            pass
        return None

    def start(self) -> None:
        """Start watchdog filesystem observer."""
        if self._is_running:
            return

        self._observer = Observer()
        handler = FolderChangeHandler(self)

        for i in range(1, 7):
            fpath = self.base_dir / str(i)
            if fpath.exists():
                self._observer.schedule(handler, str(fpath), recursive=False)

        self._observer.start()
        self._is_running = True
        logger.info(f"LocalFolderWatcher started on {self.base_dir} (Folders 1..6)")

        # Initial scan of existing files in folders 1..6
        try:
            threading.Thread(target=self.scan_all_folders, daemon=True, name="InitialFolderScan").start()
        except Exception as exc:
            logger.warning(f"Could not start initial folder scan thread: {exc}")

    def stop(self) -> None:
        """Stop filesystem observer."""
        if not self._is_running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3.0)
            self._observer = None
        self._is_running = False
        logger.info("LocalFolderWatcher stopped.")

    def is_file_copy_complete(self, path: Path, checks: int = 3, interval: float = 0.5) -> bool:
        """Ensure file is completely written and not being copied currently."""
        if not path.exists():
            return False

        last_size = -1
        for _ in range(checks):
            try:
                current_size = path.stat().st_size
                if current_size == 0:
                    return False
                if last_size != -1 and current_size != last_size:
                    return False
                last_size = current_size

                # Try opening exclusively to verify no write lock remains
                with open(path, "rb"):
                    pass
                time.sleep(interval)
            except (OSError, PermissionError):
                return False
        return True

    def scan_all_folders(self) -> list[dict[str, Any]]:
        """Synchronously scan folders 1..6 and process all valid files."""
        results: list[dict[str, Any]] = []
        for i in range(1, 7):
            fpath = self.base_dir / str(i)
            if not fpath.exists():
                continue
            for item in fpath.iterdir():
                if item.is_file() and item.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                    res = self.process_intake_file(item)
                    if res:
                        results.append(res)
        return results

    def on_file_detected(self, path: Path) -> None:
        """Callback from watchdog handler."""
        if path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            return
        # Avoid processing same file in concurrent threads
        p_str = str(path.resolve())
        if p_str in self._processing_files:
            return
        self._processing_files.add(p_str)
        try:
            self.process_intake_file(path)
        finally:
            self._processing_files.discard(p_str)

    def process_intake_file(self, path: Path) -> dict[str, Any] | None:
        """Validate, register job, and emit Virtual Office physical drawer event."""
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            return None

        folder_idx = self.identify_folder_index(path)
        if not folder_idx:
            return None

        mapping = self.get_folder_mapping(folder_idx)
        if not mapping:
            return None

        # Verify stability
        if not self.is_file_copy_complete(path):
            logger.info(f"File {path.name} is still being written or inaccessible. Skipping for now.")
            return None

        file_size = path.stat().st_size
        sha256 = compute_file_sha256(path)

        # Check if already processed or queued FOR THIS SPECIFIC DEPARTMENT & ACCOUNT
        existing_job = None
        try:
            with self._db.get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM jobs 
                       WHERE department_id = ? 
                         AND (account_id = ? OR account_id IS NULL) 
                         AND (sha256 = ? OR filename = ?)
                       ORDER BY created_at DESC LIMIT 1""",
                    (mapping["department_id"], mapping["account_id"], sha256, path.name),
                )
                existing_job = cursor.fetchone()
        except Exception as exc:
            logger.error(f"Error checking job by sha256 for department {mapping['department_id']}: {exc}")

        # Calculate next available consecutive daily slot at 18:00 (America/Sao_Paulo)
        _, scheduled_slot_str = calculate_next_daily_slot(
            account_id=mapping["account_id"],
            db=self._db,
            target_time=DEFAULT_SCHEDULE_TIME,
            tz_name=DEFAULT_SCHEDULE_TIMEZONE,
        )
        caption = DEFAULT_CAPTION

        job_id = None
        if existing_job:
            job_id = existing_job["id"]
            cur_status = str(existing_job["status"]).upper()
            if cur_status not in ("RUNNING", "UPLOADING", "PROCESSING", "SUBMITTING"):
                logger.info(f"File {path.name} in folder {folder_idx} (prev status={cur_status}). Resetting to READY_FOR_UPLOAD for account {mapping['account_username']} at {scheduled_slot_str}")
                with self._db.get_connection() as conn:
                    conn.execute(
                        """UPDATE jobs 
                           SET status = ?, 
                               schedule_time = ?, 
                               file_path = ?, 
                               attempt_count = 0, 
                               error_message = NULL, 
                               updated_at = datetime('now') 
                           WHERE id = ?""",
                        (JobStatus.READY_FOR_UPLOAD.value, scheduled_slot_str, str(path.resolve()), job_id),
                    )
            logger.info(f"File {path.name} registered as job {job_id} for {mapping['account_username']} (status={cur_status} -> READY_FOR_UPLOAD)")
        else:
            # Register new job in SQLite via QueueManager for this specific department and account
            job, is_new = self._queue.enqueue_job(
                department_id=mapping["department_id"],
                filename=path.name,
                account_id=mapping["account_id"],
                schedule_time=scheduled_slot_str,
                file_path=str(path.resolve()),
                initial_status=JobStatus.READY_FOR_UPLOAD.value,
                caption=caption,
            )
            job_id = job.id
            try:
                with self._db.get_connection() as conn:
                    conn.execute("UPDATE jobs SET sha256 = ?, size_bytes = ?, file_path = ? WHERE id = ?", (sha256, file_size, str(path.resolve()), job_id))
            except Exception:
                pass

            self._detected_hashes.add(sha256)
            logger.info(f"Registered new job {job_id} for {path.name} in department {mapping['department_name']} ({mapping['account_username']}) at {scheduled_slot_str} (is_new={is_new})")

        # Emit 3D Virtual Office operational events:
        # 1. video.detected
        self._bridge.emit(
            event_name="video.detected",
            department_id=mapping["department_id"],
            account_id=mapping["account_id"],
            username=mapping["account_username"],
            job_id=job_id,
            status="DETECTED",
            extra={
                "folder_index": folder_idx,
                "drawer_id": mapping["drawer_id"],
                "employee_id": mapping["employee_id"],
                "filename": path.name,
                "file_path": str(path.resolve()),
                "size_bytes": file_size,
                "sha256": sha256,
                "caption": caption,
                "schedule_time": scheduled_slot_str,
            },
        )

        # 2. drawer.opened
        self._bridge.emit(
            event_name="drawer.opened",
            department_id=mapping["department_id"],
            account_id=mapping["account_id"],
            username=mapping["account_username"],
            job_id=job_id,
            status="DRAWER_OPENED",
            extra={
                "drawer_id": mapping["drawer_id"],
                "employee_id": mapping["employee_id"],
                "filename": path.name,
            },
        )

        return {
            "job_id": job_id,
            "folder_index": folder_idx,
            "department": mapping["department_name"],
            "department_id": mapping["department_id"],
            "employee_id": mapping["employee_id"],
            "drawer_id": mapping["drawer_id"],
            "account_id": mapping["account_id"],
            "account_username": mapping["account_username"],
            "filename": path.name,
            "file_path": str(path.resolve()),
            "size_bytes": file_size,
            "sha256": sha256,
        }

    def archive_processed_video(self, job_id: str) -> bool:
        """Atomic archival of video to E:\\ORLA1200\\_PROCESSADOS\\{folder_idx}\\.
        
        Mandatory safety rule: ONLY move if status is SCHEDULED (TikTok Studio confirmed).
        Never move on FAILED, UNKNOWN, or REAUTH_REQUIRED.
        """
        job = self._queue.get_job(job_id)
        if not job:
            logger.error(f"Cannot archive job {job_id}: job not found.")
            return False

        if job.status != JobStatus.SCHEDULED:
            logger.warning(
                f"Cannot archive file for job {job_id}: status is {job.status.value}, "
                f"only SCHEDULED jobs are eligible for archival."
            )
            return False

        src_path = Path(job.file_path)
        if not src_path.exists():
            logger.warning(f"Source file {src_path} no longer exists. Skipping move.")
            return False

        folder_idx = self.identify_folder_index(src_path)
        if not folder_idx:
            # Fallback by department
            for f_idx, m in FOLDER_DEPT_MAPPING.items():
                if m["department_id"] == job.department_id:
                    folder_idx = f_idx
                    break

        folder_idx = folder_idx or 1
        target_dir = self.processed_dir / str(folder_idx)
        target_dir.mkdir(parents=True, exist_ok=True)
        dest_path = target_dir / src_path.name

        try:
            # Handle collision if a file with same name already exists in _PROCESSADOS
            if dest_path.exists():
                stem = src_path.stem
                ext = src_path.suffix
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = target_dir / f"{stem}_{ts}{ext}"

            # Atomic move
            shutil.move(str(src_path), str(dest_path))
            logger.info(f"Archived confirmed video: {src_path} -> {dest_path}")

            # Update job record in SQLite
            with self._db.get_connection() as conn:
                conn.execute(
                    "UPDATE jobs SET file_path = ?, status = 'ARCHIVED', updated_at = ? WHERE id = ?",
                    (str(dest_path), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), job_id),
                )

            # Emit video.archived
            self._bridge.emit(
                event_name="video.archived",
                department_id=job.department_id,
                account_id=job.account_id,
                job_id=job_id,
                status="ARCHIVED",
                extra={
                    "original_path": str(src_path),
                    "archived_path": str(dest_path),
                    "filename": dest_path.name,
                },
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to archive file for job {job_id}: {exc}", exc_info=True)
            return False

    def get_summary(self) -> dict[str, Any]:
        """Summary of intake folders and processed videos for Central de Operações."""
        folders_summary: list[dict[str, Any]] = []
        total_pending = 0
        total_processed = 0

        for i in range(1, 7):
            m = FOLDER_DEPT_MAPPING[i]
            in_dir = self.base_dir / str(i)
            proc_dir = self.processed_dir / str(i)

            pending_files: list[dict[str, Any]] = []
            if in_dir.exists():
                for f in in_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                        pending_files.append({
                            "name": f.name,
                            "size_bytes": f.stat().st_size,
                            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        })

            processed_files: list[dict[str, Any]] = []
            if proc_dir.exists():
                for f in proc_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS:
                        processed_files.append({
                            "name": f.name,
                            "size_bytes": f.stat().st_size,
                            "archived_at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        })

            total_pending += len(pending_files)
            total_processed += len(processed_files)

            folders_summary.append({
                "folder_index": i,
                "folder_path": str(in_dir),
                "processed_path": str(proc_dir),
                "department_id": m["department_id"],
                "department_name": m["department_name"],
                "employee_id": m["employee_id"],
                "drawer_id": m["drawer_id"],
                "account_id": m["account_id"],
                "account_username": m["account_username"],
                "pending_count": len(pending_files),
                "processed_count": len(processed_files),
                "pending_files": pending_files,
                "processed_files": processed_files,
            })

        return {
            "base_dir": str(self.base_dir),
            "processed_dir": str(self.processed_dir),
            "is_watching": self._is_running,
            "total_pending": total_pending,
            "total_processed": total_processed,
            "folders": folders_summary,
        }
