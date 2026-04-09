from __future__ import annotations

from PyQt6.QtCore import QDate, QPoint, Qt
from PyQt6.QtWidgets import (
  QCalendarWidget,
  QCheckBox,
  QComboBox,
  QDateEdit,
  QDialog,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QPushButton,
  QSizePolicy,
  QSpinBox,
  QVBoxLayout,
  QWidget,
)

from gui.layouts.page_layout import PageLayout
from gui.tables.video_table import VideoTable
from gui.theme.palette import ThemePalette
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon
from gui.widgets.mac_terminal import MacTerminalPanel
from gui.widgets.tag_editor import HashtagTextEdit


class PickerDateEdit(QDateEdit):
  """Date edit that opens a popup calendar when clicked.

  :param parent: Parent widget.
  :return: None
  """

  def __init__(self, parent: QWidget | None = None) -> None:
    """Initialize the picker.

    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setCalendarPopup(False)
    self.setReadOnly(True)

  def mousePressEvent(self, event) -> None:  # noqa: N802
    """Open the calendar popup after a mouse press.

    :param event: Mouse event.
    :return: None
    """
    super().mousePressEvent(event)
    self._show_calendar_popup()

  def _show_calendar_popup(self) -> None:
    """Show a popup calendar below the field.

    :return: None
    """
    popup = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
    popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    layout = QVBoxLayout(popup)
    layout.setContentsMargins(0, 0, 0, 0)

    calendar = QCalendarWidget(popup)
    calendar.setSelectedDate(self.date())
    calendar.clicked.connect(lambda date: self._apply_popup_date(date, popup))
    layout.addWidget(calendar)

    popup.move(self.mapToGlobal(QPoint(0, self.height() + 2)))
    popup.show()

  def _apply_popup_date(self, date: QDate, popup: QDialog) -> None:
    """Apply a selected date from the popup calendar.

    :param date: Selected date.
    :param popup: Popup dialog.
    :return: None
    """
    self.setDate(date)
    popup.close()


class ExecutorPage(PageLayout):
  """Primary main tab with grouped controls, queue, and terminal.

  :param icon_color: Accent color used for icons.
  :param palette: Active theme palette.
  :return: None
  """

  TITLE = "Main"
  DESCRIPTION = ""

  def __init__(self, icon_color: str, palette: ThemePalette) -> None:
    """Initialize the main page.

    :param icon_color: Accent color used for icons.
    :param palette: Active theme palette.
    :return: None
    """
    super().__init__()
    self._icon_color = icon_color
    self._palette = palette
    self._control_width = 320
    self._build_ui()

  def _build_ui(self) -> None:
    """Build the main workflow layout.

    :return: None
    """
    self.content_layout.setSpacing(16)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(14)

    controls_card = SurfaceCard()
    controls_layout = QVBoxLayout(controls_card)
    controls_layout.setContentsMargins(18, 18, 18, 18)
    controls_layout.setSpacing(8)
    controls_layout.addWidget(self._section_title("Username section"))

    controls_layout.addWidget(self._field_label("Username"))
    account_row = QHBoxLayout()
    account_row.setContentsMargins(0, 0, 0, 0)
    account_row.setSpacing(8)
    self.account_dropdown = QComboBox()
    self.account_dropdown.setFixedWidth(self._control_width)
    self.account_dropdown.setSizePolicy(
      QSizePolicy.Policy.Fixed,
      QSizePolicy.Policy.Fixed,
    )
    account_row.addWidget(self.account_dropdown)

    self.random_account_btn = QPushButton()
    self.random_account_btn.setProperty("class", "icon-button")
    self.random_account_btn.setToolTip("Random select username")
    self.random_account_btn.setIcon(build_icon("fa5s.random", self._icon_color))
    account_row.addWidget(self.random_account_btn)
    account_row.addStretch(1)
    controls_layout.addLayout(account_row)

    controls_layout.addWidget(self._field_label("Folder selection"))
    folder_row = QHBoxLayout()
    folder_row.setContentsMargins(0, 0, 0, 0)
    folder_row.setSpacing(8)
    self.folder_dropdown = QComboBox()
    self.folder_dropdown.setFixedWidth(self._control_width)
    self.folder_dropdown.setSizePolicy(
      QSizePolicy.Policy.Fixed,
      QSizePolicy.Policy.Fixed,
    )
    folder_row.addWidget(self.folder_dropdown)

    self.browse_button = QPushButton()
    self.browse_button.setProperty("class", "icon-button")
    self.browse_button.setToolTip("Choose folder")
    self.browse_button.setIcon(build_icon("fa5s.folder-open", self._icon_color))
    folder_row.addWidget(self.browse_button)

    self.scan_button = QPushButton()
    self.scan_button.setProperty("class", "icon-button")
    self.scan_button.setToolTip("Scan folder")
    self.scan_button.setIcon(build_icon("fa5s.search", self._icon_color))
    folder_row.addWidget(self.scan_button)
    folder_row.addStretch(1)
    controls_layout.addLayout(folder_row)

    self.file_count_label = QLabel("")
    self.file_count_label.hide()

    controls_layout.addWidget(self._field_label("Caption"))
    self.caption_input = HashtagTextEdit()
    self.caption_input.setPlaceholderText(
      "Write the caption and type # to get tag suggestions."
    )
    self.caption_input.setFixedWidth(440)
    self.caption_input.setMinimumHeight(120)
    self.caption_input.setMaximumHeight(120)
    controls_layout.addWidget(self.caption_input)

    self.caption_preview = QLabel("Preview: Cre: <videoid>")
    self.caption_preview.setProperty("class", "muted")
    self.caption_preview.setWordWrap(True)
    self.caption_preview.setMaximumWidth(self._control_width)
    controls_layout.addWidget(self.caption_preview)

    controls_layout.addSpacing(4)
    controls_layout.addWidget(self._field_label("Actions"))
    buttons_row = QHBoxLayout()
    buttons_row.setContentsMargins(0, 0, 0, 0)
    buttons_row.setSpacing(10)
    self.start_btn = QPushButton("Execute")
    self.start_btn.setProperty("class", "accent")
    self.start_btn.setIcon(build_icon("fa5s.play", "#ffffff"))
    self.start_btn.setEnabled(False)
    buttons_row.addWidget(self.start_btn)

    self.pause_btn = QPushButton("Pause")
    self.pause_btn.setIcon(build_icon("fa5s.pause", self._icon_color))
    self.pause_btn.setEnabled(False)
    buttons_row.addWidget(self.pause_btn)

    self.stop_btn = QPushButton("Stop")
    self.stop_btn.setProperty("class", "danger")
    self.stop_btn.setIcon(build_icon("fa5s.stop", "#ffffff"))
    self.stop_btn.setEnabled(False)
    buttons_row.addWidget(self.stop_btn)

    self.export_btn = QPushButton("Export")
    self.export_btn.setIcon(build_icon("fa5s.file-export", self._icon_color))
    buttons_row.addWidget(self.export_btn)
    buttons_row.addStretch(1)
    controls_layout.addLayout(buttons_row)

    self.headless_check = QCheckBox("Headless")
    controls_layout.addWidget(self.headless_check)
    self.retry_check = QCheckBox("Retry failures")
    controls_layout.addWidget(self.retry_check)
    controls_layout.addStretch(1)
    top_row.addWidget(controls_card, 3)

    scheduler_card = SurfaceCard()
    scheduler_layout = QVBoxLayout(scheduler_card)
    scheduler_layout.setContentsMargins(18, 18, 18, 18)
    scheduler_layout.setSpacing(8)
    scheduler_layout.addWidget(self._section_title("Scheduler settings"))

    scheduler_layout.addWidget(self._field_label("Schedule dates"))
    date_row = QHBoxLayout()
    date_row.setContentsMargins(0, 0, 0, 0)
    date_row.setSpacing(8)
    date_row.addWidget(self._inline_label("From"))
    self.start_date = self._build_date_edit(QDate.currentDate())
    date_row.addWidget(self.start_date)
    date_row.addWidget(self._inline_label("To"))
    self.end_date = self._build_date_edit(QDate.currentDate().addMonths(1))
    date_row.addWidget(self.end_date)
    date_row.addStretch(1)
    scheduler_layout.addLayout(date_row)

    time_layout = QVBoxLayout()
    time_layout.setContentsMargins(0, 0, 0, 0)
    time_layout.setSpacing(8)
    self.time_start_hour = self._build_hour_combo()
    self.time_start_minute = self._build_minute_combo()
    self.time_end_hour = self._build_hour_combo()
    self.time_end_hour.setCurrentText("23")
    self.time_end_minute = self._build_minute_combo()
    self.time_end_minute.setCurrentText("55")

    time_headers = QHBoxLayout()
    time_headers.setContentsMargins(0, 0, 0, 0)
    time_headers.setSpacing(12)
    time_headers.addWidget(self._field_label("From time"))
    time_headers.addWidget(self._field_label("To time"))
    time_headers.addStretch(1)
    time_layout.addLayout(time_headers)

    time_values = QHBoxLayout()
    time_values.setContentsMargins(0, 0, 0, 0)
    time_values.setSpacing(12)
    time_values.addWidget(self._time_row(self.time_start_hour, self.time_start_minute))
    time_values.addWidget(self._time_row(self.time_end_hour, self.time_end_minute))
    time_values.addStretch(1)
    time_layout.addLayout(time_values)

    interval_limit_labels = QHBoxLayout()
    interval_limit_labels.setContentsMargins(0, 0, 0, 0)
    interval_limit_labels.setSpacing(12)
    interval_limit_labels.addWidget(self._field_label("Interval"))
    interval_limit_labels.addWidget(self._field_label("Limit"))
    interval_limit_labels.addStretch(1)
    time_layout.addLayout(interval_limit_labels)

    interval_limit_row = QHBoxLayout()
    interval_limit_row.setContentsMargins(0, 0, 0, 0)
    interval_limit_row.setSpacing(12)
    self.interval_spin = QSpinBox()
    self.interval_spin.setRange(5, 1440)
    self.interval_spin.setValue(15)
    self.interval_spin.setSuffix(" min")
    self.interval_spin.setMaximumWidth(120)
    interval_limit_row.addWidget(self.interval_spin)

    self.limit_spin = QSpinBox()
    self.limit_spin.setRange(1, 9999)
    self.limit_spin.setValue(1)
    self.limit_spin.setMaximumWidth(100)
    interval_limit_row.addWidget(self.limit_spin)
    interval_limit_row.addStretch(1)
    time_layout.addLayout(interval_limit_row)
    scheduler_layout.addLayout(time_layout)

    self.generate_btn = QPushButton("Generate")
    self.generate_btn.setProperty("class", "accent")
    self.generate_btn.setIcon(build_icon("fa5s.cogs", "#ffffff"))
    self.generate_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    scheduler_layout.addWidget(self.generate_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    self.time_warning = QLabel("")
    self.time_warning.setProperty("class", "muted")
    self.time_warning.setStyleSheet("color: #d93025; font-size: 12px; font-weight: 600;")
    self.time_warning.hide()
    scheduler_layout.addWidget(self.time_warning)

    self.schedule_warning = QLabel("")
    self.schedule_warning.setProperty("class", "muted")
    self.schedule_warning.setStyleSheet("color: #d93025; font-size: 12px; font-weight: 600;")
    self.schedule_warning.hide()
    scheduler_layout.addWidget(self.schedule_warning)

    self.schedule_result_label = QLabel("")
    self.schedule_result_label.setProperty("class", "muted")
    self.schedule_result_label.hide()
    scheduler_layout.addWidget(self.schedule_result_label)
    scheduler_layout.addStretch(1)
    top_row.addWidget(scheduler_card, 4)
    self.content_layout.addLayout(top_row)

    table_card = SurfaceCard()
    table_layout = QVBoxLayout(table_card)
    table_layout.setContentsMargins(18, 18, 18, 18)
    table_layout.setSpacing(10)

    table_meta = QHBoxLayout()
    table_meta.setContentsMargins(0, 0, 0, 0)
    table_meta.setSpacing(14)

    self.filter_pending_check = QCheckBox("Pending")
    self.filter_pending_check.setChecked(True)
    self.filter_scheduled_check = QCheckBox("Scheduled")
    self.filter_scheduled_check.setChecked(True)
    self.filter_published_check = QCheckBox("Published")
    self.filter_published_check.setChecked(True)
    self.filter_failed_check = QCheckBox("Failed")
    self.filter_failed_check.setChecked(True)
    table_meta.addWidget(self.filter_pending_check)
    table_meta.addWidget(self.filter_scheduled_check)
    table_meta.addWidget(self.filter_published_check)
    table_meta.addWidget(self.filter_failed_check)
    table_meta.addStretch(1)

    self.video_total_label = QLabel("Total: 0")
    self.video_total_label.setProperty("class", "muted")
    self.video_selected_label = QLabel("Selected: 0")
    self.video_selected_label.setProperty("class", "muted")
    table_meta.addWidget(self.video_total_label)
    table_meta.addWidget(self.video_selected_label)
    table_layout.addLayout(table_meta)

    self.video_table = VideoTable(read_only=False)
    self.video_table.setMinimumHeight(370)
    table_layout.addWidget(self.video_table)
    self.content_layout.addWidget(table_card)

    terminal_wrap = SurfaceCard(class_name="muted-card")
    terminal_wrap_layout = QVBoxLayout(terminal_wrap)
    terminal_wrap_layout.setContentsMargins(10, 10, 10, 10)
    terminal_wrap_layout.setSpacing(0)
    self.terminal_panel = MacTerminalPanel(self._palette, title="Live terminal")
    self.log_panel = self.terminal_panel.log_view
    self.toggle_log_btn = self.terminal_panel.open_logs_button
    self.log_clear_button = self.terminal_panel.clear_button
    terminal_wrap_layout.addWidget(self.terminal_panel, 1)
    self.content_layout.addWidget(terminal_wrap, 1)

    progress_strip = QWidget()
    progress_strip.setProperty("class", "status-strip")
    progress_layout = QHBoxLayout(progress_strip)
    progress_layout.setContentsMargins(0, 10, 0, 0)
    progress_layout.setSpacing(12)

    self.progress_bar = self._build_progress_bar()
    progress_layout.addWidget(self.progress_bar, 1)

    self.progress_label = QLabel("0%")
    self.progress_label.setProperty("class", "muted")
    progress_layout.addWidget(self.progress_label)

    self.success_label = QLabel("Success 0")
    self.success_label.setProperty("class", "muted")
    progress_layout.addWidget(self.success_label)

    self.failure_label = QLabel("Failed 0")
    self.failure_label.setProperty("class", "muted")
    progress_layout.addWidget(self.failure_label)
    self.content_layout.addWidget(progress_strip)

  def _build_progress_bar(self):
    """Create the bottom progress bar.

    :return: Configured progress bar.
    """
    from PyQt6.QtWidgets import QProgressBar

    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    progress_bar.setTextVisible(False)
    return progress_bar

  def _build_date_edit(self, date_value: QDate) -> PickerDateEdit:
    """Create a calendar-based date picker.

    :param date_value: Initial date value.
    :return: Configured date edit.
    """
    date_edit = PickerDateEdit()
    date_edit.setDate(date_value)
    date_edit.setDisplayFormat("dd MMM yyyy")
    date_edit.setMaximumWidth(142)
    return date_edit

  def _build_hour_combo(self) -> QComboBox:
    """Create an hour selector.

    :return: Configured combo box.
    """
    combo = QComboBox()
    combo.addItems([f"{hour:02d}" for hour in range(24)])
    combo.setMaxVisibleItems(12)
    combo.setMaximumWidth(76)
    return combo

  def _build_minute_combo(self) -> QComboBox:
    """Create a minute selector in five-minute steps.

    :return: Configured combo box.
    """
    combo = QComboBox()
    combo.addItems([f"{minute:02d}" for minute in range(0, 60, 5)])
    combo.setMaxVisibleItems(12)
    combo.setMaximumWidth(76)
    return combo

  def _time_row(self, hour_combo: QComboBox, minute_combo: QComboBox) -> QWidget:
    """Create a compact hour and minute row.

    :param hour_combo: Hour combo box.
    :param minute_combo: Minute combo box.
    :return: Row widget.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(hour_combo)
    layout.addWidget(self._time_separator())
    layout.addWidget(minute_combo)
    layout.addStretch(1)
    return container

  def _time_separator(self) -> QLabel:
    """Create a time separator label.

    :return: Configured label.
    """
    label = QLabel(":")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setProperty("class", "section-title")
    return label

  def _section_title(self, text: str) -> QLabel:
    """Create a section title label.

    :param text: Title text.
    :return: Configured label.
    """
    label = QLabel(text)
    label.setProperty("class", "section-title")
    return label

  def _field_label(self, text: str) -> QLabel:
    """Create a muted field label.

    :param text: Label text.
    :return: Configured label.
    """
    label = QLabel(text)
    label.setProperty("class", "muted")
    return label

  def _inline_label(self, text: str) -> QLabel:
    """Create a compact inline label.

    :param text: Label text.
    :return: Configured label.
    """
    label = QLabel(text)
    label.setProperty("class", "muted")
    return label

  def set_palette_data(self, palette: ThemePalette) -> None:
    """Refresh palette-driven terminal presentation.

    :param palette: Active theme palette.
    :return: None
    """
    self._palette = palette
    self.terminal_panel.set_palette_data(palette)
