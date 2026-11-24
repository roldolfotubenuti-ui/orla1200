from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, timedelta

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import (
  QDialog,
  QFrame,
  QGraphicsDropShadowEffect,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QListWidget,
  QListWidgetItem,
  QPushButton,
  QVBoxLayout,
  QWidget,
)

from gui.widgets.icon import build_icon
from gui.widgets.tiktok_style import (
  TT_BG_HOVER,
  TT_BORDER,
  TT_FONT,
  TT_RED,
  TT_TEXT,
  TT_TEXT_2,
  TT_TEXT_DISABLED,
  hline,
  tt_base_stylesheet,
  vline,
)
from utils.datetime_utils import DateTimeUtils

MONTHS_PT = [
  "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
WEEKDAYS_PT = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

MIN_OFFSET_MINUTES = 30
MAX_OFFSET_DAYS = 10
MINUTE_STEP = 5


class TikTokScheduleDialog(QDialog):
  """TikTok Studio schedule popup: month grid + "Time" column.

  Enforces TikTok Studio schedule constraints:
  - Minimum 30 minutes ahead of current time.
  - Maximum 10 days in the future.
  - 5-minute interval steps.
  - Times outside the allowed range are disabled, styled grayish, and cannot be clicked.
  """

  scheduled = pyqtSignal(datetime)
  publish_now = pyqtSignal()

  def __init__(
    self,
    current_dt: datetime | None = None,
    filename: str = "",
    parent: QWidget | None = None,
    anchor: QWidget | None = None,
  ) -> None:
    super().__init__(parent)
    self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    self.setModal(True)
    self._filename = filename
    self._anchor = anchor

    now = datetime.now()
    self._min_dt = self._round_up(now + timedelta(minutes=MIN_OFFSET_MINUTES))
    self._max_dt = DateTimeUtils.max_allowed_datetime(now, max_offset_days=MAX_OFFSET_DAYS)

    if current_dt and DateTimeUtils.is_valid_schedule_time(
      current_dt, MIN_OFFSET_MINUTES, max_offset_days=MAX_OFFSET_DAYS
    ):
      start = current_dt
    else:
      start = self._min_dt

    self._selected_date: date = start.date()
    self._view_year = start.year
    self._view_month = start.month
    self._init_hour = start.hour
    self._init_minute = (start.minute // MINUTE_STEP) * MINUTE_STEP

    self._day_buttons: list[QPushButton] = []
    self._build_ui()
    self._render_month()
    self._update_time_constraints()

  # ------------------------------------------------------------------
  @staticmethod
  def _round_up(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    rem = dt.minute % MINUTE_STEP
    if rem:
      dt += timedelta(minutes=MINUTE_STEP - rem)
    return dt

  def _build_ui(self) -> None:
    outer = QVBoxLayout(self)
    outer.setContentsMargins(10, 10, 10, 10)

    self.panel = QFrame()
    self.panel.setObjectName("ttPopup")
    self.panel.setFixedSize(425, 395)
    shadow = QGraphicsDropShadowEffect(self.panel)
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 40))
    self.panel.setGraphicsEffect(shadow)
    outer.addWidget(self.panel)

    root = QVBoxLayout(self.panel)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)

    # ---------------- Calendar ----------------
    cal = QWidget()
    cal.setFixedWidth(295)
    cal_l = QVBoxLayout(cal)
    cal_l.setContentsMargins(14, 12, 12, 8)
    cal_l.setSpacing(4)

    nav = QHBoxLayout()
    self.prev_btn = QPushButton()
    self.prev_btn.setObjectName("ttIconBtn")
    self.prev_btn.setIcon(build_icon("fa5s.chevron-left", TT_TEXT))
    self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.prev_btn.clicked.connect(lambda: self._shift_month(-1))
    nav.addWidget(self.prev_btn)

    self.month_lbl = QLabel()
    self.month_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.month_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #161823;")
    nav.addWidget(self.month_lbl, 1)

    self.next_btn = QPushButton()
    self.next_btn.setObjectName("ttIconBtn")
    self.next_btn.setIcon(build_icon("fa5s.chevron-right", TT_TEXT))
    self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.next_btn.clicked.connect(lambda: self._shift_month(1))
    nav.addWidget(self.next_btn)
    cal_l.addLayout(nav)

    grid = QGridLayout()
    grid.setHorizontalSpacing(4)
    grid.setVerticalSpacing(4)
    for col, name in enumerate(WEEKDAYS_PT):
      lbl = QLabel(name)
      lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
      lbl.setFixedHeight(26)
      lbl.setStyleSheet(f"color: {TT_TEXT_DISABLED}; font-size: 12px; font-weight: 600;")
      grid.addWidget(lbl, 0, col)

    for i in range(42):
      btn = QPushButton()
      btn.setFixedSize(34, 34)
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      btn.clicked.connect(lambda _c=False, idx=i: self._on_day_clicked(idx))
      grid.addWidget(btn, 1 + i // 7, i % 7, alignment=Qt.AlignmentFlag.AlignCenter)
      self._day_buttons.append(btn)
    cal_l.addLayout(grid)
    body.addWidget(cal)
    body.addWidget(vline())

    # ---------------- Time ----------------
    time_w = QWidget()
    time_w.setFixedWidth(128)
    time_l = QVBoxLayout(time_w)
    time_l.setContentsMargins(0, 12, 0, 0)
    time_l.setSpacing(0)

    t_title = QLabel("Time")
    t_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    t_title.setFixedHeight(30)
    t_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #161823;")
    time_l.addWidget(t_title)
    time_l.addSpacing(6)
    time_l.addWidget(hline())

    cols = QHBoxLayout()
    cols.setContentsMargins(8, 4, 8, 4)
    cols.setSpacing(0)

    self.hour_list = self._make_time_list([f"{h:02d}" for h in range(24)])
    self.hour_list.setFixedHeight(240)
    self.hour_list.itemClicked.connect(self._on_hour_clicked)
    self.hour_list.currentItemChanged.connect(self._on_hour_current_changed)

    self.minute_list = self._make_time_list([f"{m:02d}" for m in range(0, 60, MINUTE_STEP)])
    self.minute_list.setFixedHeight(240)
    self.minute_list.itemClicked.connect(self._on_minute_clicked)
    self.minute_list.currentItemChanged.connect(self._on_minute_current_changed)

    colon = QLabel(":")
    colon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    colon.setFixedWidth(12)
    colon.setStyleSheet(f"color: {TT_TEXT_2}; font-weight: 700; font-size: 14px;")

    cols.addWidget(self.hour_list)
    cols.addWidget(colon)
    cols.addWidget(self.minute_list)
    time_l.addLayout(cols, 1)
    body.addWidget(time_w)
    root.addLayout(body)

    root.addWidget(hline())

    # ---------------- Error line (Dedicated Row) ----------------
    self.error_lbl = QLabel("")
    self.error_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.error_lbl.setStyleSheet(f"color: {TT_RED}; font-size: 11px; font-weight: 600; padding: 2px 8px;")
    self.error_lbl.setFixedHeight(18)
    self.error_lbl.hide()
    root.addWidget(self.error_lbl)

    # ---------------- Footer ----------------
    footer = QHBoxLayout()
    footer.setContentsMargins(14, 8, 14, 10)
    footer.setSpacing(8)

    self.cancel_btn = QPushButton("Cancelar")
    self.cancel_btn.setObjectName("ttPillGray")
    self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.cancel_btn.clicked.connect(self.reject)
    footer.addWidget(self.cancel_btn)

    footer.addStretch(1)

    self.now_btn = QPushButton("Publicar agora")
    self.now_btn.setObjectName("ttPillGray")
    self.now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.now_btn.clicked.connect(self._on_publish_now)
    footer.addWidget(self.now_btn)

    self.confirm_btn = QPushButton("Programados")
    self.confirm_btn.setObjectName("ttPillRed")
    self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.confirm_btn.clicked.connect(self._on_confirm_schedule)
    footer.addWidget(self.confirm_btn)
    root.addLayout(footer)

    self.setStyleSheet(tt_base_stylesheet() + f"""
      QFrame#ttPopup {{
        background: #FFFFFF;
        border: 1px solid {TT_BORDER};
        border-radius: 8px;
        font-family: {TT_FONT};
      }}
      QListWidget {{
        background: transparent;
        border: none;
        outline: none;
      }}
      QListWidget::item {{
        height: 32px;
        color: {TT_TEXT};
        font-size: 14px;
        border: none;
      }}
      QListWidget::item:hover {{
        color: #161823;
        background: {TT_BG_HOVER};
        border-radius: 4px;
      }}
      QListWidget::item:disabled {{
        color: {TT_TEXT_DISABLED};
        background: transparent;
      }}
      QListWidget::item:disabled:hover {{
        color: {TT_TEXT_DISABLED};
        background: transparent;
      }}
      QListWidget::item:selected {{
        color: {TT_TEXT};
        font-weight: 700;
        background: transparent;
        border-top: 1px solid {TT_BORDER};
        border-bottom: 1px solid {TT_BORDER};
      }}
    """)

    self._select_list_value(self.hour_list, f"{self._init_hour:02d}")
    self._select_list_value(self.minute_list, f"{self._init_minute:02d}")

  def _make_time_list(self, values: list[str]) -> QListWidget:
    lw = QListWidget()
    lw.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    lw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    lw.setFixedWidth(50)
    for v in values:
      it = QListWidgetItem(v)
      it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      lw.addItem(it)
    return lw

  @staticmethod
  def _select_list_value(lw: QListWidget, value: str) -> None:
    for i in range(lw.count()):
      if lw.item(i).text() == value and (lw.item(i).flags() & Qt.ItemFlag.ItemIsEnabled):
        lw.setCurrentRow(i)
        lw.scrollToItem(lw.item(i), QListWidget.ScrollHint.PositionAtCenter)
        return
    for i in range(lw.count()):
      if lw.item(i).flags() & Qt.ItemFlag.ItemIsEnabled:
        lw.setCurrentRow(i)
        lw.scrollToItem(lw.item(i), QListWidget.ScrollHint.PositionAtCenter)
        return

  # ------------------------------------------------------------------
  # Time constraints and graying out logic
  # ------------------------------------------------------------------
  def _update_time_constraints(self) -> None:
    """Enable only hours and minutes that fall between _min_dt and _max_dt.

    Disallowed hours and minutes are disabled (Qt.ItemFlag.NoItemFlags),
    styled in TT_TEXT_DISABLED (#C4C4C4), and clicking on them does nothing.
    """
    now = datetime.now()
    self._min_dt = self._round_up(now + timedelta(minutes=MIN_OFFSET_MINUTES))
    self._max_dt = DateTimeUtils.max_allowed_datetime(now, max_offset_days=MAX_OFFSET_DAYS)

    d = self._selected_date
    first_valid_hour_row: int | None = None

    # 1. Update hours
    for row in range(self.hour_list.count()):
      item = self.hour_list.item(row)
      hour = int(item.text())
      has_valid_slot = False
      for m in range(0, 60, MINUTE_STEP):
        candidate_dt = datetime(d.year, d.month, d.day, hour, m, 0)
        if self._min_dt <= candidate_dt <= self._max_dt:
          has_valid_slot = True
          break

      if has_valid_slot:
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setForeground(QColor(TT_TEXT))
        if first_valid_hour_row is None:
          first_valid_hour_row = row
      else:
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(QColor(TT_TEXT_DISABLED))

    # Verify if selected hour is valid; if not, switch to first valid hour
    current_h_item = self.hour_list.currentItem()
    if not current_h_item or not (current_h_item.flags() & Qt.ItemFlag.ItemIsEnabled):
      if first_valid_hour_row is not None:
        self.hour_list.setCurrentRow(first_valid_hour_row)
        self.hour_list.scrollToItem(
          self.hour_list.item(first_valid_hour_row),
          QListWidget.ScrollHint.PositionAtCenter,
        )

    # 2. Update minutes for the active hour
    self._update_minute_constraints()

  def _update_minute_constraints(self) -> None:
    """Enable only minutes for the currently selected hour that fall within bounds."""
    d = self._selected_date
    current_h_item = self.hour_list.currentItem()
    if not current_h_item:
      return

    try:
      hour = int(current_h_item.text())
    except Exception:
      return

    first_valid_min_row: int | None = None
    for row in range(self.minute_list.count()):
      item = self.minute_list.item(row)
      minute = int(item.text())
      candidate_dt = datetime(d.year, d.month, d.day, hour, minute, 0)

      if self._min_dt <= candidate_dt <= self._max_dt:
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        item.setForeground(QColor(TT_TEXT))
        if first_valid_min_row is None:
          first_valid_min_row = row
      else:
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(QColor(TT_TEXT_DISABLED))

    current_m_item = self.minute_list.currentItem()
    if not current_m_item or not (current_m_item.flags() & Qt.ItemFlag.ItemIsEnabled):
      if first_valid_min_row is not None:
        self.minute_list.setCurrentRow(first_valid_min_row)
        self.minute_list.scrollToItem(
          self.minute_list.item(first_valid_min_row),
          QListWidget.ScrollHint.PositionAtCenter,
        )

  def _restore_valid_hour(self) -> None:
    for row in range(self.hour_list.count()):
      item = self.hour_list.item(row)
      if item.flags() & Qt.ItemFlag.ItemIsEnabled:
        self.hour_list.setCurrentRow(row)
        self.hour_list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
        self._update_minute_constraints()
        return

  def _restore_valid_minute(self) -> None:
    for row in range(self.minute_list.count()):
      item = self.minute_list.item(row)
      if item.flags() & Qt.ItemFlag.ItemIsEnabled:
        self.minute_list.setCurrentRow(row)
        self.minute_list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
        return

  def _on_hour_clicked(self, item: QListWidgetItem) -> None:
    if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
      self._restore_valid_hour()
      return
    self.error_lbl.clear()
    self.error_lbl.hide()
    self._update_minute_constraints()

  def _on_hour_current_changed(
    self, current: QListWidgetItem | None, previous: QListWidgetItem | None
  ) -> None:
    if not current:
      return
    if not (current.flags() & Qt.ItemFlag.ItemIsEnabled):
      if previous and (previous.flags() & Qt.ItemFlag.ItemIsEnabled):
        self.hour_list.setCurrentItem(previous)
      else:
        self._restore_valid_hour()
      return
    self.error_lbl.clear()
    self.error_lbl.hide()
    self._update_minute_constraints()

  def _on_minute_clicked(self, item: QListWidgetItem) -> None:
    if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
      self._restore_valid_minute()
      return
    self.error_lbl.clear()
    self.error_lbl.hide()

  def _on_minute_current_changed(
    self, current: QListWidgetItem | None, previous: QListWidgetItem | None
  ) -> None:
    if not current:
      return
    if not (current.flags() & Qt.ItemFlag.ItemIsEnabled):
      if previous and (previous.flags() & Qt.ItemFlag.ItemIsEnabled):
        self.minute_list.setCurrentItem(previous)
      else:
        self._restore_valid_minute()
      return
    self.error_lbl.clear()
    self.error_lbl.hide()

  # ------------------------------------------------------------------
  # Calendar logic
  # ------------------------------------------------------------------
  def _month_cells(self) -> list[date]:
    first = date(self._view_year, self._view_month, 1)
    lead = (first.weekday() + 1) % 7  # Sunday-first
    start = first - timedelta(days=lead)
    return [start + timedelta(days=i) for i in range(42)]

  def _render_month(self) -> None:
    self.month_lbl.setText(f"{MONTHS_PT[self._view_month]} / {self._view_year}")
    min_d = self._min_dt.date()
    max_d = self._max_dt.date()
    self._cells = self._month_cells()
    last_row_hidden = all(d.month != self._view_month for d in self._cells[35:])
    for i, (btn, d) in enumerate(zip(self._day_buttons, self._cells)):
      btn.setText(str(d.day))
      btn.setVisible(not (last_row_hidden and i >= 35))
      enabled = min_d <= d <= max_d
      btn.setEnabled(enabled)
      selected = d == self._selected_date
      if selected:
        style = f"background: {TT_RED}; color: #FFFFFF; font-weight: 700; border-radius: 17px; font-size: 14px;"
      elif enabled:
        style = f"background: transparent; color: {TT_TEXT}; border-radius: 17px; font-size: 14px; font-weight: 500;"
      else:
        style = f"background: transparent; color: {TT_TEXT_DISABLED}; border-radius: 17px; font-size: 14px;"
      hover = "" if selected or not enabled else f"QPushButton:hover {{ background: {TT_BG_HOVER}; }}"
      btn.setStyleSheet(f"QPushButton {{ {style} }} {hover}")

    self.prev_btn.setEnabled(date(self._view_year, self._view_month, 1) > min_d.replace(day=1))
    self.next_btn.setEnabled(date(self._view_year, self._view_month, 1) < max_d.replace(day=1))

  def _shift_month(self, delta: int) -> None:
    m = self._view_month + delta
    y = self._view_year
    if m < 1:
      m, y = 12, y - 1
    elif m > 12:
      m, y = 1, y + 1
    self._view_month, self._view_year = m, y
    self._render_month()

  def _on_day_clicked(self, idx: int) -> None:
    try:
      d = self._cells[idx]
      self._selected_date = d
      self.error_lbl.clear()
      self.error_lbl.hide()
      if d.month != self._view_month:
        self._view_year, self._view_month = d.year, d.month
      self._render_month()
      self._update_time_constraints()
    except Exception:
      pass

  # ------------------------------------------------------------------
  def selected_datetime(self) -> datetime:
    hi = self.hour_list.currentItem()
    mi = self.minute_list.currentItem()
    hour = int(hi.text()) if hi and (hi.flags() & Qt.ItemFlag.ItemIsEnabled) else self._init_hour
    minute = int(mi.text()) if mi and (mi.flags() & Qt.ItemFlag.ItemIsEnabled) else self._init_minute
    d = self._selected_date
    return datetime(d.year, d.month, d.day, hour, minute, 0)

  def _on_confirm_schedule(self) -> None:
    try:
      dt = self.selected_datetime()
      if not DateTimeUtils.is_valid_schedule_time(dt, MIN_OFFSET_MINUTES, max_offset_days=MAX_OFFSET_DAYS):
        self.error_lbl.setText("Escolha um horário entre 30 min e 10 dias a partir de agora.")
        self.error_lbl.show()
        return
      self.scheduled.emit(dt)
      self.accept()
    except Exception as exc:
      self.error_lbl.setText(f"Erro: {exc}")
      self.error_lbl.show()

  def _on_publish_now(self) -> None:
    try:
      self.publish_now.emit()
    finally:
      self.accept()

  # ------------------------------------------------------------------
  def showEvent(self, event) -> None:  # noqa: N802
    super().showEvent(event)
    if self._anchor is not None:
      try:
        pos = self._anchor.mapToGlobal(QPoint(-12, self._anchor.height() - 6))
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        if screen is not None:
          geo = screen.availableGeometry()
          x = min(max(geo.left(), pos.x()), geo.right() - self.width())
          y = pos.y()
          if y + self.height() > geo.bottom():
            y = self._anchor.mapToGlobal(QPoint(0, 0)).y() - self.height() + 6
          pos = QPoint(x, max(geo.top(), y))
        self.move(pos)
      except Exception:
        pass
