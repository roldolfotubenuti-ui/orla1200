from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.browser_manager import BrowserManager
from core.cookie_manager import CookieManager
from core.dom_handler import DOMHandler, RateLimitError
from core.logger_manager import LoggerManager
from core.schedule_rule_engine import ScheduleRuleEngine
from core.scheduler import UploadTask
from core.uploader import UploadResult, Uploader
from utils.datetime_utils import DateTimeUtils


class UploadWorker(QThread):
  """Run the async upload pipeline in a background thread.

  :param cookie_manager: Cookie manager used to authenticate the browser.
  :param username: Account username.
  :param tasks: Upload tasks to process.
  :param headless: Whether to launch the browser headlessly.
  :param retry_enabled: Whether failed uploads should be retried.
  :param logger: Logger instance.
  :param rule_engine: Schedule validation engine.
  :param storage_dir: Optional storage directory.
  :param process_limit: Maximum number of videos to process.
  :return: None
  """

  progress_update = pyqtSignal(int, int, int, int)
  log_message = pyqtSignal(str, int)
  upload_started = pyqtSignal(str)
  upload_complete = pyqtSignal(bool, str)
  finished_all = pyqtSignal()
  error_occurred = pyqtSignal(str)
  rate_limited = pyqtSignal(str)

  def __init__(
    self,
    cookie_manager: CookieManager,
    username: str,
    tasks: list[UploadTask],
    headless: bool,
    retry_enabled: bool,
    logger: LoggerManager,
    rule_engine: ScheduleRuleEngine,
    storage_dir: Path | None = None,
    process_limit: int = 0,
  ) -> None:
    """Initialize the upload worker.

    :param cookie_manager: Cookie manager used to authenticate the browser.
    :param username: Account username.
    :param tasks: Upload tasks to process.
    :param headless: Whether to launch the browser headlessly.
    :param retry_enabled: Whether failed uploads should be retried.
    :param logger: Logger instance.
    :param rule_engine: Schedule validation engine.
    :param storage_dir: Optional storage directory.
    :param process_limit: Maximum number of videos to process.
    :return: None
    """
    super().__init__()
    self._cookie_manager = cookie_manager
    self._username = username
    self._tasks = tasks
    self._headless = headless
    self._retry_enabled = retry_enabled
    self._logger = logger
    self._rules = rule_engine
    self._storage_dir = storage_dir
    self._process_limit = process_limit
    self._stop_flag = False
    self._pause_flag = False
    self._results: list[UploadResult] = []

  def run(self) -> None:
    """Start the worker event loop.

    :return: None
    """
    try:
      asyncio.run(self._execute())
    except Exception as exc:
      self._logger.error(f"Fatal worker exception: {exc}\n{traceback.format_exc()}")
      self.error_occurred.emit(str(exc))

  async def _execute(self) -> None:
    """Execute the upload pipeline sequentially.

    :return: None
    """
    browser_manager = BrowserManager(
      cookie_manager=self._cookie_manager,
      logger=self._logger,
      headless=self._headless,
    )

    total = len(self._tasks)
    success_count = 0
    failed_count = 0

    try:
      await browser_manager.launch(self._username)

      for index, task in enumerate(self._tasks):
        while self._pause_flag and not self._stop_flag:
          await asyncio.sleep(0.5)
        if self._stop_flag:
          self._logger.info("Upload stopped by user")
          break

        self._logger.info(f"Processing: {index + 1} of {len(self._tasks)} ({task.file_path.name})")
        self.upload_started.emit(task.file_path.name)

        processed = success_count + failed_count
        if self._process_limit > 0 and processed >= self._process_limit:
          self._logger.info(
            f"Process limit reached ({self._process_limit}) - stopping"
          )
          break

        if task.schedule_time is not None:
          # Phase 2.5: Strict revalidation before each video upload
          valid, reason = self._rules.validate(task.schedule_time)
          if not valid:
            self._logger.error(
              f"Skipping {task.file_path.name}: Schedule time ({DateTimeUtils.format_for_display(task.schedule_time)}) "
              f"is no longer valid at execution time ({reason}). Aborting upload to prevent rejection."
            )
            result = UploadResult(
              success=False,
              file_path=task.file_path,
              message="Schedule validation failed (expired or insufficient lead time)",
              timestamp=datetime.now(),
              error=reason,
            )
            self._results.append(result)
            failed_count += 1
            self.progress_update.emit(index + 1, total, success_count, failed_count)
            self.upload_complete.emit(False, task.file_path.name)
            continue

        page = browser_manager.get_page()
        datetime_utils = DateTimeUtils()
        dom_handler = DOMHandler(page, self._logger, datetime_utils)
        uploader = Uploader(dom_handler, self._logger, self._storage_dir)
        telemetry_base = getattr(browser_manager, "telemetry", {})

        if self._retry_enabled:
          result = await uploader.retry_upload(
            task=task,
            max_retries=3,
            navigate_callback=browser_manager.new_upload_page,
            telemetry_base=telemetry_base,
            username=self._username,
          )
        else:
          result = await uploader.upload_video(
            task=task,
            telemetry_base=telemetry_base,
            username=self._username,
          )

        self._results.append(result)
        if result.success:
          success_count += 1
        else:
          failed_count += 1

        self.progress_update.emit(index + 1, total, success_count, failed_count)
        self.upload_complete.emit(result.success, task.file_path.name)

        if index < total - 1 and not self._stop_flag:
          # Prepare the existing browser page for the next video without destroying Chromium
          await browser_manager.prepare_for_next_video()

      # Queue completion summary
      total_time = sum(
        getattr(r, "telemetry", {}).get("total_sec", 0.0)
        for r in self._results
        if r and getattr(r, "telemetry", None)
      )
      avg_time = (total_time / len(self._results)) if self._results else 0.0
      restart_count = getattr(browser_manager, "restart_count", 0)
      reused_sessions = sum(
        1 for r in self._results
        if r and getattr(r, "telemetry", {}).get("session_reused", False)
      )
      self._logger.info(
        f"[RESUMO DA FILA] Conta: @{self._username}\n"
        f"  • Total de Vídeos: {len(self._tasks)}\n"
        f"  • Concluídos com Sucesso: {success_count}\n"
        f"  • Falhas: {failed_count}\n"
        f"  • Inicializações do Navegador: {1 + restart_count}\n"
        f"  • Sessões Reutilizadas: {reused_sessions}\n"
        f"  • Reinicializações/Recuperações: {restart_count}\n"
        f"  • Tempo Total da Fila: {total_time:.2f}s (Média: {avg_time:.2f}s / vídeo)"
      )

    except RateLimitError as exc:
      self._stop_flag = True
      toast_message = str(exc)
      self._logger.error(f"Account rate limit reached: {toast_message}")
      self.rate_limited.emit(toast_message)
    except Exception as exc:
      self._logger.error(f"Execution error: {exc}\n{traceback.format_exc()}")
      self.error_occurred.emit(str(exc))
    finally:
      await browser_manager.close()
      self.finished_all.emit()

  def request_stop(self) -> None:
    """Signal the worker to stop after the current upload.

    :return: None
    """
    self._stop_flag = True

  def toggle_pause(self) -> None:
    """Toggle the paused state.

    :return: None
    """
    self._pause_flag = not self._pause_flag

  @property
  def is_paused(self) -> bool:
    """Return whether the worker is currently paused.

    :return: ``True`` when paused.
    """
    return self._pause_flag

  @property
  def results(self) -> list[UploadResult]:
    """Return accumulated upload results.

    :return: Upload results.
    """
    return self._results

  @property
  def username(self) -> str:
    """Return the account username bound to this worker.

    :return: Account username.
    """
    return self._username
