from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QTableWidgetItem

from gui.controllers.upload_worker import UploadWorker
from gui.tables.video_table import build_status_badge
from utils.datetime_utils import DateTimeUtils


class UploadExecutionControllerMixin:
  """Handle log forwarding, upload execution, and report export."""

  def _on_log_message(self, message: str, level: int) -> None:
    """Forward logger output to the GUI log panels.

    :param message: Formatted log message.
    :param level: Numeric log level.
    :return: None
    """
    self._window.append_log(message, level)

  def _on_start_upload(self) -> None:
    """Launch the background upload worker.

    :return: None
    """
    if not self._tasks:
      self._logger.warning("No tasks to upload. Generate a schedule first.")
      return

    username = self._window.account_dropdown.currentText()
    if not username:
      self._logger.error("No account selected")
      return

    self._window.set_upload_running(True)
    self._window.update_progress(0, len(self._tasks), 0, 0)

    self._worker = UploadWorker(
      cookie_manager=self._cookie_manager,
      username=username,
      tasks=self._tasks,
      headless=self._window.headless_check.isChecked(),
      retry_enabled=self._window.retry_check.isChecked(),
      logger=self._logger,
      rule_engine=self._rules,
      storage_dir=self._storage_dir,
      process_limit=self._window.limit_spin.value(),
    )
    self._worker.progress_update.connect(self._on_progress_update)
    self._worker.upload_complete.connect(self._on_upload_complete)
    self._worker.finished_all.connect(self._on_finished)
    self._worker.error_occurred.connect(self._on_worker_error)
    self._worker.rate_limited.connect(self._on_rate_limited)
    self._worker.start()
    self._logger.info("Upload started")

  def _on_stop_clicked(self) -> None:
    """Signal the worker to stop after the current upload.

    :return: None
    """
    if self._worker:
      self._worker.request_stop()
      self._logger.warning("Stop requested - finishing current upload")

  def _on_pause_resume(self) -> None:
    """Toggle upload pause and resume state.

    :return: None
    """
    if not self._worker:
      return

    self._worker.toggle_pause()
    if self._worker.is_paused:
      self._window.pause_btn.setText(" Resume")
      self._logger.info("Upload paused")
    else:
      self._window.pause_btn.setText(" Pause")
      self._logger.info("Upload resumed")

  def _on_progress_update(
    self,
    current: int,
    total: int,
    success: int,
    failed: int,
  ) -> None:
    """Update progress widgets.

    :param current: Completed uploads.
    :param total: Total uploads.
    :param success: Successful uploads.
    :param failed: Failed uploads.
    :return: None
    """
    self._window.update_progress(current, total, success, failed)

  def _on_upload_complete(self, success: bool, filename: str) -> None:
    """Persist upload results and update table status cells.

    :param success: Whether the upload succeeded.
    :param filename: Uploaded filename.
    :return: None
    """
    if self._worker:
      username = self._window.account_dropdown.currentText()
      scheduled_data = self._storage_service.load_scheduled(username)
      results = self._worker.results
      if results:
        last_result = results[-1]
        for task in self._tasks:
          if task.file_path.name == filename:
            self._storage_service.append_upload_record(
              scheduled_data,
              task,
              last_result,
            )
            self._storage_service.save_scheduled(username, scheduled_data)
            self._cached_data_uploads = self._storage_service.get_user_uploads(
              scheduled_data
            )
            break

    status_text = "Scheduled" if success else "Failed"
    if success:
      self._scheduled_basenames.add(filename)
      if filename in self._failed_basenames:
        self._failed_basenames.remove(filename)
    else:
      self._failed_basenames.add(filename)

    tables = [self._window.video_table]
    mirror_table = getattr(self._window, "video_library_table", None)
    if mirror_table is not None:
      tables.append(mirror_table)

    for table in tables:
      for row in range(table.rowCount()):
        filename_item = table.item(row, 1)
        if filename_item is None or filename_item.text() != filename:
          continue
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 5, status_item)
        table.setCellWidget(row, 5, build_status_badge(status_text))
        break

    self._refresh_video_table()

  def _on_finished(self) -> None:
    """Handle worker completion.

    :return: None
    """
    self._window.set_upload_running(False)
    self._window.pause_btn.setText(" Pause")
    self._logger.success("All uploads finished")

  def _on_worker_error(self, error: str) -> None:
    """Handle a fatal worker error.

    :param error: Error message.
    :return: None
    """
    self._window.set_upload_running(False)
    self._logger.error(f"Worker error: {error}")

  def _on_rate_limited(self, toast_message: str) -> None:
    """Handle account rate limit detection.

    :param toast_message: TikTok toast text.
    :return: None
    """
    self._window.set_upload_running(False)
    self._window.show_schedule_warning(f"Account rate limited: {toast_message}")
    self._window.set_actions_enabled(False)
    self._logger.error(
      f"RATE LIMIT - All uploads stopped. TikTok message: {toast_message}"
    )

  def _on_export_report(self) -> None:
    """Export upload results to a text report.

    :return: None
    """
    if not self._worker or not self._worker.results:
      self._logger.warning("No results to export")
      return

    file_path, _ = QFileDialog.getSaveFileName(
      self._window,
      "Export Report",
      "upload_report.txt",
      "Text Files (*.txt);;All Files (*)",
    )
    if not file_path:
      return

    try:
      with open(file_path, "w", encoding="utf-8") as file_obj:
        file_obj.write("TikTok Upload Report\n")
        file_obj.write(f"Generated: {datetime.now().isoformat()}\n")
        file_obj.write("=" * 50 + "\n\n")
        for result in self._worker.results:
          status = "SUCCESS" if result.success else "FAILED"
          file_obj.write(f"[{status}] {result.file_path.name}\n")
          file_obj.write(f"  Message: {result.message}\n")
          file_obj.write(
            f"  Time: {DateTimeUtils.format_for_display(result.timestamp)}\n"
          )
          if result.error:
            file_obj.write(f"  Error: {result.error}\n")
          file_obj.write("\n")
      self._logger.success(f"Report exported to {file_path}")
    except OSError as exc:
      self._logger.error(f"Failed to export report: {exc}")
