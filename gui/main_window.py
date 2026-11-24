from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
  QDialog,
  QMainWindow,
  QStackedWidget,
  QTabWidget,
  QVBoxLayout,
  QWidget,
)

from gui.dialogs import LogsDialog
from gui.pages import (
  AccountsPage,
  ConfigWizardPage,
  ExecutionWizardPage,
  FoldersPage,
  ReviewWizardPage,
  SettingsPage,
  TikTokStudioPage,
  VideosWizardPage,
)
from gui.theme.manager import ThemeManager
from gui.widgets.wizard_stepper import WizardStepperBar


class MainWindow(QMainWindow):
  """Main application window structured as a 5-step guided SaaS Wizard.

  Steps:
  0 - CONTA (AccountsPage)
  1 - VÍDEOS (VideosWizardPage)
  2 - CONFIGURAÇÃO (ConfigWizardPage)
  3 - REVISÃO (ReviewWizardPage)
  4 - PUBLICAÇÃO (ExecutionWizardPage)
  """

  WINDOW_TITLE = "TikTok Scheduler"

  _log_signal = pyqtSignal(str, int)
  wizard_step_changed = pyqtSignal(int)

  def __init__(
    self,
    theme_manager: ThemeManager,
    parent: QWidget | None = None,
  ) -> None:
    super().__init__(parent)
    self._theme_manager = theme_manager
    self._page_order: list[tuple[str, QWidget, str, str]] = []
    self._locked_normal_size: QSize | None = None
    self._restoring_locked_size = False
    self._log_file_path: Path | None = None
    self._session_logs: list[tuple[str, int]] = []
    self._logs_dialog: LogsDialog | None = None
    self._settings_dialog: QDialog | None = None
    self._log_signal.connect(self._do_append_log)

    self.setWindowTitle(self.WINDOW_TITLE)
    self._build_ui()
    self._expose_controller_aliases()
    self._bind_theme_controls()
    self.set_wizard_step(0)
    self._apply_theme_state()

  def _build_ui(self) -> None:
    central = QWidget()
    central.setObjectName("main-central")
    self.setCentralWidget(central)

    root_layout = QVBoxLayout(central)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    icon_color = self._theme_manager.palette.accent
    self.stepper_bar = WizardStepperBar(accent_color=icon_color, parent=central)
    root_layout.addWidget(self.stepper_bar)

    self.wizard_stack = QStackedWidget(central)
    root_layout.addWidget(self.wizard_stack, 1)

    # Hidden QTabWidget shim for any legacy code referencing self.tab_widget
    self.tab_widget = QTabWidget()
    self.tab_widget.hide()

    self._build_pages()

  def lock_normal_size(self, size: QSize) -> None:
    # Kept for backward compatibility; windows are freely resizable per desktop guidelines
    self._locked_normal_size = None

  def _build_pages(self) -> None:
    icon_color = self._theme_manager.palette.accent
    self.accounts_page = AccountsPage(icon_color)
    self.studio_page = TikTokStudioPage()
    self.executor_page = ExecutionWizardPage(icon_color, self._theme_manager.palette)

    # Auxiliary pages kept for backward compatibility and mixin references
    self.videos_page = VideosWizardPage(icon_color)
    self.config_page = ConfigWizardPage(icon_color)
    self.review_page = ReviewWizardPage(icon_color)
    self.folders_page = FoldersPage(icon_color)
    self.settings_page = SettingsPage(icon_color)

    self._register_wizard_page("accounts", self.accounts_page, AccountsPage.TITLE, AccountsPage.DESCRIPTION)
    self._register_wizard_page("studio", self.studio_page, "2. Estúdio TikTok", "Carregar e agendar publicações")
    self._register_wizard_page("main", self.executor_page, ExecutionWizardPage.TITLE, ExecutionWizardPage.DESCRIPTION)

  def _register_wizard_page(
    self,
    key: str,
    page: QWidget,
    title: str,
    description: str,
  ) -> None:
    self._page_order.append((key, page, title, description))
    self.wizard_stack.addWidget(page)

  def set_wizard_step(self, step_index: int) -> None:
    """Switch active wizard page (0..4) and update the top progress stepper."""
    if not (0 <= step_index < self.wizard_stack.count()):
      return
    self.wizard_stack.setCurrentIndex(step_index)
    _key, _page, title, _desc = self._page_order[step_index]

    # In Studio step, the TikTok Studio header & sidebar provide full navigation
    if _key == "studio":
      self.stepper_bar.setVisible(False)
    else:
      self.stepper_bar.setVisible(True)
      self.stepper_bar.set_current_step(step_index)

    self.setWindowTitle(f"{self.WINDOW_TITLE} — {title}")
    self.wizard_step_changed.emit(step_index)

  def current_wizard_step(self) -> int:
    return self.wizard_stack.currentIndex()

  def _set_current_page(self, key: str) -> None:
    for index, (page_key, _page, _title, _description) in enumerate(self._page_order):
      if page_key == key:
        self.set_wizard_step(index)
        break

  def _expose_controller_aliases(self) -> None:
    """Expose child widgets under stable attribute names for controllers and regression tests."""
    # Account controls (Page 1 & Page 5)
    self.account_dropdown = self.executor_page.account_dropdown
    self.random_account_btn = self.executor_page.random_account_btn
    self.add_account_btn = self.accounts_page.add_account_btn
    self.import_json_btn = getattr(self.accounts_page, "import_json_btn", self.add_account_btn)
    self.accounts_table = self.accounts_page.accounts_table
    self.accounts_edit_btn = self.accounts_page.accounts_edit_btn
    self.accounts_delete_btn = self.accounts_page.accounts_delete_btn
    self.accounts_random_btn = self.accounts_page.accounts_random_btn

    # Video / Folder controls (Page 2)
    self.folder_dropdown = self.videos_page.folder_dropdown
    self.browse_button = self.videos_page.browse_button
    self.scan_button = self.videos_page.scan_button
    self.file_count_label = self.executor_page.file_count_label
    self.folders_table = self.videos_page.folders_table
    self.add_folder_btn = self.videos_page.add_folder_btn

    # Schedule & Caption configuration controls (Page 3)
    self.caption_input = self.config_page.caption_input
    self.caption_preview = self.config_page.caption_preview
    self.prefix_caption_check = self.config_page.prefix_caption_check
    self.start_date = self.config_page.start_date
    self.end_date = self.config_page.end_date
    self.time_start_hour = self.config_page.time_start_hour
    self.time_start_minute = self.config_page.time_start_minute
    self.time_end_hour = self.config_page.time_end_hour
    self.time_end_minute = self.config_page.time_end_minute
    self.interval_spin = self.config_page.interval_spin
    self.limit_spin = self.config_page.limit_spin
    self.schedule_warning = self.config_page.schedule_warning
    self.time_warning = self.config_page.time_warning
    self.schedule_result_label = self.config_page.schedule_result_label
    self.generate_btn = self.config_page.generate_btn

    # Execution & Live Terminal controls (Page 5)
    self.headless_check = self.executor_page.headless_check
    self.retry_check = self.executor_page.retry_check
    self.start_btn = self.executor_page.start_btn
    self.stop_btn = self.executor_page.stop_btn
    self.pause_btn = self.executor_page.pause_btn
    self.resume_btn = self.executor_page.resume_btn
    self.export_btn = self.executor_page.export_btn
    self.progress_bar = self.executor_page.progress_bar
    self.progress_label = self.executor_page.progress_label
    self.success_label = self.executor_page.success_label
    self.failure_label = self.executor_page.failure_label

    self.video_total_label = self.executor_page.video_total_label
    self.video_selected_label = self.executor_page.video_selected_label
    self.filter_pending_check = self.executor_page.filter_pending_check
    self.filter_scheduled_check = self.executor_page.filter_scheduled_check
    self.filter_published_check = self.executor_page.filter_published_check
    self.filter_failed_check = self.executor_page.filter_failed_check
    self.video_table = self.executor_page.video_table
    self.video_library_table = None

    self.log_panel = self.executor_page.log_panel
    self.toggle_log_btn = self.executor_page.toggle_log_btn
    self.log_clear_button = self.executor_page.log_clear_button

    self.theme_mode_combo = self.settings_page.theme_mode_combo

  def _bind_theme_controls(self) -> None:
    self.theme_mode_combo.currentTextChanged.connect(self._on_theme_mode_changed)
    self.toggle_log_btn.clicked.connect(self._open_logs_dialog)
    self.stepper_bar.open_logs_requested.connect(self._open_logs_dialog)
    self.stepper_bar.open_settings_requested.connect(self._open_settings_dialog)
    self.log_clear_button.clicked.connect(self._clear_log)
    self._theme_manager.theme_changed.connect(lambda _mode: self._apply_theme_state())

  def set_log_file_path(self, log_file_path: Path) -> None:
    self._log_file_path = log_file_path

  def _open_logs_dialog(self) -> None:
    if self._logs_dialog is None:
      self._logs_dialog = LogsDialog(
        palette=self._theme_manager.palette,
        log_file_path=self._log_file_path,
        parent=self,
      )
      self._logs_dialog.set_entries(self._session_logs)
    self._logs_dialog.show()
    self._logs_dialog.raise_()
    self._logs_dialog.activateWindow()

  def _open_settings_dialog(self) -> None:
    if self._settings_dialog is None:
      self._settings_dialog = QDialog(self)
      self._settings_dialog.setWindowTitle("TikTok Scheduler — Configurações de Tema")
      self._settings_dialog.resize(520, 420)
      lay = QVBoxLayout(self._settings_dialog)
      lay.setContentsMargins(0, 0, 0, 0)
      lay.addWidget(self.settings_page)
    self._settings_dialog.show()
    self._settings_dialog.raise_()
    self._settings_dialog.activateWindow()

  def _on_theme_mode_changed(self, mode_text: str) -> None:
    self._theme_manager.apply_theme(mode_text.lower())

  def _apply_theme_state(self) -> None:
    palette = self._theme_manager.palette
    self.executor_page.set_palette_data(palette)
    if self._logs_dialog is not None:
      self._logs_dialog.set_palette_data(palette)
    self._sync_theme_combo()

  def _sync_theme_combo(self) -> None:
    label = self._theme_manager.theme_label()
    self.theme_mode_combo.blockSignals(True)
    index = self.theme_mode_combo.findText(label)
    if index >= 0:
      self.theme_mode_combo.setCurrentIndex(index)
    self.theme_mode_combo.blockSignals(False)

  def _clear_log(self) -> None:
    self.log_panel.clear()

  def append_log(self, message: str, level: int = 20) -> None:
    self._log_signal.emit(message, level)

  def _do_append_log(self, message: str, level: int) -> None:
    self._session_logs.append((message, level))
    self.log_panel.append_message(message, level)
    if self._logs_dialog is not None:
      self._logs_dialog.append_entry(message, level)

  def update_progress(
    self,
    current: int,
    total: int,
    success: int,
    failed: int,
  ) -> None:
    progress = int((current / total) * 100) if total > 0 else 0
    self.progress_bar.setValue(progress)
    self.progress_label.setText(f"{progress}%")
    self.success_label.setText(f"Success {success}")
    self.failure_label.setText(f"Failed {failed}")

  def set_upload_running(self, running: bool) -> None:
    self.start_btn.setEnabled(not running)
    self.stop_btn.setEnabled(running)
    self.pause_btn.setEnabled(running)
    self.resume_btn.setEnabled(False)
    self.generate_btn.setEnabled(not running)
    self.folder_dropdown.setEnabled(not running)
    self.browse_button.setEnabled(not running)
    self.scan_button.setEnabled(not running)
    self.account_dropdown.setEnabled(not running)
    self.random_account_btn.setEnabled(not running)
    self.add_account_btn.setEnabled(not running)
    if hasattr(self, "import_json_btn"):
      self.import_json_btn.setEnabled(not running)
    self.accounts_edit_btn.setEnabled(not running)
    self.accounts_delete_btn.setEnabled(not running)
    self.accounts_random_btn.setEnabled(not running)

  def _set_widget_error_state(self, widget: QWidget, enabled: bool) -> None:
    widget.setProperty("state", "error" if enabled else "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)

  def show_schedule_warning(self, message: str) -> None:
    self.schedule_warning.setText(message)
    self.schedule_warning.show()
    self._set_widget_error_state(self.start_date, True)
    self._set_widget_error_state(self.end_date, True)

  def clear_schedule_warning(self) -> None:
    self.schedule_warning.clear()
    self.schedule_warning.hide()
    self._set_widget_error_state(self.start_date, False)
    self._set_widget_error_state(self.end_date, False)

  def show_time_warning(self, message: str) -> None:
    self.time_warning.setText(message)
    self.time_warning.show()

  def clear_time_warning(self) -> None:
    self.time_warning.clear()
    self.time_warning.hide()

  def set_actions_enabled(self, enabled: bool, has_tasks: bool = False) -> None:
    self.generate_btn.setEnabled(enabled)
    if not enabled and not has_tasks:
      self.start_btn.setEnabled(False)
    elif has_tasks:
      self.start_btn.setEnabled(True)
