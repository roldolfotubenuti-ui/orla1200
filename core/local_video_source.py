"""LocalVideoSource service for TKS Engine 3.0.

Discovers, validates, and hashes local video files stored directly on disk (e.g. E:\ORLA1200\),
bypassing Google Drive downloads and preparing jobs for multiaccount TikTok Studio scheduling.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.account_manager import AccountManager
from core.db_manager import DatabaseManager
from core.queue_manager import JobRecord, JobStatus, QueueManager

logger = logging.getLogger("tks.local_video_source")

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".flv"}

# Department & Drawer mapping
FOLDER_MAPPING = {
    1: {
        "department_id": "dept_instagram",
        "department_name": "Instagram",
        "employee_id": "01",
        "drawer_id": "drawer-01",
        "account_id": "10d617eb-e1a7-4ed7-b8b3-acda804f3f98",
        "account_username": "unamyti",
        "display_title": "Conta 01 — Instagram",
    },
    2: {
        "department_id": "dept_mercadolivre",
        "department_name": "Mercado Livre",
        "employee_id": "02",
        "drawer_id": "drawer-02",
        "account_id": "37bc39cd-077f-4920-95d1-b11746f0399f",
        "account_username": "valueini",
        "display_title": "Conta 02 — Mercado Livre",
    },
    3: {
        "department_id": "dept_shorts",
        "department_name": "Shorts",
        "employee_id": "03",
        "drawer_id": "drawer-03",
        "account_id": "669df47e-4abf-4efd-a870-934295fa7a58",
        "account_username": "vinihack537",
        "display_title": "Conta 03 — Shorts",
    },
    4: {
        "department_id": "dept_tiktok",
        "department_name": "TikTok",
        "employee_id": "04",
        "drawer_id": "drawer-04",
        "account_id": "a874cfb3-700c-4b6f-aa3c-ba1e2856894e",
        "account_username": "vinihack979",
        "display_title": "Conta 04 — TikTok",
    },
    5: {
        "department_id": "dept_tiktokshop",
        "department_name": "TikTok Shop",
        "employee_id": "05",
        "drawer_id": "drawer-05",
        "account_id": "e7e6bd57-59de-4272-82b8-f20ce2487e83",
        "account_username": "vinihack120",
        "display_title": "Conta 05 — TikTok Shop",
    },
    6: {
        "department_id": "dept_youtube",
        "department_name": "YouTube",
        "employee_id": "06",
        "drawer_id": "drawer-06",
        "account_id": "4baf0564-985f-4273-b559-9787cdd86c0d",
        "account_username": "viniciusferraz218",
        "display_title": "Conta 06 — YouTube",
    },
}


@dataclass
class LocalVideoMetadata:
    filename: str
    extension: str
    absolute_path: str
    size_bytes: int
    size_mb: float
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    codec: str | None = None
    readable: bool = True
    sha256: str = ""
    integrity_ok: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LocalVideoFolder:
    folder_number: int
    folder_path: str
    department_id: str
    department_name: str
    employee_id: str
    drawer_id: str
    account_id: str
    account_username: str
    display_title: str
    is_valid: bool = False
    validation_error: str | None = None
    video: LocalVideoMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalVideoSource:
    """Discovers, validates, and inspects video files from local folders."""

    def __init__(self, base_path: str = r"E:\ORLA1200") -> None:
        self.base_path = Path(base_path)

    @staticmethod
    def extract_media_info(path: str | Path) -> dict[str, Any]:
        """Probe media metadata using ffprobe."""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=codec_name,width,height",
            "-of",
            "json",
            str(path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
            data = json.loads(res.stdout)
            duration_str = data.get("format", {}).get("duration")
            duration = float(duration_str) if duration_str else None
            streams = data.get("streams", [])
            video_stream = next((s for s in streams if "width" in s), {})
            return {
                "duration": duration,
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "codec": video_stream.get("codec_name"),
            }
        except Exception as exc:
            logger.warning(f"ffprobe probe failed for {path}: {exc}")
            return {"duration": None, "width": None, "height": None, "codec": None, "error": str(exc)}

    @staticmethod
    def compute_sha256(path: str | Path) -> str:
        """Compute SHA-256 hash in 1MB chunks."""
        h = hashlib.sha256()
        with open(path, "rb") as fp:
            while chunk := fp.read(1024 * 1024):
                h.update(chunk)
        return h.hexdigest()

    def scan_folder(self, folder_num: int) -> LocalVideoFolder:
        """Scan a single folder (1..6) and validate its contents."""
        folder_info = FOLDER_MAPPING.get(folder_num)
        if not folder_info:
            return LocalVideoFolder(
                folder_number=folder_num,
                folder_path="",
                department_id="",
                department_name="",
                employee_id="",
                drawer_id="",
                account_id="",
                account_username="",
                display_title="",
                is_valid=False,
                validation_error=f"Pasta {folder_num} não mapeada.",
            )

        target_dir = self.base_path / str(folder_num)

        result = LocalVideoFolder(
            folder_number=folder_num,
            folder_path=str(target_dir),
            department_id=folder_info["department_id"],
            department_name=folder_info["department_name"],
            employee_id=folder_info["employee_id"],
            drawer_id=folder_info["drawer_id"],
            account_id=folder_info["account_id"],
            account_username=folder_info["account_username"],
            display_title=folder_info["display_title"],
        )

        if not target_dir.exists() or not target_dir.is_dir():
            result.is_valid = False
            result.validation_error = f"Diretório não encontrado: {target_dir}"
            return result

        # List video files
        all_entries = os.listdir(target_dir)
        video_files = [
            f for f in all_entries
            if (target_dir / f).is_file() and (target_dir / f).suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
        ]

        if len(video_files) == 0:
            result.is_valid = False
            result.validation_error = f"Nenhum arquivo de vídeo encontrado em {target_dir}."
            return result

        if len(video_files) > 1:
            result.is_valid = False
            result.validation_error = (
                f"Mais de um vídeo encontrado em {target_dir} ({len(video_files)} arquivos). "
                f"Para este teste, deve haver exatamente 1 vídeo por pasta."
            )
            return result

        file_name = video_files[0]
        full_path = target_dir / file_name
        abs_path = str(full_path.resolve())

        # Check readability
        readable = os.access(abs_path, os.R_OK)
        size_bytes = full_path.stat().st_size
        size_mb = round(size_bytes / (1024 * 1024), 2)

        if size_bytes == 0:
            result.is_valid = False
            result.validation_error = f"Arquivo vazio (0 bytes): {file_name}"
            return result

        if not readable:
            result.is_valid = False
            result.validation_error = f"Arquivo sem permissão de leitura: {file_name}"
            return result

        # Probe ffprobe and SHA256
        sha256_hash = self.compute_sha256(abs_path)
        media_info = self.extract_media_info(abs_path)

        metadata = LocalVideoMetadata(
            filename=file_name,
            extension=full_path.suffix.lower(),
            absolute_path=abs_path,
            size_bytes=size_bytes,
            size_mb=size_mb,
            duration_seconds=media_info.get("duration"),
            width=media_info.get("width"),
            height=media_info.get("height"),
            codec=media_info.get("codec"),
            readable=readable,
            sha256=sha256_hash,
            integrity_ok=True,
        )

        result.is_valid = True
        result.video = metadata
        return result

    def scan_all(self) -> list[LocalVideoFolder]:
        """Scan all 6 folders and return validation list."""
        return [self.scan_folder(i) for i in range(1, 7)]

    def reconcile_and_prepare_jobs(
        self,
        db_manager: DatabaseManager,
        queue_manager: QueueManager,
        folders: list[LocalVideoFolder],
        schedule_time: str = "2026-11-23 17:00:00",
        caption: str = "bizarro",
    ) -> list[JobRecord]:
        """Reconcile scanned local videos with SQLite jobs.
        
        Reuses existing matching jobs if file/department matches, or supersedes previous jobs
        and creates new dedicated local jobs.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prepared_jobs: list[JobRecord] = []

        with db_manager.transaction() as conn:
            # First, inspect existing jobs
            existing_jobs = [
                dict(r) for r in conn.execute("SELECT * FROM jobs;").fetchall()
            ]

            for folder in folders:
                if not folder.is_valid or not folder.video:
                    continue

                v = folder.video
                dept_id = folder.department_id
                acc_id = folder.account_id

                # Check if there is an existing job for this department
                dept_jobs = [j for j in existing_jobs if j["department_id"] == dept_id]

                # Match by filename
                matching_job = next((j for j in dept_jobs if j["filename"] == v.filename), None)

                if matching_job:
                    # Update existing job with exact local path and schedule details
                    job_id = matching_job["id"]
                    conn.execute(
                        """
                        UPDATE jobs
                        SET file_path = ?,
                            caption = ?,
                            schedule_time = ?,
                            status = ?,
                            error_code = NULL,
                            error_message = NULL,
                            updated_at = ?
                        WHERE id = ?;
                        """,
                        (v.absolute_path, caption, schedule_time, JobStatus.READY_FOR_UPLOAD.value, now, job_id),
                    )
                    logger.info(f"Reconciled existing job {job_id} for {dept_id} with local file {v.absolute_path}")
                    rec = queue_manager.get_job(job_id)
                    if rec:
                        prepared_jobs.append(rec)
                else:
                    # Mark any old pending/running job in this department as SUPERSEDED to avoid duplicate runs
                    for old_j in dept_jobs:
                        if old_j["status"] in (JobStatus.READY_FOR_UPLOAD.value, JobStatus.QUEUED.value, JobStatus.ASSIGNED.value):
                            conn.execute(
                                "UPDATE jobs SET status = 'SUPERSEDED', updated_at = ? WHERE id = ?;",
                                (now, old_j["id"]),
                            )
                            logger.info(f"Superseded previous job {old_j['id']} for {dept_id}")

                    # Create new local job
                    idempotency_key = f"local:{folder.folder_number}:{v.sha256[:16]}:{acc_id}:publish"
                    new_job, _ = queue_manager.enqueue_job(
                        department_id=dept_id,
                        filename=v.filename,
                        account_id=acc_id,
                        schedule_time=schedule_time,
                        platform="tiktok",
                        operation="publish",
                        auto_assign=False,
                        file_path=v.absolute_path,
                        initial_status=JobStatus.READY_FOR_UPLOAD.value,
                        caption=caption,
                    )
                    # Force exact idempotency key if needed
                    conn.execute(
                        "UPDATE jobs SET idempotency_key = ?, caption = ?, file_path = ? WHERE id = ?;",
                        (idempotency_key, caption, v.absolute_path, new_job.id),
                    )
                    rec = queue_manager.get_job(new_job.id)
                    if rec:
                        prepared_jobs.append(rec)

        return prepared_jobs
