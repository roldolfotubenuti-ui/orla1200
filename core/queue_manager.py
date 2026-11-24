"""QueueManager for persistent job orchestration in TKS Engine multiaccount architecture.

Handles transactional job persistence, strict idempotency checks, lifecycle state transitions,
and crash recovery on engine startup.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from core.db_manager import DatabaseManager
from core.round_robin_router import RoundRobinRouter

logger = logging.getLogger("tks.queue_manager")


class JobStatus(str, Enum):
    # Google Drive Download Lifecycle
    DETECTED = "DETECTED"
    DOWNLOAD_QUEUED = "DOWNLOAD_QUEUED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOAD_VERIFYING = "DOWNLOAD_VERIFYING"
    DOWNLOAD_COMPLETED = "DOWNLOAD_COMPLETED"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    READY_FOR_UPLOAD = "READY_FOR_UPLOAD"

    # Execution / Upload Lifecycle
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    SUBMITTING = "SUBMITTING"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"


@dataclass
class JobRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    department_id: str = ""
    account_id: str | None = None
    drive_file_id: str | None = None
    filename: str = ""
    file_path: str | None = None
    platform: str = "tiktok"
    status: str = JobStatus.RECEIVED.value
    idempotency_key: str | None = None
    schedule_time: str | None = None
    caption: str = ""
    attempt_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Any) -> JobRecord:
        d = dict(row)
        # Filter only fields matching dataclass
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)


class QueueManager:
    """Manages transactional job queue in SQLite with strict idempotency."""

    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        router: RoundRobinRouter | None = None,
    ) -> None:
        self._db = db_manager or DatabaseManager.get_instance()
        self._router = router or RoundRobinRouter(self._db)

    @staticmethod
    def compute_idempotency_key(
        drive_file_id: str | None,
        platform: str,
        account_id: str | None,
        operation: str = "publish",
    ) -> str | None:
        """Construct standard idempotency key."""
        if not drive_file_id:
            return None
        acc_part = account_id or "auto"
        return f"{drive_file_id}:{platform}:{acc_part}:{operation}"

    def enqueue_job(
        self,
        department_id: str,
        filename: str,
        drive_file_id: str | None = None,
        account_id: str | None = None,
        schedule_time: str | None = None,
        platform: str = "tiktok",
        operation: str = "publish",
        auto_assign: bool = True,
        file_path: str | None = None,
        initial_status: str | None = None,
        caption: str = "",
    ) -> tuple[JobRecord, bool]:
        """Enqueue a new job with idempotency protection.

        :return: (JobRecord, is_new: bool). If an active job exists with the same idempotency key,
                 returns existing job with is_new=False.
        """
        dept = self._db.get_department_by_id_or_name(department_id)
        if not dept:
            raise ValueError(f"Department {department_id} does not exist.")
        resolved_dept_id = dept["id"]

        # If account_id not provided and auto_assign requested, use RoundRobinRouter
        assigned_acc = account_id
        if not assigned_acc and auto_assign:
            assigned_acc = self._router.select_next_account(resolved_dept_id, platform=platform)

        idempotency_key = self.compute_idempotency_key(drive_file_id, platform, assigned_acc, operation)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._db.transaction() as conn:
            # Check for existing job with same idempotency key
            if idempotency_key:
                existing = conn.execute(
                    "SELECT * FROM jobs WHERE idempotency_key = ?;",
                    (idempotency_key,),
                ).fetchone()

                if existing:
                    existing_record = JobRecord.from_row(existing)
                    # If existing job is still active, scheduled, or published, return it
                    if existing_record.status not in (JobStatus.FAILED.value, JobStatus.DOWNLOAD_FAILED.value):
                        logger.info(
                            f"Idempotent match for key {idempotency_key} - returning existing job {existing_record.id}"
                        )
                        return existing_record, False
                    else:
                        # Existing failed job: re-use and reset its record
                        chosen_status = initial_status or (JobStatus.ASSIGNED.value if assigned_acc else JobStatus.QUEUED.value)
                        conn.execute(
                            """
                            UPDATE jobs
                            SET department_id = ?, account_id = ?, drive_file_id = ?, filename = ?,
                                file_path = ?, platform = ?, status = ?, schedule_time = ?,
                                attempt_count = 0, error_code = NULL, error_message = NULL, updated_at = ?
                            WHERE id = ?;
                            """,
                            (
                                resolved_dept_id,
                                assigned_acc,
                                drive_file_id,
                                filename,
                                file_path,
                                platform,
                                chosen_status,
                                schedule_time,
                                now,
                                existing_record.id,
                            ),
                        )
                        updated = conn.execute("SELECT * FROM jobs WHERE id = ?;", (existing_record.id,)).fetchone()
                        logger.info(f"Re-activated failed job {existing_record.id} with status {chosen_status}")
                        return JobRecord.from_row(updated), True

            # Create new job record
            job_id = str(uuid.uuid4())
            if initial_status:
                chosen_status = initial_status
            else:
                chosen_status = JobStatus.ASSIGNED.value if assigned_acc else JobStatus.QUEUED.value

            job = JobRecord(
                id=job_id,
                department_id=resolved_dept_id,
                account_id=assigned_acc,
                drive_file_id=drive_file_id,
                filename=filename,
                file_path=file_path,
                platform=platform,
                status=chosen_status,
                idempotency_key=idempotency_key,
                schedule_time=schedule_time,
                caption=caption,
                attempt_count=0,
                error_code=None,
                error_message=None,
                created_at=now,
                updated_at=now,
            )

            conn.execute(
                """
                INSERT INTO jobs (
                    id, department_id, account_id, drive_file_id, filename, file_path, platform,
                    status, idempotency_key, schedule_time, attempt_count, error_code,
                    error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    job.id,
                    job.department_id,
                    job.account_id,
                    job.drive_file_id,
                    job.filename,
                    job.file_path,
                    job.platform,
                    job.status,
                    job.idempotency_key,
                    job.schedule_time,
                    job.attempt_count,
                    job.error_code,
                    job.error_message,
                    job.created_at,
                    job.updated_at,
                ),
            )

            # Record event
            self._db.log_execution_event(
                event_type="job.created",
                job_id=job.id,
                account_id=job.account_id,
                department_id=job.department_id,
                payload=f"status={job.status};file={filename}",
            )

            logger.info(f"Enqueued new job {job.id} for department {dept['name']} (account: {assigned_acc})")
            return job, True

    def get_job(self, job_id: str) -> JobRecord | None:
        """Fetch job by ID."""
        conn = self._db.get_connection()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,)).fetchone()
        return JobRecord.from_row(row) if row else None

    def update_job_schedule(self, job_id: str, schedule_time: str) -> None:
        """Update scheduled time for a job."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE jobs SET schedule_time = ?, updated_at = ? WHERE id = ?;",
                (schedule_time, now, job_id),
            )
        logger.info(f"Updated schedule for job {job_id} to {schedule_time}")

    def get_pending_jobs(
        self,
        department_id: str | None = None,
        limit: int = 100,
    ) -> list[JobRecord]:
        """Fetch actionable pending jobs (READY_FOR_UPLOAD, ASSIGNED, or QUEUED) ordered by creation date."""
        conn = self._db.get_connection()
        query = """
            SELECT * FROM jobs
            WHERE status IN ('READY_FOR_UPLOAD', 'ASSIGNED', 'QUEUED')
        """
        params: list[Any] = []
        if department_id:
            dept = self._db.get_department_by_id_or_name(department_id)
            if dept:
                query += " AND department_id = ?"
                params.append(dept["id"])

        query += " ORDER BY created_at ASC LIMIT ?;"
        params.append(limit)

        return [JobRecord.from_row(row) for row in conn.execute(query, params).fetchall()]

    def update_job_status(
        self,
        job_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        increment_attempt: bool = False,
        account_id: str | None = None,
        file_path: str | None = None,
    ) -> bool:
        """Update job lifecycle status and record execution event."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db.transaction() as conn:
            existing = conn.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,)).fetchone()
            if not existing:
                return False

            updates = ["status = ?", "updated_at = ?"]
            params: list[Any] = [status, now]

            if error_code is not None:
                updates.append("error_code = ?")
                params.append(error_code)

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            if increment_attempt:
                updates.append("attempt_count = attempt_count + 1")

            if account_id is not None:
                updates.append("account_id = ?")
                params.append(account_id)

            if file_path is not None:
                updates.append("file_path = ?")
                params.append(file_path)

            params.append(job_id)
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?;", params)

            self._db.log_execution_event(
                event_type=f"job.status.{status.lower()}",
                job_id=job_id,
                account_id=account_id or existing["account_id"],
                department_id=existing["department_id"],
                payload=f"attempt={existing['attempt_count']};err={error_code}",
            )

        return True

    def recover_interrupted_jobs(self) -> int:
        """Recover jobs left in transient states after engine shutdown or crash.

        Rules:
        - Jobs in SUBMITTING: mark UNKNOWN (cannot retry automatically to avoid duplicate post).
        - Jobs in RUNNING, UPLOADING, PROCESSING: reset to QUEUED/ASSIGNED for safe resume.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        recovered_count = 0

        with self._db.transaction() as conn:
            # 1. SUBMITTING -> UNKNOWN
            submitting_rows = conn.execute(
                "SELECT id FROM jobs WHERE status = 'SUBMITTING';"
            ).fetchall()
            for row in submitting_rows:
                conn.execute(
                    """
                    UPDATE jobs SET status = ?, error_code = ?, error_message = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        JobStatus.UNKNOWN.value,
                        "CRASH_DURING_SUBMISSION",
                        "Post was submitted before interruption; status unconfirmed to prevent duplicates.",
                        now,
                        row["id"],
                    ),
                )
                recovered_count += 1

            # 2. RUNNING, UPLOADING, PROCESSING -> ASSIGNED (or QUEUED)
            in_flight = conn.execute(
                "SELECT id, account_id FROM jobs WHERE status IN ('RUNNING', 'UPLOADING', 'PROCESSING');"
            ).fetchall()
            for row in in_flight:
                revert_status = JobStatus.ASSIGNED.value if row["account_id"] else JobStatus.QUEUED.value
                conn.execute(
                    """
                    UPDATE jobs SET status = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (revert_status, now, row["id"]),
                )
                recovered_count += 1

        if recovered_count > 0:
            logger.info(f"Recovered {recovered_count} interrupted jobs upon startup.")
        return recovered_count

    def get_queue_stats(self) -> dict[str, Any]:
        """Aggregate statistics across all jobs and statuses."""
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status;"
        ).fetchall()
        status_counts = {row["status"]: row["count"] for row in rows}
        return {
            "total_jobs": sum(status_counts.values()),
            "status_counts": status_counts,
            "pending": (
                status_counts.get(JobStatus.QUEUED.value, 0)
                + status_counts.get(JobStatus.ASSIGNED.value, 0)
            ),
            "running": (
                status_counts.get(JobStatus.RUNNING.value, 0)
                + status_counts.get(JobStatus.UPLOADING.value, 0)
                + status_counts.get(JobStatus.PROCESSING.value, 0)
                + status_counts.get(JobStatus.SUBMITTING.value, 0)
            ),
            "completed": (
                status_counts.get(JobStatus.SCHEDULED.value, 0)
                + status_counts.get(JobStatus.PUBLISHED.value, 0)
            ),
            "failed": status_counts.get(JobStatus.FAILED.value, 0),
        }
