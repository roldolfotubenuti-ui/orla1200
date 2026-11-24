"""DriveSyncCoordinator for TKS Engine 3.0.

Orchestrates the entire Google Drive ingestion pipeline:
1. Detects video files in Google Drive folders or receives batch specifications.
2. Registers jobs into QueueManager with initial DETECTED / DOWNLOAD_QUEUED status.
3. Dispatches parallel downloads via GoogleDriveDownloader (concurrency = 2) with streaming and resumption.
4. Leverages DriveCacheManager to bypass downloads when files are already intact on disk.
5. Verifies integrity (size & MD5 checksum) upon completion.
6. Promotes jobs to READY_FOR_UPLOAD with verified local file_path in SQLite.
7. Emits structured OfficeEventBridge telemetry for real-time office visualization.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.db_manager import DatabaseManager
from core.drive_cache import DriveCacheManager
from core.drive_downloader import (
    DEFAULT_CHUNK_SIZE,
    MAX_CONCURRENT_DRIVE_DOWNLOADS,
    DownloadProgress,
    DownloadStatus,
    GoogleDriveDownloader,
)
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus, QueueManager

logger = logging.getLogger("tks.drive_sync_coordinator")


@dataclass
class DriveVideoItem:
    dept_id: str
    file_id: str
    filename: str
    expected_size: int | None = None
    expected_md5: str | None = None
    remote_mtime: str | None = None
    caption: str = ""
    schedule_time: str | None = None
    account_id: str | None = None


class DriveSyncCoordinator:
    """Coordinates detection, parallel download, caching, and QueueManager readiness."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        queue_manager: QueueManager | None = None,
        cache_manager: DriveCacheManager | None = None,
        downloader: GoogleDriveDownloader | None = None,
        event_bridge: OfficeEventBridge | None = None,
        max_concurrent_downloads: int = MAX_CONCURRENT_DRIVE_DOWNLOADS,
    ) -> None:
        self._db = db_manager or DatabaseManager.get_instance()
        self._queue = queue_manager or QueueManager(self._db)
        self._cache = cache_manager or DriveCacheManager()
        self._downloader = downloader or GoogleDriveDownloader(
            cache_manager=self._cache,
            max_concurrent=max_concurrent_downloads,
        )
        self._bridge = event_bridge or OfficeEventBridge.get_instance()
        self._progress_history: dict[str, DownloadProgress] = {}

    @property
    def downloader(self) -> GoogleDriveDownloader:
        return self._downloader

    @property
    def cache(self) -> DriveCacheManager:
        return self._cache

    def _on_download_progress(self, progress: DownloadProgress) -> None:
        """Handle live download progress updates."""
        self._progress_history[progress.file_id] = progress

        # Emit to bridge for UI and Virtual Office
        event_name = "drive.download_progress"
        if progress.status in (DownloadStatus.COMPLETED, DownloadStatus.CACHED):
            event_name = "drive.download_completed"
        elif progress.status == DownloadStatus.FAILED:
            event_name = "drive.download_failed"

        self._bridge.emit(
            event_name,
            department_id=progress.dept_id,
            extra={
                "file_id": progress.file_id,
                "filename": progress.filename,
                "status": progress.status.value,
                "percent": progress.percent,
                "speed_mbps": progress.speed_mbps,
                "downloaded_bytes": progress.downloaded_bytes,
                "total_bytes": progress.total_bytes,
                "eta_seconds": progress.eta_seconds,
                "is_cached": progress.is_cached,
                "error_code": progress.error_code,
            },
        )

    async def ingest_drive_videos(
        self,
        items: list[DriveVideoItem],
        on_progress_ui: Callable[[list[DownloadProgress]], None] | None = None,
        auto_assign_accounts: bool = True,
    ) -> list[JobRecord]:
        """Process a batch of Drive videos: queue, download, verify, and promote to READY_FOR_UPLOAD.

        Guarantees:
        - Max 2 concurrent downloads.
        - Zero redundant downloads for cached assets.
        - Strict transactional QueueManager state transitions.
        """
        logger.info(f"Starting ingestion of {len(items)} Drive videos (max_concurrent={self._downloader.max_concurrent})")
        t_batch_start = time.monotonic()

        # Step 1: Detect and enqueue in QueueManager with DETECTED / DOWNLOAD_QUEUED status
        job_map: dict[str, JobRecord] = {}  # file_id -> JobRecord
        download_payloads: list[dict[str, Any]] = []

        for item in items:
            job, is_new = self._queue.enqueue_job(
                department_id=item.dept_id,
                filename=item.filename,
                drive_file_id=item.file_id,
                account_id=item.account_id,
                schedule_time=item.schedule_time,
                caption=item.caption,
                initial_status=JobStatus.DOWNLOAD_QUEUED.value,
                auto_assign=auto_assign_accounts,
            )
            job_map[item.file_id] = job

            download_payloads.append({
                "file_id": item.file_id,
                "filename": item.filename,
                "dept_id": item.dept_id,
                "expected_size": item.expected_size,
                "expected_md5": item.expected_md5,
                "remote_mtime": item.remote_mtime,
            })

            # Emit drawer open / cabinet interaction event to office bridge
            self._bridge.emit(
                "drive.file_detected",
                department_id=item.dept_id,
                account_id=job.account_id,
                job_id=job.id,
                extra={"file_id": item.file_id, "filename": item.filename},
            )

        # Step 2: Progress tracking wrapper
        def local_progress_callback(p: DownloadProgress):
            self._on_download_progress(p)
            if on_progress_ui:
                on_progress_ui(list(self._progress_history.values()))

        # Step 3: Execute parallel streaming downloads with concurrency limit = 2
        download_results = await self._downloader.download_batch(
            items=download_payloads,
            progress_callback=local_progress_callback,
        )

        # Step 4: Promote completed and verified files to READY_FOR_UPLOAD in QueueManager
        ready_jobs: list[JobRecord] = []
        for res in download_results:
            job = job_map.get(res.file_id)
            if not job:
                continue

            if res.status in (DownloadStatus.COMPLETED, DownloadStatus.CACHED) and res.local_path:
                self._queue.update_job_status(
                    job_id=job.id,
                    status=JobStatus.READY_FOR_UPLOAD.value,
                    file_path=res.local_path,
                )
                job.status = JobStatus.READY_FOR_UPLOAD.value
                job.file_path = res.local_path
                ready_jobs.append(job)
                logger.info(f"Job {job.id} marked READY_FOR_UPLOAD: {Path(res.local_path).name}")
            else:
                self._queue.update_job_status(
                    job_id=job.id,
                    status=JobStatus.DOWNLOAD_FAILED.value,
                    error_code=res.error_code or "DOWNLOAD_FAILED",
                    error_message=res.error_message or "Download could not be completed",
                )
                job.status = JobStatus.DOWNLOAD_FAILED.value
                job.error_code = res.error_code
                job.error_message = res.error_message
                logger.error(f"Job {job.id} marked DOWNLOAD_FAILED: {res.error_message}")

        t_batch_elapsed = time.monotonic() - t_batch_start
        logger.info(
            f"Ingestion batch complete in {t_batch_elapsed:.2f}s: "
            f"{len(ready_jobs)}/{len(items)} jobs READY_FOR_UPLOAD"
        )
        return ready_jobs
