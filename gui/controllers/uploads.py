from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QTableWidgetItem

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
    if self._worker is not None and self._worker.isRunning():
      self._logger.warning("An upload execution is already running.")
      return

    if not self._tasks:
      self._logger.warning("No tasks to upload. Generate a schedule first.")
      return

    # Filter out tasks that were already completed or marked unknown in a previous run
    remaining_tasks = [
      t
      for t in self._tasks
      if t.file_path.name not in self._scheduled_basenames
      and t.file_path.name not in getattr(self, "_unknown_basenames", set())
    ]
    if not remaining_tasks:
      self._logger.warning(
        "All generated tasks in the queue have already been processed. Generate a new schedule."
      )
      self._window.start_btn.setEnabled(False)
      return

    self._tasks = remaining_tasks

    # Phase 2.5: Queue Pre-Validation before browser launch
    queue_inspection = self._rules.inspect_queue(self._tasks)
    if not queue_inspection["is_valid"]:
      self._logger.warning(
        f"Queue schedule validation failed: {len(queue_inspection['issues'])} issue(s) detected. "
        "Recalculating safe sequential schedule..."
      )
      recalculated = self._rules.recalculate_schedule_queue(
        self._tasks,
        interval_minutes=30,
      )

      # If interactive GUI, prompt user for approval
      app = QApplication.instance()
      if app is not None and getattr(self._window, "isVisible", lambda: True)():
        from gui.dialogs.studio_dialogs import ScheduleApprovalDialog
        dlg = ScheduleApprovalDialog(recalculated, parent=self._window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
          self._logger.info("Execução cancelada pelo usuário para revisão de horários.")
          return

      # Apply approved schedule
      self._apply_recalculated_schedule(recalculated)

    username = self._window.account_dropdown.currentText()
    if not username:
      self._logger.error("No account selected")
      return

    self._window.set_upload_running(True)
    self._window.update_progress(0, len(self._tasks), 0, 0)

    self._worker = UploadWorker(
      cookie_manager=self._cookie_manager,
      username=username,
      tasks=list(self._tasks),
      headless=self._window.headless_check.isChecked(),
      retry_enabled=self._window.retry_check.isChecked(),
      logger=self._logger,
      rule_engine=self._rules,
      storage_dir=self._storage_dir,
      process_limit=self._window.limit_spin.value(),
    )
    self._worker.progress_update.connect(self._on_progress_update)
    if hasattr(self._worker, "upload_started"):
      self._worker.upload_started.connect(self._on_upload_started)
    self._worker.upload_complete.connect(self._on_upload_complete)
    self._worker.finished_all.connect(self._on_finished)
    self._worker.error_occurred.connect(self._on_worker_error)
    self._worker.rate_limited.connect(self._on_rate_limited)
    self._worker.start()
    self._logger.info(
      f"Upload execution started for @{username} ({len(self._tasks)} task(s) in queue, "
      f"headless={self._window.headless_check.isChecked()})"
    )

  def _apply_recalculated_schedule(self, recalculated: list[dict[str, Any]]) -> None:
    """
    Apply approved recalculated schedule times to tasks, controller state, UI and storage.
    """
    history_records = []
    username = self._window.account_dropdown.currentText() or "default"

    for item in recalculated:
      task = item.get("task")
      new_dt = item.get("new_schedule")
      old_dt = item.get("old_schedule")
      fn = item.get("filename")

      if task is not None:
        task.schedule_time = new_dt

      if hasattr(self, "_studio_schedules") and fn:
        self._studio_schedules[fn] = new_dt

      history_records.append({
        "account": username,
        "filename": fn,
        "old_schedule": DateTimeUtils.format_iso(old_dt) if old_dt else None,
        "new_schedule": DateTimeUtils.format_iso(new_dt) if new_dt else None,
        "reason": item.get("reason", "Ajustado sequencialmente"),
        "timestamp": datetime.now().isoformat(),
      })

    # Update UI tables
    if hasattr(self, "_update_table_schedule"):
      self._update_table_schedule()

    # Update planned_tasks in wizard-state.json and storage
    if hasattr(self, "_save_wizard_state"):
      self._save_wizard_state()

    # Append to schedule change history (without deleting previous history)
    try:
      history_file = Path(self._storage_dir) / "schedule_history.json"
      existing_history = []
      if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
          existing_history = json.load(f)
      existing_history.extend(history_records)
      with open(history_file, "w", encoding="utf-8") as f:
        json.dump(existing_history, f, indent=2, ensure_ascii=False)
    except Exception as e:
      self._logger.debug(f"Error persisting schedule history: {e}")

    self._logger.success(f"Horários da fila recalculados e sincronizados com sucesso ({len(recalculated)} itens).")

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
      if hasattr(self._window, "resume_btn"):
        self._window.pause_btn.setEnabled(False)
        self._window.resume_btn.setEnabled(True)
      self._set_active_row_status("Paused")
      self._logger.info("Upload paused")
    else:
      self._window.pause_btn.setText(" Pause")
      if hasattr(self._window, "resume_btn"):
        self._window.pause_btn.setEnabled(True)
        self._window.resume_btn.setEnabled(False)
      self._set_active_row_status("Processing")
      self._logger.info("Upload resumed")

    if hasattr(self._window, "studio_page"):
      self._window.studio_page.update_live_upload(
        current=0,
        total=len(self._tasks),
        status_text="Envio pausado" if self._worker.is_paused else "Envio retomado",
        is_running=True,
        is_paused=self._worker.is_paused,
      )

  def _on_resume_clicked(self) -> None:
    """Explicitly resume a paused worker."""
    if self._worker and self._worker.is_paused:
      self._on_pause_resume()

  def _on_upload_started(self, filename: str) -> None:
    """Mark the currently executing video row as 'Processing'."""
    self._current_processing_filename = filename
    self._set_row_status_by_filename(filename, "Processing")
    if hasattr(self._window, "studio_page"):
      tot = max(1, len(self._tasks) + len(self._scheduled_basenames) + len(self._failed_basenames))
      done = len(self._scheduled_basenames) + len(self._failed_basenames)
      pct = int((done / tot) * 100)
      self._window.studio_page.update_live_upload(
        current=done + 1,
        total=tot,
        status_text=f"Enviando '{filename}'...",
        filename=filename,
        percent=pct,
        is_running=True,
      )
      if hasattr(self, "_refresh_studio_publications"):
        self._refresh_studio_publications()

  def _set_active_row_status(self, status_text: str) -> None:
    """Update status badge for the currently active video row."""
    active_file = getattr(self, "_current_processing_filename", "")
    if active_file:
      self._set_row_status_by_filename(active_file, status_text)

  def _set_row_status_by_filename(self, filename: str, status_text: str) -> None:
    """Set status text and badge for a specific filename in the queue table."""
    table = self._window.video_table
    for row in range(table.rowCount()):
      item = table.item(row, 1)
      if item is not None and item.text() == filename:
        status_item = QTableWidgetItem(status_text)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 5, status_item)
        table.setCellWidget(row, 5, build_status_badge(status_text))
        break
    if hasattr(self, "_update_execution_metrics"):
      self._update_execution_metrics()

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
    if hasattr(self._window, "studio_page"):
      pct = int((current / total) * 100) if total else 0
      self._window.studio_page.update_live_upload(
        current=current,
        total=total,
        status_text=f"{success} com sucesso · {failed} com falha",
        percent=pct,
        is_running=True,
      )

  def _on_upload_complete(self, success: bool, filename: str) -> None:
    """Persist upload results and update table status cells.

    :param success: Whether the upload succeeded.
    :param filename: Uploaded filename.
    :return: None
    """
    last_result = None
    if self._worker:
      username = getattr(self._worker, "username", None) or getattr(
        self._worker, "_username", None
      ) or self._window.account_dropdown.currentText()
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
            if username == self._window.account_dropdown.currentText():
              self._cached_data_uploads = self._storage_service.get_user_uploads(
                scheduled_data
              )
            break

    outcome = getattr(last_result, "outcome", "") if last_result else ""
    if outcome == "unknown":
      status_text = "Unknown"
      self._unknown_basenames.add(filename)
      self._scheduled_basenames.discard(filename)
      self._failed_basenames.discard(filename)
    elif success:
      is_sched = getattr(last_result, "is_scheduled", False) or getattr(last_result, "status", "") == "scheduled"
      status_text = "Scheduled" if is_sched else "Published"
      self._scheduled_basenames.add(filename)
      self._failed_basenames.discard(filename)
      self._unknown_basenames.discard(filename)
    else:
      status_text = "Failed"
      self._failed_basenames.add(filename)
      self._scheduled_basenames.discard(filename)
      self._unknown_basenames.discard(filename)

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
    self._update_table_schedule()
    if hasattr(self, "_refresh_studio_publications"):
      self._refresh_studio_publications()
    if hasattr(self, "_save_wizard_state"):
      self._save_wizard_state()

  def _on_finished(self) -> None:
    """Handle worker completion.

    :return: None
    """
    was_stopped = bool(self._worker and getattr(self._worker, "_stop_flag", False))
    self._current_processing_filename = ""
    # Remove processed, failed, and unknown tasks so failed tasks are not masked as pending
    self._tasks = [
      t
      for t in self._tasks
      if t.file_path.name not in self._scheduled_basenames
      and t.file_path.name not in getattr(self, "_unknown_basenames", set())
      and t.file_path.name not in self._failed_basenames
    ]
    self._window.set_upload_running(False)
    self._window.start_btn.setEnabled(len(self._tasks) > 0)
    self._window.pause_btn.setText(" Pause")
    if hasattr(self._window, "resume_btn"):
      self._window.resume_btn.setEnabled(False)
    self._refresh_video_table()
    self._update_table_schedule()
    if hasattr(self._window, "studio_page"):
      total_completed = len(self._scheduled_basenames) + len(self._failed_basenames) + len(getattr(self, "_unknown_basenames", set()))
      self._window.studio_page.update_live_upload(
        current=total_completed,
        total=total_completed,
        status_text="Envio de publicações finalizado",
        percent=100,
        is_running=False,
        scheduled_count=len(self._scheduled_basenames),
        published_count=0,
        failed_count=len(self._failed_basenames),
        unknown_count=len(getattr(self, "_unknown_basenames", set())),
      )
    if hasattr(self, "_refresh_studio_publications"):
      self._refresh_studio_publications()
    if hasattr(self, "_save_wizard_state"):
      self._save_wizard_state()
    if was_stopped:
      self._logger.warning(
        f"Execution stopped by user. {len(self._tasks)} pending task(s) preserved in queue."
      )
    else:
      self._logger.success("All uploads finished")

  def _on_worker_error(self, error: str) -> None:
    """Handle a fatal worker error.

    :param error: Error message.
    :return: None
    """
    self._window.set_upload_running(False)
    self._logger.error(f"Worker error: {error}")
    if hasattr(self._window, "studio_page"):
      self._window.studio_page.update_live_upload(
        current=0,
        total=0,
        status_text=f"Erro no envio: {error}",
        percent=0,
        is_running=False,
      )
    if hasattr(self, "_refresh_studio_publications"):
      self._refresh_studio_publications()

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
