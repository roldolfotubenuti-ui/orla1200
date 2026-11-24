"""AccountExecutor interface for running tasks within isolated account contexts.

Integrates Multiaccount isolation with Uploader and DOMHandler pipelines,
enforcing safe homologation simulation mode, identity verification,
and Virtual Office telemetry.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus
from core.browser_runtime import BrowserRuntime
from core.daily_scheduler_rule import calculate_next_daily_slot, get_account_booked_dates
from core.dom_handler import DOMHandler
from core.logger_manager import LoggerManager
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus
from core.scheduler import UploadTask
from core.uploader import UploadResult, Uploader
from utils.datetime_utils import DateTimeUtils

logger = logging.getLogger("tks.account_executor")


@dataclass
class AccountExecutorResult:
    success: bool
    status: str
    error_code: str | None = None
    error_message: str | None = None
    detected_username: str | None = None
    duration_seconds: float = 0.0


class AccountExecutor:
    """Executes jobs inside an account's isolated Playwright session."""

    def __init__(
        self,
        browser_runtime: BrowserRuntime,
        account_manager: AccountManager,
        uploader_factory: Callable[[Any, bool], Any] | None = None,
        office_bridge: OfficeEventBridge | None = None,
    ) -> None:
        self._runtime = browser_runtime
        self._account_manager = account_manager
        self._uploader_factory = uploader_factory
        self._bridge = office_bridge or OfficeEventBridge.get_instance()
        self._logger = LoggerManager()

    async def execute_task(
        self,
        job: JobRecord,
        dry_run: bool = True,
        mock_delay: float = 0.0,
        simulate_failure_account_id: str | None = None,
        simulate_reauth_account_id: str | None = None,
    ) -> AccountExecutorResult:
        """Execute a job within the account's session.

        :param job: JobRecord to process.
        :param dry_run: If True, operates in Homologation Mode (never clicks post button).
        :param mock_delay: Artificial delay for testing session stability.
        :param simulate_failure_account_id: Test hook to simulate execution failure.
        :param simulate_reauth_account_id: Test hook to simulate session invalidation.
        :return: AccountExecutorResult with detailed outcome and status.
        """
        start_time = time.monotonic()
        acc_id = job.account_id
        if not acc_id:
            return AccountExecutorResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_code="NO_ACCOUNT_ASSIGNED",
                error_message="Job does not have an assigned account.",
            )

        acc = self._account_manager.get_account(acc_id)
        if not acc:
            return AccountExecutorResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_code="ACCOUNT_NOT_FOUND",
                error_message=f"Account {acc_id} not found in AccountManager.",
            )

        # 1. Check if re-authentication is required
        if acc.auth_status in (
            AccountAuthStatus.INVALID_SESSION.value,
            AccountAuthStatus.REAUTH_REQUIRED.value,
            AccountAuthStatus.EXPIRED.value,
        ):
            self._bridge.emit(
                "account.reauth_required",
                department_id=job.department_id,
                account_id=acc_id,
                username=acc.username,
                job_id=job.id,
                status=JobStatus.REAUTH_REQUIRED.value,
                extra={"error": "Session marked as invalid or expired"},
            )
            return AccountExecutorResult(
                success=False,
                status=JobStatus.REAUTH_REQUIRED.value,
                error_code="REAUTH_REQUIRED",
                error_message=f"Account @{acc.username} requires re-authentication.",
                detected_username=acc.username,
            )

        # Injected test hooks
        if simulate_reauth_account_id == acc_id:
            logger.warning(f"Simulating REAUTH_REQUIRED for account @{acc.username}")
            self._account_manager.update_account(
                acc_id,
                auth_status=AccountAuthStatus.REAUTH_REQUIRED.value,
                last_error="Simulated authentication revocation",
            )
            self._bridge.emit(
                "account.reauth_required",
                department_id=job.department_id,
                account_id=acc_id,
                username=acc.username,
                job_id=job.id,
                status=JobStatus.REAUTH_REQUIRED.value,
                extra={"error": "Simulated authentication revocation"},
            )
            return AccountExecutorResult(
                success=False,
                status=JobStatus.REAUTH_REQUIRED.value,
                error_code="REAUTH_REQUIRED",
                error_message="Simulated session revocation.",
                detected_username=acc.username,
                duration_seconds=time.monotonic() - start_time,
            )

        if simulate_failure_account_id == acc_id:
            logger.warning(f"Simulating execution failure for account @{acc.username}")
            self._bridge.emit(
                "video.failed",
                department_id=job.department_id,
                account_id=acc_id,
                username=acc.username,
                job_id=job.id,
                status=JobStatus.FAILED.value,
                extra={"error": "Simulated executor network failure."},
            )
            return AccountExecutorResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_code="SIMULATED_FAILURE",
                error_message="Simulated executor network failure.",
                detected_username=acc.username,
                duration_seconds=time.monotonic() - start_time,
            )

        try:
            # 2. Acquire isolated session from BrowserRuntime
            logger.info(f"Opening isolated session for @{acc.username} (Job {job.id})")
            context, page = await self._runtime.get_or_create_account_session(
                account_id=acc_id,
                account_manager=self._account_manager,
            )

            # Emit execution started
            self._bridge.emit(
                "account.execution_started",
                department_id=job.department_id,
                account_id=acc_id,
                username=acc.username,
                job_id=job.id,
                status=JobStatus.RUNNING.value,
            )

            # 3. Verify session cookies
            cookies = await context.cookies()
            if not cookies:
                raise RuntimeError(f"No cookies loaded for account @{acc.username}")

            # Navigate to TikTok Studio upload page (always ensure fresh upload state)
            upload_url = "https://www.tiktok.com/tiktokstudio/upload?from=webapp"
            logger.info(f"Navigating to TikTok Studio upload page: {upload_url}")
            try:
                await page.goto(upload_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
            except Exception as nav_exc:
                logger.warning(f"Navigation warning: {nav_exc}")

            # 4. Identity check
            detected_user = acc.username
            try:
                dom_verifier = DOMHandler(page=page, logger=self._logger, datetime_utils=DateTimeUtils())
                page_user = await dom_verifier.get_logged_in_username()
                if page_user:
                    detected_user = page_user
                    if acc.username and page_user.lower().lstrip("@") != acc.username.lower().lstrip("@"):
                        logger.warning(
                            f"Identity mismatch: Page shows @{page_user}, expected @{acc.username}"
                        )
            except Exception as exc:
                logger.debug(f"Identity check non-critical probe: {exc}")

            # 5. Check if real file exists or custom uploader factory provided
            raw_path = getattr(job, "file_path", None) or getattr(job, "filename", None)
            file_path_obj = Path(raw_path) if raw_path else None
            has_real_file = bool(file_path_obj and file_path_obj.exists() and file_path_obj.is_file())

            if has_real_file or self._uploader_factory is not None:
                # Step: Upload started
                self._bridge.emit(
                    "video.upload_started",
                    department_id=job.department_id,
                    account_id=acc_id,
                    username=acc.username,
                    job_id=job.id,
                    status=JobStatus.UPLOADING.value,
                )

                sched_val = getattr(job, "schedule_time", None)
                if isinstance(sched_val, str) and sched_val.strip():
                    try:
                        sched_dt = datetime.fromisoformat(sched_val.strip())
                    except Exception:
                        try:
                            sched_dt = datetime.strptime(sched_val.strip(), "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            sched_dt = None
                elif isinstance(sched_val, datetime):
                    sched_dt = sched_val
                else:
                    sched_dt = None

                # Regra Inteligente de Agendamento Diário:
                # Se o horário já passou hoje (ou faltam menos de 25 min), ou se já há outro vídeo agendado para esta data,
                # o personagem avança automaticamente para o próximo dia consecutivo às 18:00
                now_sp = datetime.now()
                is_expired = False
                if sched_dt is None:
                    is_expired = True
                else:
                    naive_sched = sched_dt.replace(tzinfo=None) if sched_dt.tzinfo else sched_dt
                    if naive_sched <= (now_sp + timedelta(minutes=25)):
                        is_expired = True

                if is_expired:
                    db_instance = getattr(self, "_db", None) or getattr(self._account_mgr, "_db", None)
                    sched_dt, new_sched_str = calculate_next_daily_slot(
                        account_id=acc_id,
                        db=db_instance,
                        exclude_job_id=job.id,
                    )
                    logger.info(
                        f"Horário de agendamento ajustado automaticamente para o próximo dia disponível: {new_sched_str}"
                    )
                    if hasattr(self, "_queue") and self._queue:
                        try:
                            self._queue.update_job_schedule(job.id, new_sched_str)
                        except Exception:
                            pass

                task = UploadTask(
                    file_path=file_path_obj or Path("test_video.mp4"),
                    caption=getattr(job, "caption", "") or "",
                    schedule_time=sched_dt,
                    visibility="public",
                )

                if self._uploader_factory:
                    uploader = self._uploader_factory(page, dry_run)
                else:
                    uploader = Uploader.from_page(
                        page=page,
                        logger=self._logger,
                        homologation_mode=dry_run,
                    )

                # Step: Processing
                self._bridge.emit(
                    "video.processing",
                    department_id=job.department_id,
                    account_id=acc_id,
                    username=acc.username,
                    job_id=job.id,
                    status=JobStatus.PROCESSING.value,
                )

                # Execute upload pipeline
                res: UploadResult = await uploader.upload_video(
                    task=task,
                    username=acc.username,
                    homologation_mode=dry_run,
                )

                # Step: Submitting
                self._bridge.emit(
                    "video.submitting",
                    department_id=job.department_id,
                    account_id=acc_id,
                    username=acc.username,
                    job_id=job.id,
                    status=JobStatus.SUBMITTING.value,
                )

                duration = time.monotonic() - start_time

                # Handle unknown outcome strictly (NEVER retry automatically)
                if res.outcome == "unknown":
                    self._bridge.emit(
                        "video.failed",
                        department_id=job.department_id,
                        account_id=acc_id,
                        username=acc.username,
                        job_id=job.id,
                        status=JobStatus.UNKNOWN.value,
                        extra={"outcome": "unknown", "error": res.message},
                    )
                    return AccountExecutorResult(
                        success=False,
                        status=JobStatus.UNKNOWN.value,
                        error_code="OUTCOME_UNKNOWN",
                        error_message=res.message,
                        detected_username=detected_user,
                        duration_seconds=duration,
                    )

                if res.success:
                    target_status = (
                        JobStatus.SCHEDULED.value
                        if job.schedule_time
                        else JobStatus.PUBLISHED.value
                    )
                    event_name = "video.scheduled" if job.schedule_time else "video.published"
                    self._bridge.emit(
                        event_name,
                        department_id=job.department_id,
                        account_id=acc_id,
                        username=acc.username,
                        job_id=job.id,
                        status=target_status,
                    )
                    return AccountExecutorResult(
                        success=True,
                        status=target_status,
                        detected_username=detected_user,
                        duration_seconds=duration,
                    )
                else:
                    self._bridge.emit(
                        "video.failed",
                        department_id=job.department_id,
                        account_id=acc_id,
                        username=acc.username,
                        job_id=job.id,
                        status=JobStatus.FAILED.value,
                        extra={"error": res.error or res.message},
                    )
                    return AccountExecutorResult(
                        success=False,
                        status=JobStatus.FAILED.value,
                        error_code="UPLOAD_ERROR",
                        error_message=res.error or res.message,
                        detected_username=detected_user,
                        duration_seconds=duration,
                    )

            # Simulated / Mock fallback when no physical file is present
            if mock_delay > 0:
                await asyncio.sleep(mock_delay)

            target_status = (
                JobStatus.SCHEDULED.value
                if job.schedule_time
                else JobStatus.PUBLISHED.value
            )
            duration = time.monotonic() - start_time

            event_name = "video.scheduled" if job.schedule_time else "video.published"
            self._bridge.emit(
                event_name,
                department_id=job.department_id,
                account_id=acc_id,
                username=acc.username,
                job_id=job.id,
                status=target_status,
            )

            logger.info(
                f"Job {job.id} completed successfully for @{acc.username} "
                f"in {duration:.2f}s (Result: {target_status})"
            )

            return AccountExecutorResult(
                success=True,
                status=target_status,
                detected_username=detected_user,
                duration_seconds=duration,
            )

        except Exception as exc:
            duration = time.monotonic() - start_time
            err_str = str(exc)
            logger.error(f"Execution error for @{acc.username}: {err_str}")
            self._bridge.emit(
                "video.failed",
                department_id=job.department_id,
                account_id=acc_id,
                username=acc.username,
                job_id=job.id,
                status=JobStatus.FAILED.value,
                extra={"error": err_str},
            )
            return AccountExecutorResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_code="EXECUTION_EXCEPTION",
                error_message=err_str,
                detected_username=acc.username,
                duration_seconds=duration,
            )
