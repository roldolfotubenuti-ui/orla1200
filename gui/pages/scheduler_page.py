from __future__ import annotations

from PyQt6.QtCore import QDate, QTimer, Qt
from PyQt6.QtWidgets import (
  QComboBox,
  QDateEdit,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QPushButton,
  QSpinBox,
  QVBoxLayout,
  QWidget,
)

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.widgets.icon import build_icon


class PickerDateEdit(QDateEdit):
  """Date edit that opens the calendar popup when clicked.

  :param parent: Parent widget.
  :return: None
  """

  def __init__(self, parent: QWidget | None = None) -> None:
    """Initialize the date picker field.

    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setCalendarPopup(True)
    self.setReadOnly(True)

  def mousePressEvent(self, event) -> None:  # noqa: N802
    """Open the calendar popup when the field is clicked.

    :param event: Mouse event.
    :return: None
    """
    super().mousePressEvent(event)
    QTimer.singleShot(0, self.showCalendarPopup)


class SchedulerPage(PageLayout):
  """Schedule settings page.

  :param icon_color: Accent color used for icons.
  :return: None
  """

  TITLE = "Scheduler Settings"
  DESCRIPTION = "Configure the scheduling window, generate slots, and then review the outcome in the Video Table tab."

  def __init__(self, icon_color: str) -> None:
    """Initialize the scheduler page.

    :param icon_color: Accent color used for icons.
    :return: None
    """
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    """Build the scheduler settings UI.

    :return: None
    """
    self.content_layout.addWidget(SectionHeader(
      "Scheduling window",
      "Define the date range, pick clear hour and minute values, then generate upload slots for the video queue.",
      "fa5s.calendar-alt",
      self._icon_color,
    ))

    form_grid = QGridLayout()
    form_grid.setContentsMargins(0, 0, 0, 0)
    form_grid.setHorizontalSpacing(18)
    form_grid.setVerticalSpacing(12)

    form_grid.addWidget(self._field_header("fa5s.calendar-day", "From"), 0, 0)
    self.start_date = self._build_date_edit(QDate.currentDate())
    form_grid.addWidget(self.start_date, 1, 0)

    form_grid.addWidget(self._field_header("fa5s.calendar-check", "To"), 0, 1)
    self.end_date = self._build_date_edit(QDate.currentDate().addMonths(1))
    form_grid.addWidget(self.end_date, 1, 1)

    form_grid.addWidget(self._field_header("fa5s.clock", "From time"), 2, 0)
    self.time_start_hour = self._build_hour_combo()
    self.time_start_minute = self._build_minute_combo()
    form_grid.addWidget(
      self._time_row(self.time_start_hour, self.time_start_minute),
      3,
      0,
    )

    form_grid.addWidget(self._field_header("fa5s.hourglass-end", "To time"), 2, 1)
    self.time_end_hour = self._build_hour_combo()
    self.time_end_hour.setCurrentText("23")
    self.time_end_minute = self._build_minute_combo()
    self.time_end_minute.setCurrentText("55")
    form_grid.addWidget(
      self._time_row(self.time_end_hour, self.time_end_minute),
      3,
      1,
    )

    form_grid.addWidget(self._field_header("fa5s.stopwatch", "Interval"), 4, 0)
    self.interval_spin = QSpinBox()
    self.interval_spin.setRange(5, 1440)
    self.interval_spin.setValue(15)
    self.interval_spin.setSuffix(" min")
    form_grid.addWidget(self.interval_spin, 5, 0)

    form_grid.addWidget(self._field_header("fa5s.layer-group", "Limit"), 4, 1)
    self.limit_spin = QSpinBox()
    self.limit_spin.setRange(1, 9999)
    self.limit_spin.setValue(1)
    form_grid.addWidget(self.limit_spin, 5, 1)

    self.content_layout.addLayout(form_grid)

    self.time_warning = QLabel("")
    self.time_warning.setProperty("class", "muted")
    self.time_warning.setStyleSheet("color: #d93025; font-size: 12px; font-weight: 600;")
    self.time_warning.hide()
    self.content_layout.addWidget(self.time_warning)

    self.schedule_warning = QLabel("")
    self.schedule_warning.setProperty("class", "muted")
    self.schedule_warning.setStyleSheet("color: #d93025; font-size: 12px; font-weight: 600;")
    self.schedule_warning.hide()
    self.content_layout.addWidget(self.schedule_warning)

    self.schedule_result_label = QLabel("")
    self.schedule_result_label.setProperty("class", "muted")
    self.schedule_result_label.hide()
    self.content_layout.addWidget(self.schedule_result_label)

    action_row = QHBoxLayout()
    action_row.setContentsMargins(0, 4, 0, 0)
    action_row.setSpacing(10)
    self.generate_btn = QPushButton("Generate")
    self.generate_btn.setProperty("class", "accent")
    self.generate_btn.setIcon(build_icon("fa5s.cogs", "#ffffff"))
    action_row.addWidget(self.generate_btn)
    action_row.addStretch(1)
    self.content_layout.addLayout(action_row)
    self.content_layout.addStretch(1)

  def _build_date_edit(self, date_value: QDate) -> QDateEdit:
    """Create a calendar-based date picker.

    :param date_value: Initial date value.
    :return: Configured date edit.
    """
    date_edit = PickerDateEdit()
    date_edit.setDate(date_value)
    date_edit.setDisplayFormat("dd MMM yyyy")
    return date_edit

  def _field_header(self, icon_name: str, text: str) -> QWidget:
    """Create a compact field header with an icon.

    :param icon_name: qtawesome icon name.
    :param text: Header text.
    :return: Configured header widget.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    icon_label = QLabel()
    icon_label.setPixmap(build_icon(icon_name, self._icon_color).pixmap(14, 14))
    layout.addWidget(icon_label)

    text_label = QLabel(text)
    text_label.setProperty("class", "muted")
    layout.addWidget(text_label)
    layout.addStretch(1)
    return container

  def _time_row(self, hour_combo: QComboBox, minute_combo: QComboBox) -> QWidget:
    """Create a clear hour and minute row.

    :param hour_combo: Hour combo box.
    :param minute_combo: Minute combo box.
    :return: Row container.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    hour_combo.setMaximumWidth(92)
    minute_combo.setMaximumWidth(92)
    layout.addWidget(hour_combo)

    separator = QLabel(":")
    separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
    separator.setProperty("class", "section-title")
    layout.addWidget(separator)

    layout.addWidget(minute_combo)
    layout.addStretch(1)
    return container

  def _build_hour_combo(self) -> QComboBox:
    """Create an hour selector.

    :return: Configured combo box.
    """
    combo = QComboBox()
    combo.addItems([f"{hour:02d}" for hour in range(24)])
    combo.setMaxVisibleItems(12)
    return combo

  def _build_minute_combo(self) -> QComboBox:
    """Create a minute selector in five-minute steps.

    :return: Configured combo box.
    """
    combo = QComboBox()
    combo.addItems([f"{minute:02d}" for minute in range(0, 60, 5)])
    combo.setMaxVisibleItems(12)
    return combo
