from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.dom_handler import DOMHandler, PostError, RateLimitError
from core.logger_manager import LoggerManager
from core.scheduler import UploadTask
from utils.datetime_utils import DateTimeUtils


class UploadError(Exception):
  """
  Raised when a video upload operation fails.
  """


@dataclass
class UploadResult:
  """
  Result of a single upload attempt.

  :param success: Whether the upload succeeded.
  :type success: bool
  :param file_path: Path of the uploaded file.
  :type file_path: Path
  :param message: Human-readable status message.
  :type message: str
  :param timestamp: When the upload completed.
  :type timestamp: datetime
  :param error: Error details if the upload failed.
  :type error: str | None
  :param cm: Music copyright flag.
  :type cm: bool
  :param qc: Quality check message.
  :type qc: str
  :param outcome: Detailed technical outcome.
  :type outcome: str
  :param telemetry: Step-by-step monotonic performance timings.
  :type telemetry: dict | None
  :param status: Standardized status ('scheduled', 'published', 'failed', 'unknown').
  :type status: str
  :param is_scheduled: Whether this task was an explicit schedule with future time.
  :type is_scheduled: bool
  """

  success: bool
  file_path: Path
  message: str
  timestamp: datetime
  error: str | None = None
  cm: bool = False
  qc: str = ""
  outcome: str = ""
  telemetry: dict | None = None
  status: str = ""
  is_scheduled: bool = False

  def __post_init__(self) -> None:
    if not self.outcome:
      self.outcome = "confirmed_success" if self.success else "confirmed_failure"
    if not self.status:
      if self.outcome == "unknown":
        self.status = "unknown"
      elif self.success:
        self.status = "scheduled" if self.is_scheduled else "published"
      else:
        self.status = "failed"

  def to_dict(self) -> dict:
    """
    Serialize this result to a dictionary for JSON storage.

    :return: Dictionary representation.
    :rtype: dict
    """
    st = self.status
    if not st:
      if self.outcome == "unknown":
        st = "unknown"
      elif self.success:
        st = "scheduled" if self.is_scheduled else "published"
      else:
        st = "failed"
    return {
      "file": str(self.file_path),
      "message": self.message,
      "status": st,
      "outcome": self.outcome,
      "timestamp": DateTimeUtils.format_iso(self.timestamp),
      "error": self.error,
      "cm": self.cm,
      "qc": self.qc,
      "telemetry": self.telemetry,
    }


class Uploader:
  """
  Orchestrates the full upload pipeline for a single video.

  Manages the sequence: file upload -> caption entry -> schedule
  configuration -> visibility selection -> post submission. Includes
  retry logic with exponential backoff.

  :param dom_handler: DOMHandler instance for page interactions.
  :type dom_handler: DOMHandler
  :param logger: Logger instance for status messages.
  :type logger: LoggerManager
  """

  def __init__(
    self,
    dom_handler: DOMHandler,
    logger: LoggerManager,
    storage_dir: Path | None = None,
    homologation_mode: bool = False,
  ) -> None:
    """
    Initialize Uploader.

    :param dom_handler: DOMHandler instance for page interactions.
    :type dom_handler: DOMHandler
    :param logger: Logger instance.
    :type logger: LoggerManager
    :param storage_dir: Directory for copyright.json and schedule files.
    :type storage_dir: Path | None
    :param homologation_mode: When True, simulates upload without clicking post button.
    :type homologation_mode: bool
    """
    self._dom_handler = dom_handler
    self._logger = logger
    self._storage_dir = storage_dir
    self._homologation_mode = homologation_mode

  @classmethod
  def from_page(
    cls,
    page: Any,
    logger: LoggerManager,
    storage_dir: Path | None = None,
    homologation_mode: bool = True,
  ) -> Uploader:
    """
    Convenience factory to create an Uploader directly from a Playwright Page instance.

    :param page: Active Playwright Page.
    :param logger: Logger instance.
    :param storage_dir: Directory for persistence files.
    :param homologation_mode: Whether to run in safe non-publishing simulation mode.
    :return: Configured Uploader instance.
    """
    from utils.datetime_utils import DateTimeUtils
    dom_handler = DOMHandler(page=page, logger=logger, datetime_utils=DateTimeUtils())
    return cls(
      dom_handler=dom_handler,
      logger=logger,
      storage_dir=storage_dir,
      homologation_mode=homologation_mode,
    )

  async def upload_video(
    self,
    task: UploadTask,
    telemetry_base: dict | None = None,
    username: str = "",
    homologation_mode: bool | None = None,
  ) -> UploadResult:
    """
    Execute the full upload pipeline for a single video.

    Pipeline steps:
    1. Upload file via hidden input
    2. Wait for upload completion
    3. Set caption text
    4. Enable scheduling and set time/date (if scheduled)
    5. Set visibility mode
    6. Verify post button readiness and click post
    7. Wait for submission confirmation

    :param task: Upload task with file, caption, schedule, and visibility.
    :type task: UploadTask
    :param telemetry_base: Pre-measured browser setup timings.
    :type telemetry_base: dict | None
    :param username: Sanitized username for telemetry reporting.
    :type username: str
    :return: Structured result of the upload attempt.
    :rtype: UploadResult
    """
    filename = task.file_path.name
    self._logger.info(f"Starting upload for {filename}")
    post_clicked = False
    video_start_time = time.monotonic()

    telemetry_base = telemetry_base or {}
    t_browser_init = float(telemetry_base.get("browser_init_sec", 0.0))
    t_studio_load = float(telemetry_base.get("studio_load_sec", 0.0))
    t_auth = float(telemetry_base.get("auth_sec", 0.0))
    t_upload = 0.0
    t_caption = 0.0
    t_date = 0.0
    t_time = 0.0
    t_quality = 0.0
    t_submit = 0.0
    t_confirm = 0.0
    t_button_enable_wait = None
    t_content_check_timeout = False
    schedule_validation_err = False
    schedule_rejection_reason = None

    def _build_telemetry() -> dict:
      t_total = (time.monotonic() - video_start_time) + t_browser_init + t_studio_load + t_auth
      return {
        "browser_init_sec": round(t_browser_init, 2),
        "studio_load_sec": round(t_studio_load, 2),
        "auth_sec": round(t_auth, 2),
        "upload_sec": round(t_upload, 2),
        "caption_sec": round(t_caption, 2),
        "date_config_sec": round(t_date, 2),
        "time_config_sec": round(t_time, 2),
        "quality_check_sec": round(t_quality, 2),
        "content_processing_wait_sec": round(t_quality, 2),
        "button_enable_wait_sec": t_button_enable_wait,
        "content_check_timeout": t_content_check_timeout,
        "schedule_validation_error": schedule_validation_err,
        "schedule_rejection_reason": schedule_rejection_reason,
        "submission_sec": round(t_submit, 2),
        "confirmation_sec": round(t_confirm, 2),
        "total_sec": round(t_total, 2),
        "browser_reused": bool(telemetry_base.get("browser_reused", False)),
        "session_reused": bool(telemetry_base.get("session_reused", False)),
        "page_reloaded": bool(telemetry_base.get("page_reloaded", False)),
        "browser_recovery_sec": round(float(telemetry_base.get("browser_recovery_sec", 0.0)), 2),
        "browser_restart_count": int(telemetry_base.get("browser_restart_count", 0)),
        "videos_processed_per_browser_session": int(
          telemetry_base.get("videos_processed_per_browser_session", 1)
        ),
      }

    def _log_telemetry(t_data: dict, q_state: str) -> None:
      acct_label = f"@{username}" if username else "Conta ativa"
      session_status = "Reutilizada" if t_data.get("session_reused") else "Nova inicialização"
      btn_wait_str = f"{t_data['button_enable_wait_sec']}s" if t_data.get('button_enable_wait_sec') is not None else "imediato/N/A"
      self._logger.info(
        f"[TELEMETRIA] Video: {filename} | {acct_label}\n"
        f"  • Sessão do Navegador: {session_status} (Vídeo #{t_data.get('videos_processed_per_browser_session', 1)} na sessão)\n"
        f"  • Tempo de inicialização do navegador: {t_data['browser_init_sec']}s\n"
        f"  • Tempo de carregamento do TikTok Studio: {t_data['studio_load_sec']}s\n"
        f"  • Tempo de autenticação: {t_data['auth_sec']}s\n"
        f"  • Tempo de upload: {t_data['upload_sec']}s\n"
        f"  • Tempo de preenchimento da legenda: {t_data['caption_sec']}s\n"
        f"  • Tempo de configuração da data: {t_data['date_config_sec']}s\n"
        f"  • Tempo de configuração do horário: {t_data['time_config_sec']}s\n"
        f"  • Tempo de verificação do conteúdo: {t_data['quality_check_sec']}s ({q_state})\n"
        f"  • Tempo de liberação do botão: {btn_wait_str}\n"
        f"  • Tempo de submissão: {t_data['submission_sec']}s\n"
        f"  • Tempo de confirmação: {t_data['confirmation_sec']}s\n"
        f"  • Tempo total: {t_data['total_sec']}s"
      )

    try:
      # Dismiss any blocking popups before starting
      await self._dom_handler.dismiss_all_popups()

      # Step 1: Upload file
      t_upload_start = time.monotonic()
      await self._dom_handler.upload_file(task.file_path)

      # Step 2: Wait for upload to complete
      upload_ok = await self._dom_handler.wait_upload_complete(timeout=120)
      t_upload = time.monotonic() - t_upload_start

      if not upload_ok:
        t_data = _build_telemetry()
        _log_telemetry(t_data, "upload_timeout")
        return UploadResult(
          success=False,
          file_path=task.file_path,
          message="Upload timed out",
          timestamp=datetime.now(),
          error="File upload did not complete within 120 seconds",
          telemetry=t_data,
        )

      # Dismiss popups that may have appeared during upload
      await self._dom_handler.dismiss_all_popups()

      # Step 3: Set caption
      if task.caption:
        t_caption_start = time.monotonic()
        await self._dom_handler.set_caption(task.caption)
        t_caption = time.monotonic() - t_caption_start

      # Step 4: Schedule (if specified)
      if task.schedule_time is not None:
        await self._dom_handler.enable_schedule()
        await self._dom_handler.dismiss_allow_schedule()

        # CRITICAL: Always set DATE first so tomorrow's date is established,
        # otherwise setting time first for today (in the past) gets rejected by TikTok!
        day, month, year = DateTimeUtils.parse_day_month_year(task.schedule_time)
        t_date_start = time.monotonic()
        await self._dom_handler.set_date(day, month, year)
        t_date = time.monotonic() - t_date_start

        hour, minute = DateTimeUtils.parse_hour_minute(task.schedule_time)
        t_time_start = time.monotonic()
        await self._dom_handler.set_time(hour, minute)
        t_time = time.monotonic() - t_time_start

        # Phase 2.5: Verify schedule inputs in DOM and detect validation errors
        if hasattr(self._dom_handler, "verify_schedule_inputs"):
          sched_verify = await self._dom_handler.verify_schedule_inputs(
            expected_hour=hour,
            expected_minute=minute,
            expected_day=day,
            expected_month_name=getattr(self._dom_handler, "MONTH_NAMES", {}).get(month, ""),
          )
          if not sched_verify.get("valid", True):
            reason = sched_verify.get("reason", "Erro de agendamento no DOM do TikTok")
            schedule_validation_err = True
            schedule_rejection_reason = reason
            self._logger.error(f"Schedule configuration failed in DOM: {reason}")
            t_data = _build_telemetry()
            _log_telemetry(t_data, "schedule_error")
            return UploadResult(
              success=False,
              file_path=task.file_path,
              message=f"Schedule validation failed in DOM: {reason}",
              timestamp=datetime.now(),
              error=reason,
              cm=False,
              qc="schedule_error",
              telemetry=t_data,
            )

      # Step 5: Set visibility
      await self._dom_handler.set_visibility(task.visibility)

      # Step 5b: Check music copyright
      copyright_result = await self._dom_handler.check_music_copyright()
      has_copyright = copyright_result.get("has_copyright", False)
      copyright_msg = copyright_result.get("message", "")

      # Step 5c: Check content quality (non-blocking when platform allows)
      t_quality_start = time.monotonic()
      quality_result = await self._dom_handler.check_content_quality()
      t_quality = time.monotonic() - t_quality_start
      quality_state = quality_result.get("state", "")
      quality_msg = quality_result.get("message", "")
      t_button_enable_wait = quality_result.get("button_enable_wait_sec")
      t_content_check_timeout = bool(quality_result.get("content_check_timeout", False))

      # If music has copyright, save to copyright.json and abort
      if has_copyright:
        self._logger.error(
          f"Music copyright detected for {filename}: {copyright_msg}"
        )
        self._save_copyright_record(
          filename=filename,
          music_message=copyright_msg,
          quality_message=quality_msg,
        )
        t_data = _build_telemetry()
        _log_telemetry(t_data, quality_state)
        return UploadResult(
          success=False,
          file_path=task.file_path,
          message="Music copyright detected — upload aborted",
          timestamp=datetime.now(),
          error=copyright_msg,
          cm=True,
          qc=quality_msg,
          telemetry=t_data,
        )

      # If content check reported an impeding / blocking error, abort
      if quality_result.get("blocking", False):
        self._logger.error(
          f"Content check reported blocking condition for {filename}: {quality_msg}"
        )
        t_data = _build_telemetry()
        _log_telemetry(t_data, quality_state)
        return UploadResult(
          success=False,
          file_path=task.file_path,
          message=f"Content check blocked: {quality_msg}",
          timestamp=datetime.now(),
          error=quality_msg,
          cm=False,
          qc=quality_msg,
          telemetry=t_data,
        )

      # Step 6: Verify post button readiness
      if hasattr(self._dom_handler, "is_post_button_enabled"):
        is_enabled = await self._dom_handler.is_post_button_enabled()
        if not is_enabled:
          self._logger.error(f"Post button is disabled for {filename} — cannot proceed")
          t_data = _build_telemetry()
          _log_telemetry(t_data, quality_state)
          return UploadResult(
            success=False,
            file_path=task.file_path,
            message="Post button is disabled",
            timestamp=datetime.now(),
            error="Post button remained disabled in TikTok Studio",
            cm=False,
            qc=quality_msg,
            telemetry=t_data,
          )

      # Homologation safety interceptor: verify readiness but never click post button
      is_homologation = self._homologation_mode if homologation_mode is None else homologation_mode
      if is_homologation:
        self._logger.info(
          f"[HOMOLOGAÇÃO] Botão de postagem/agendamento verificado e pronto para {filename}. "
          f"Postagem real BLOQUEADA por segurança no Modo Homologação."
        )
        t_data = _build_telemetry()
        _log_telemetry(t_data, quality_state)

        if hasattr(self._dom_handler, "cancel_or_dismiss_upload"):
          await self._dom_handler.cancel_or_dismiss_upload()

        schedule_info = ""
        if task.schedule_time:
          schedule_info = f" (agendado simulado: {DateTimeUtils.format_for_display(task.schedule_time)})"

        return UploadResult(
          success=True,
          file_path=task.file_path,
          message=f"Simulação de homologação concluída com sucesso{schedule_info} (botão verificado e preservado)",
          timestamp=datetime.now(),
          cm=False,
          qc=quality_msg,
          outcome="simulation_success",
          telemetry=t_data,
          status="scheduled" if task.schedule_time else "published",
          is_scheduled=bool(task.schedule_time),
        )

      # Click post (Only in REAL OPERATION MODE with homologation_mode=False)
      t_submit_start = time.monotonic()
      await self._dom_handler.click_post()
      post_clicked = True
      t_submit = time.monotonic() - t_submit_start

      # Step 6b: Handle any confirmation modals (copyright, in-progress check, etc.)
      if hasattr(self._dom_handler, "handle_all_post_modals"):
        await self._dom_handler.handle_all_post_modals()
      elif hasattr(self._dom_handler, "handle_copyright_modal"):
        await asyncio.sleep(1)
        await self._dom_handler.handle_copyright_modal()

      # Step 7: Wait for confirmation
      t_confirm_start = time.monotonic()
      post_ok = await self._dom_handler.wait_post_complete(timeout=60)
      t_confirm = time.monotonic() - t_confirm_start

      t_data = _build_telemetry()
      _log_telemetry(t_data, quality_state)

      if not post_ok:
        return UploadResult(
          success=False,
          file_path=task.file_path,
          message="Post confirmation timed out (outcome unknown)",
          timestamp=datetime.now(),
          error="Post button clicked but confirmation not received",
          cm=False,
          qc=quality_msg,
          outcome="unknown",
          telemetry=t_data,
        )

      # Success
      schedule_info = ""
      if task.schedule_time:
        schedule_info = f" (scheduled: {DateTimeUtils.format_for_display(task.schedule_time)})"

      if hasattr(self._logger, "success"):
        self._logger.success(f"Upload complete: {filename}{schedule_info}")
      else:
        self._logger.info(f"SUCCESS: Upload complete: {filename}{schedule_info}")

      return UploadResult(
        success=True,
        file_path=task.file_path,
        message=f"Upload successful{schedule_info}",
        timestamp=datetime.now(),
        cm=False,
        qc=quality_msg,
        outcome="confirmed_success",
        telemetry=t_data,
        status="scheduled" if task.schedule_time else "published",
        is_scheduled=bool(task.schedule_time),
      )

    except RateLimitError:
      # Let rate limit propagate — the worker must stop all uploads
      raise

    except PostError as e:
      error_msg = str(e)
      self._logger.error(f"Explicit post error for {filename}: {error_msg}")
      return UploadResult(
        success=False,
        file_path=task.file_path,
        message="Post rejected by TikTok",
        timestamp=datetime.now(),
        error=error_msg,
        outcome="confirmed_failure",
      )

    except Exception as e:
      error_msg = str(e)
      self._logger.error(f"Upload failed for {filename}: {error_msg}")
      outcome = "unknown" if post_clicked else "confirmed_failure"
      msg = (
        "Upload interrupted after post click (outcome unknown)"
        if post_clicked
        else "Upload failed"
      )

      return UploadResult(
        success=False,
        file_path=task.file_path,
        message=msg,
        timestamp=datetime.now(),
        error=error_msg,
        outcome=outcome,
      )

  def _save_copyright_record(
    self,
    filename: str,
    music_message: str,
    quality_message: str,
  ) -> None:
    """
    Append a copyright failure record to ``storage/copyright.json``.

    :param filename: Name of the video file (e.g. ``sample.mp4``).
    :type filename: str
    :param music_message: Copyright check message from TikTok.
    :type music_message: str
    :param quality_message: Content quality check message.
    :type quality_message: str
    """
    if self._storage_dir is None:
      self._logger.warning(
        "No storage_dir configured — skipping copyright.json write"
      )
      return

    copyright_path = self._storage_dir / "copyright.json"

    # Load existing data
    data: dict = {}
    if copyright_path.exists():
      try:
        with open(copyright_path, "r", encoding="utf-8") as f:
          data = json.load(f)
      except (json.JSONDecodeError, OSError):
        data = {}

    # Add / overwrite entry for this file
    data[filename] = {
      "date_failed": DateTimeUtils.format_iso(datetime.now()),
      "music_message": music_message,
      "quality_message": quality_message,
    }

    # Write back
    try:
      self._storage_dir.mkdir(parents=True, exist_ok=True)
      temp = copyright_path.with_suffix(".tmp")
      with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
      temp.replace(copyright_path)
      self._logger.info(f"Copyright record saved for {filename}")
    except OSError as e:
      self._logger.error(f"Failed to save copyright.json: {e}")

  async def retry_upload(
    self,
    task: UploadTask,
    max_retries: int = 3,
    navigate_callback=None,
    telemetry_base: dict | None = None,
    username: str = "",
  ) -> UploadResult:
    """
    Wrap upload_video with retry logic and exponential backoff.

    On failure, waits progressively longer between attempts and
    optionally calls a navigation callback to refresh the upload page
    before retrying.

    :param task: Upload task to retry.
    :type task: UploadTask
    :param max_retries: Maximum number of attempts.
    :type max_retries: int
    :param navigate_callback: Async callable to navigate to a fresh upload
        page between retries (e.g., ``browser_manager.new_upload_page``).
    :type navigate_callback: Callable[[], Awaitable[None]] | None
    :param telemetry_base: Pre-measured browser setup timings.
    :type telemetry_base: dict | None
    :param username: Sanitized username for telemetry reporting.
    :type username: str
    :return: Result from the last attempt.
    :rtype: UploadResult
    """
    result: UploadResult | None = None

    for attempt in range(1, max_retries + 1):
      self._logger.info(
        f"Upload attempt {attempt}/{max_retries} for {task.file_path.name}"
      )

      result = await self.upload_video(
        task,
        telemetry_base=telemetry_base,
        username=username,
      )

      if result.success:
        return result

      if result.outcome == "unknown":
        self._logger.warning(
          f"Attempt {attempt} outcome is UNKNOWN (post was already clicked). "
          "Skipping automatic retry to prevent duplicate publication."
        )
        return result

      self._logger.warning(
        f"Attempt {attempt} failed: {result.error}"
      )

      if attempt < max_retries:
        backoff = 5 * attempt
        self._logger.info(f"Retrying in {backoff}s...")
        await asyncio.sleep(backoff)

        # Refresh the page for a clean upload form
        if navigate_callback is not None:
          try:
            await navigate_callback()
          except Exception as e:
            self._logger.error(f"Navigation callback failed: {e}")

    # Return last failed result
    return result  # type: ignore[return-value]
