from __future__ import annotations

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget

from gui.pages import AccountsPage, ExecutorPage, FoldersPage, SettingsPage
from gui.theme.manager import ThemeManager


class MainWindow(QMainWindow):
  """Main application window with top-aligned tabs.

  :param theme_manager: Shared theme manager.
  :param parent: Parent widget.
  :return: None
  """

  WINDOW_TITLE = "TikTok Scheduler"

  _log_signal = pyqtSignal(str, int)

  def __init__(
    self,
    theme_manager: ThemeManager,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the main window.

    :param theme_manager: Shared theme manager.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self._theme_manager = theme_manager
    self._page_order: list[tuple[str, QWidget, str, str]] = []
    self._locked_normal_size: QSize | None = None
    self._restoring_locked_size = False
    self._log_signal.connect(self._do_append_log)

    self.setWindowTitle(self.WINDOW_TITLE)
    self._build_ui()
    self._expose_controller_aliases()
    self._bind_theme_controls()
    self._set_current_page("main")
    self._apply_theme_state()

  def _build_ui(self) -> None:
    """Build the tab-based application shell.

    :return: None
    """
    central = QWidget()
    central.setObjectName("main-central")
    self.setCentralWidget(central)

    root_layout = QVBoxLayout(central)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    self.tab_widget = QTabWidget()
    self.tab_widget.setProperty("class", "workspace-tabs")
    self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
    self.tab_widget.setDocumentMode(False)
    self.tab_widget.setMovable(False)
    self.tab_widget.setUsesScrollButtons(True)
    self.tab_widget.tabBar().setExpanding(False)
    self.tab_widget.currentChanged.connect(self._on_tab_changed)
    root_layout.addWidget(self.tab_widget, 1)

    self._build_pages()

  def lock_normal_size(self, size: QSize) -> None:
    """Lock the normal window size while still allowing maximize/fullscreen.

    :param size: Normal window size.
    :return: None
    """
    self._locked_normal_size = QSize(size)

  def resizeEvent(self, event) -> None:  # noqa: N802
    """Prevent manual resizing in the normal window state.

    :param event: Resize event.
    :return: None
    """
    super().resizeEvent(event)
    if self._restoring_locked_size:
      return
    if self._locked_normal_size is None:
      return
    if self.isMaximized() or self.isFullScreen():
      return
    if event.size() == self._locked_normal_size:
      return

    self._restoring_locked_size = True
    self.resize(self._locked_normal_size)
    self._restoring_locked_size = False

  def _build_pages(self) -> None:
    """Create page widgets and register top tabs.

    :return: None
    """
    icon_color = self._theme_manager.palette.accent
    self.executor_page = ExecutorPage(icon_color, self._theme_manager.palette)
    self.accounts_page = AccountsPage(icon_color)
    self.folders_page = FoldersPage(icon_color)
    self.settings_page = SettingsPage(icon_color)

    self._register_page("main", self.executor_page, ExecutorPage.TITLE, ExecutorPage.DESCRIPTION, "Main")
    self._register_page("accounts", self.accounts_page, AccountsPage.TITLE, AccountsPage.DESCRIPTION, "Accounts")
    self._register_page("folders", self.folders_page, FoldersPage.TITLE, FoldersPage.DESCRIPTION, "Folders")
    self._register_page("settings", self.settings_page, SettingsPage.TITLE, SettingsPage.DESCRIPTION, "Settings")

  def _register_page(
    self,
    key: str,
    page: QWidget,
    title: str,
    description: str,
    tab_label: str,
  ) -> None:
    """Register a page with the top tab widget.

    :param key: Stable page key.
    :param page: Page widget.
    :param title: Page title.
    :param description: Page description.
    :param tab_label: Visible tab label.
    :return: None
    """
    self._page_order.append((key, page, title, description))
    self.tab_widget.addTab(page, tab_label)

  def _expose_controller_aliases(self) -> None:
    """Expose child widgets under stable attribute names for controllers.

    :return: None
    """
    self.account_dropdown = self.executor_page.account_dropdown
    self.random_account_btn = self.executor_page.random_account_btn
    self.add_account_btn = self.accounts_page.add_account_btn
    self.accounts_table = self.accounts_page.accounts_table
    self.accounts_edit_btn = self.accounts_page.accounts_edit_btn
    self.accounts_delete_btn = self.accounts_page.accounts_delete_btn
    self.accounts_random_btn = self.accounts_page.accounts_random_btn

    self.folder_dropdown = self.executor_page.folder_dropdown
    self.browse_button = self.executor_page.browse_button
    self.scan_button = self.executor_page.scan_button
    self.file_count_label = self.executor_page.file_count_label
    self.folders_table = self.folders_page.folders_table
    self.add_folder_btn = self.folders_page.add_folder_btn

    self.caption_input = self.executor_page.caption_input
    self.caption_preview = self.executor_page.caption_preview
    self.headless_check = self.executor_page.headless_check
    self.retry_check = self.executor_page.retry_check
    self.start_btn = self.executor_page.start_btn
    self.stop_btn = self.executor_page.stop_btn
    self.pause_btn = self.executor_page.pause_btn
    self.export_btn = self.executor_page.export_btn
    self.generate_btn = self.executor_page.generate_btn
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

    self.start_date = self.executor_page.start_date
    self.end_date = self.executor_page.end_date
    self.time_start_hour = self.executor_page.time_start_hour
    self.time_start_minute = self.executor_page.time_start_minute
    self.time_end_hour = self.executor_page.time_end_hour
    self.time_end_minute = self.executor_page.time_end_minute
    self.interval_spin = self.executor_page.interval_spin
    self.limit_spin = self.executor_page.limit_spin
    self.schedule_warning = self.executor_page.schedule_warning
    self.time_warning = self.executor_page.time_warning
    self.schedule_result_label = self.executor_page.schedule_result_label

    self.theme_mode_combo = self.settings_page.theme_mode_combo

  def _bind_theme_controls(self) -> None:
    """Connect theme and log related controls.

    :return: None
    """
    self.theme_mode_combo.currentTextChanged.connect(self._on_theme_mode_changed)
    self.toggle_log_btn.clicked.connect(self._focus_terminal_log)
    self.log_clear_button.clicked.connect(self._clear_log)
    self._theme_manager.theme_changed.connect(lambda _mode: self._apply_theme_state())

  def _on_theme_mode_changed(self, mode_text: str) -> None:
    """Apply the theme selected on the settings page.

    :param mode_text: Selected theme label.
    :return: None
    """
    self._theme_manager.apply_theme(mode_text.lower())

  def _apply_theme_state(self) -> None:
    """Refresh widgets that depend on the active theme.

    :return: None
    """
    palette = self._theme_manager.palette
    self.executor_page.set_palette_data(palette)
    self._sync_theme_combo()

  def _sync_theme_combo(self) -> None:
    """Synchronize the settings combo with the active theme.

    :return: None
    """
    label = self._theme_manager.theme_label()
    self.theme_mode_combo.blockSignals(True)
    index = self.theme_mode_combo.findText(label)
    if index >= 0:
      self.theme_mode_combo.setCurrentIndex(index)
    self.theme_mode_combo.blockSignals(False)

  def _set_current_page(self, key: str) -> None:
    """Switch the visible top tab.

    :param key: Page key.
    :return: None
    """
    for index, (page_key, _page, _title, _description) in enumerate(self._page_order):
      if page_key == key:
        self.tab_widget.setCurrentIndex(index)
        break

  def _on_tab_changed(self, index: int) -> None:
    """Handle top-tab changes.

    :param index: Active tab index.
    :return: None
    """
    if 0 <= index < len(self._page_order):
      _key, _page, title, description = self._page_order[index]
      self.setWindowTitle(title if description else self.WINDOW_TITLE)

  def _clear_log(self) -> None:
    """Clear both visible log views.

    :return: None
    """
    self.log_panel.clear()

  def _focus_terminal_log(self) -> None:
    """Focus the terminal log and scroll to the latest entry.

    :return: None
    """
    self.log_panel.setFocus()
    self.log_panel.moveCursor(QTextCursor.MoveOperation.End)

  def append_log(self, message: str, level: int = 20) -> None:
    """Append a log message from any thread.

    :param message: Formatted log line.
    :param level: Numeric log level.
    :return: None
    """
    self._log_signal.emit(message, level)

  def _do_append_log(self, message: str, level: int) -> None:
    """Append a log message on the GUI thread.

    :param message: Formatted log line.
    :param level: Numeric log level.
    :return: None
    """
    self.log_panel.append_message(message, level)

  def update_progress(
    self,
    current: int,
    total: int,
    success: int,
    failed: int,
  ) -> None:
    """Update progress widgets in the Main tab.

    :param current: Completed uploads.
    :param total: Total uploads.
    :param success: Successful uploads.
    :param failed: Failed uploads.
    :return: None
    """
    progress = int((current / total) * 100) if total > 0 else 0
    self.progress_bar.setValue(progress)
    self.progress_label.setText(f"{progress}%")
    self.success_label.setText(f"Success {success}")
    self.failure_label.setText(f"Failed {failed}")

  def set_upload_running(self, running: bool) -> None:
    """Toggle the UI between running and idle states.

    :param running: Whether an upload is currently running.
    :return: None
    """
    self.start_btn.setEnabled(not running)
    self.stop_btn.setEnabled(running)
    self.pause_btn.setEnabled(running)
    self.generate_btn.setEnabled(not running)
    self.folder_dropdown.setEnabled(not running)
    self.browse_button.setEnabled(not running)
    self.scan_button.setEnabled(not running)
    self.account_dropdown.setEnabled(not running)
    self.random_account_btn.setEnabled(not running)

  def _set_widget_error_state(self, widget: QWidget, enabled: bool) -> None:
    """Toggle error styling on a widget.

    :param widget: Target widget.
    :param enabled: Whether the error state is active.
    :return: None
    """
    widget.setProperty("state", "error" if enabled else "")
    widget.style().unpolish(widget)
    widget.style().polish(widget)

  def show_schedule_warning(self, message: str) -> None:
    """Display an inline schedule warning.

    :param message: Warning message.
    :return: None
    """
    self.schedule_warning.setText(message)
    self.schedule_warning.show()
    self._set_widget_error_state(self.start_date, True)
    self._set_widget_error_state(self.end_date, True)

  def clear_schedule_warning(self) -> None:
    """Hide the schedule warning.

    :return: None
    """
    self.schedule_warning.clear()
    self.schedule_warning.hide()
    self._set_widget_error_state(self.start_date, False)
    self._set_widget_error_state(self.end_date, False)

  def show_time_warning(self, message: str) -> None:
    """Display an inline time warning.

    :param message: Warning message.
    :return: None
    """
    self.time_warning.setText(message)
    self.time_warning.show()

  def clear_time_warning(self) -> None:
    """Hide the time warning.

    :return: None
    """
    self.time_warning.clear()
    self.time_warning.hide()

  def set_actions_enabled(self, enabled: bool) -> None:
    """Enable or disable scheduling actions.

    :param enabled: Whether actions should be enabled.
    :return: None
    """
    self.generate_btn.setEnabled(enabled)
    if not enabled:
      self.start_btn.setEnabled(False)
