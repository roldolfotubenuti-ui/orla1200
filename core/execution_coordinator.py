"""ExecutionCoordinator for controlled parallel multiaccount processing in TKS Engine.

Enforces strict concurrency limits (MAX_CONCURRENT_ACCOUNT_JOBS=2, MAX_JOBS_PER_ACCOUNT=1),
fair scheduling across departments, per-account async locking, and comprehensive
pause, resume, and stop controls.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from core.account_executor import AccountExecutor
from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus
from core.browser_runtime import BrowserRuntime
from core.db_manager import DatabaseManager
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus, QueueManager
from core.round_robin_router import RoundRobinRouter

logger = logging.getLogger("tks.execution_coordinator")

DEFAULT_MAX_CONCURRENT_JOBS = 2
DEFAULT_MAX_JOBS_PER_ACCOUNT = 1


class ExecutionCoordinator:
    """Orchestrates parallel execution with fair scheduling and strict concurrency limits."""

    def __init__(
        self,
        browser_runtime: BrowserRuntime,
        queue_manager: QueueManager,
        account_manager: AccountManager,
        router: RoundRobinRouter,
        db_manager: DatabaseManager,
        max_concurrent_jobs: int = DEFAULT_MAX_CONCURRENT_JOBS,
        max_jobs_per_account: int = DEFAULT_MAX_JOBS_PER_ACCOUNT,
        allow_real_publishing: bool = False,
    ) -> None:
        self._runtime = browser_runtime
        self._queue = queue_manager
        self._account_mgr = account_manager
        self._router = router
        self._db = db_manager
        self._bridge = OfficeEventBridge.get_instance()

        self._max_concurrent = max_concurrent_jobs
        self._max_per_account = max_jobs_per_account
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)

        self._account_locks: dict[str, asyncio.Lock] = {}
        self._running_jobs: dict[str, JobRecord] = {}  # job_id -> JobRecord
        self._active_tasks: dict[str, asyncio.Task] = {}  # job_id -> Task

        self._paused_accounts: set[str] = set()
        self._paused_departments: set[str] = set()
        self._is_paused: bool = False
        self._is_stopped: bool = False
        self._allow_real_publishing: bool = allow_real_publishing

        self._executor = AccountExecutor(self._runtime, self._account_mgr)
        self._dept_rotation_idx: int = 0
        self._event_callbacks: list[Callable[[str, dict[str, Any]], None]] = []

    @property
    def allow_real_publishing(self) -> bool:
        return self._allow_real_publishing

    def set_real_publishing(self, enabled: bool, confirmed: bool = False) -> bool:
        """Explicit gate required to enable actual video submissions to TikTok Studio."""
        if enabled and not confirmed:
            logger.warning("Cannot enable real publishing without explicit confirmation.")
            self._allow_real_publishing = False
            return False
        self._allow_real_publishing = enabled
        logger.info(f"ExecutionCoordinator: Real publishing state set to {enabled} (confirmed={confirmed})")
        return self._allow_real_publishing

    @property
    def max_concurrent_jobs(self) -> int:
        return self._max_concurrent

    @property
    def active_job_count(self) -> int:
        return len(self._running_jobs)

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_stopped(self) -> bool:
        return self._is_stopped

    def register_callback(self, cb: Callable[[str, dict[str, Any]], None]) -> None:
        """Register listener for coordinator state events."""
        self._event_callbacks.append(cb)

    def _notify(self, event_type: str, data: dict[str, Any]) -> None:
        for cb in self._event_callbacks:
            try:
                cb(event_type, data)
            except Exception as exc:
                logger.debug(f"Callback error in coordinator: {exc}")

    def _get_account_lock(self, account_id: str) -> asyncio.Lock:
        if account_id not in self._account_locks:
            self._account_locks[account_id] = asyncio.Lock()
        return self._account_locks[account_id]

    def is_account_busy(self, account_id: str) -> bool:
        """Check if an account currently has an in-flight job."""
        lock = self._account_locks.get(account_id)
        if lock and lock.locked():
            return True
        for j in self._running_jobs.values():
            if j.account_id == account_id:
                return True
        return False

    def pause(self) -> None:
        """Alias for pause_all."""
        self.pause_all()

    def resume(self) -> None:
        """Alias for resume_all."""
        self.resume_all()

    def start(self) -> None:
        """Start or unpause execution loop."""
        self._is_stopped = False
        self._is_paused = False
        logger.info("ExecutionCoordinator: START/ACTIVE initiated.")
        self._notify("coordinator.started", {})

    def pause_all(self) -> None:
        """Pause scheduling across all departments and accounts."""
        self._is_paused = True
        logger.info("ExecutionCoordinator: Global PAUSE initiated.")
        self._notify("coordinator.paused", {})

    def resume_all(self) -> None:
        """Resume global scheduling."""
        self._is_paused = False
        logger.info("ExecutionCoordinator: Global RESUME initiated.")
        self._notify("coordinator.resumed", {})

    def pause_account(self, account_id: str) -> None:
        self._paused_accounts.add(account_id)
        logger.info(f"ExecutionCoordinator: Paused account {account_id}")

    def resume_account(self, account_id: str) -> None:
        self._paused_accounts.discard(account_id)
        logger.info(f"ExecutionCoordinator: Resumed account {account_id}")

    def pause_department(self, department_id: str) -> None:
        dept = self._db.get_department_by_id_or_name(department_id)
        if dept:
            self._paused_departments.add(dept["id"])
            logger.info(f"ExecutionCoordinator: Paused department {dept['name']}")

    def resume_department(self, department_id: str) -> None:
        dept = self._db.get_department_by_id_or_name(department_id)
        if dept:
            self._paused_departments.discard(dept["id"])
            logger.info(f"ExecutionCoordinator: Resumed department {dept['name']}")

    def stop(self) -> None:
        """Stop coordinator loop."""
        self._is_stopped = True
        logger.info("ExecutionCoordinator: STOP requested.")
        self._notify("coordinator.stopped", {})

    async def step(self, dry_run: bool = True) -> int:
        """Perform one scheduling tick across departments using fair round-robin.

        Returns number of tasks spawned in this tick.
        """
        if self._is_paused or self._is_stopped:
            return 0

        # Safety gate: force dry_run if real publishing is not explicitly confirmed
        if not dry_run and not self._allow_real_publishing:
            logger.warning("ExecutionCoordinator: Real mode attempted without explicit confirmation. Enforcing dry_run=True.")
            dry_run = True

        # Check if global concurrency capacity is available
        if self.active_job_count >= self._max_concurrent:
            return 0

        departments = self._db.get_departments(enabled_only=True)
        if not departments:
            return 0

        num_depts = len(departments)
        spawned = 0

        # Fair departmental round-robin scan
        for i in range(num_depts):
            if self.active_job_count >= self._max_concurrent:
                break

            dept_idx = (self._dept_rotation_idx + i) % num_depts
            dept = departments[dept_idx]
            dept_id = dept["id"]

            if dept_id in self._paused_departments:
                continue

            # Fetch pending jobs for this department
            pending = self._queue.get_pending_jobs(department_id=dept_id, limit=5)
            if not pending:
                continue

            for job in pending:
                if self.active_job_count >= self._max_concurrent:
                    break

                target_acc_id = job.account_id

                # If job was QUEUED without assigned account, resolve via RoundRobinRouter
                if not target_acc_id:
                    target_acc_id = self._router.select_next_account(dept_id, platform=job.platform)
                    if target_acc_id:
                        self._queue.update_job_status(
                            job.id,
                            JobStatus.ASSIGNED.value,
                            account_id=target_acc_id,
                        )
                        job.account_id = target_acc_id

                if not target_acc_id:
                    # No account currently available in this department, move to next dept
                    continue

                if target_acc_id in self._paused_accounts:
                    continue

                # Check account exclusivity (MAX_JOBS_PER_ACCOUNT = 1)
                if self.is_account_busy(target_acc_id):
                    continue

                # Account is free and capacity is available: register and dispatch immediately
                self._dept_rotation_idx = (dept_idx + 1) % num_depts
                self._running_jobs[job.id] = job
                self._queue.update_job_status(job.id, JobStatus.RUNNING.value)
                task = asyncio.create_task(self._execute_job_pipeline(job, dry_run=dry_run))
                self._active_tasks[job.id] = task
                spawned += 1
                break  # Advance to next department to ensure fair distribution

        return spawned

    async def _execute_job_pipeline(self, job: JobRecord, dry_run: bool = True) -> None:
        """Run execution pipeline for a single job under concurrency and per-account lock."""
        # Safety gate: ensure dry_run if real publishing is not explicitly confirmed
        if not dry_run and not self._allow_real_publishing:
            dry_run = True

        await self._semaphore.acquire()
        acc_id = job.account_id or ""
        lock = self._get_account_lock(acc_id)
        await lock.acquire()

        acc = self._account_mgr.get_account(acc_id)
        username = acc.username if acc else None

        # Telemetry: employee begins visual fetch from department drawer
        self._bridge.emit(
            "employee.fetch_started",
            department_id=job.department_id,
            account_id=acc_id,
            username=username,
            job_id=job.id,
            status="FETCHING",
        )

        try:
            self._notify("job.started", {"job_id": job.id, "account_id": acc_id})

            result = await self._executor.execute_task(job, dry_run=dry_run)

            if result.success:
                self._queue.update_job_status(job.id, result.status)
                self._notify("job.completed", {"job_id": job.id, "status": result.status})
            elif result.status == JobStatus.UNKNOWN.value:
                # UNKNOWN outcome: strictly do NOT retry automatically, preserve for operator inspection
                self._queue.update_job_status(
                    job.id,
                    JobStatus.UNKNOWN.value,
                    error_code=result.error_code or "OUTCOME_UNKNOWN",
                    error_message=result.error_message,
                )
                self._notify("job.unknown", {"job_id": job.id, "error": result.error_message})
            elif result.status == JobStatus.REAUTH_REQUIRED.value:
                self._queue.update_job_status(
                    job.id,
                    JobStatus.REAUTH_REQUIRED.value,
                    error_code=result.error_code,
                    error_message=result.error_message,
                )
                self.pause_account(acc_id)
                self._account_mgr.update_account(
                    acc_id,
                    auth_status=AccountAuthStatus.REAUTH_REQUIRED.value,
                    last_error=result.error_message,
                )
                self._notify("account.reauth_required", {"account_id": acc_id})
            else:
                self._queue.update_job_status(
                    job.id,
                    JobStatus.FAILED.value,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    increment_attempt=True,
                )
                self._notify("job.failed", {"job_id": job.id, "error": result.error_message})

        except Exception as exc:
            logger.error(f"Unexpected error executing job {job.id}: {exc}")
            self._queue.update_job_status(
                job.id,
                JobStatus.FAILED.value,
                error_code="UNEXPECTED_ERROR",
                error_message=str(exc),
                increment_attempt=True,
            )
        finally:
            self._running_jobs.pop(job.id, None)
            self._active_tasks.pop(job.id, None)
            lock.release()
            self._semaphore.release()

            # Virtual Office employee telemetry: returned to workstation
            self._bridge.emit(
                "employee.returned",
                department_id=job.department_id,
                account_id=acc_id,
                username=username,
                job_id=job.id,
            )

            # If no remaining running jobs for this department, mark employee idle
            dept_active = any(
                j.department_id == job.department_id
                for j in self._running_jobs.values()
            )
            if not dept_active:
                self._bridge.emit(
                    "employee.idle",
                    department_id=job.department_id,
                    account_id=acc_id,
                    username=username,
                )

    async def wait_for_completion(self, timeout: float = 30.0) -> None:
        """Wait until all running tasks are finished."""
        start = asyncio.get_event_loop().time()
        while self.active_job_count > 0:
            if asyncio.get_event_loop().time() - start > timeout:
                logger.warning("Timeout waiting for coordinator tasks to complete.")
                break
            await asyncio.sleep(0.05)
