from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
  QCalendarWidget,
  QCheckBox,
  QComboBox,
  QDateEdit,
  QFrame,
  QGridLayout,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QListWidget,
  QListWidgetItem,
  QPushButton,
  QSpinBox,
  QVBoxLayout,
  QWidget,
)

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon
from gui.widgets.tag_editor import HashtagTextEdit
from utils.video_media import VideoMediaUtils


class VideoCaptionRowCard(SurfaceCard):
  """Individual per-video caption and hashtags editor card."""

  caption_edited = pyqtSignal(str, str, str)

  def __init__(
    self,
    filename: str,
    file_path: Path,
    caption_text: str,
    hashtags_text: str,
    thumb_cache_dir: Path | None = None,
    parent: QWidget | None = None,
  ) -> None:
    super().__init__(class_name="muted-card", parent=parent)
    self._filename = filename
    self._custom_modified = bool(caption_text.strip() or hashtags_text.strip())

    layout = QHBoxLayout(self)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(14)

    thumb_lbl = QLabel()
    thumb_lbl.setPixmap(VideoMediaUtils.get_thumbnail(file_path, thumb_cache_dir, 88, 56))
    thumb_lbl.setFixedSize(88, 56)
    layout.addWidget(thumb_lbl)

    fields_col = QVBoxLayout()
    fields_col.setSpacing(6)

    top_row = QHBoxLayout()
    name_lbl = QLabel(filename)
    name_lbl.setProperty("class", "section-title")
    top_row.addWidget(name_lbl)
    top_row.addStretch(1)

    self.preview_lbl = QLabel("")
    self.preview_lbl.setProperty("class", "muted")
    top_row.addWidget(self.preview_lbl)
    fields_col.addLayout(top_row)

    inputs_row = QHBoxLayout()
    inputs_row.setSpacing(10)

    self.caption_edit = QLineEdit(caption_text)
    self.caption_edit.setPlaceholderText("Legenda deste vídeo...")
    self.caption_edit.textEdited.connect(self._on_user_edit)
    inputs_row.addWidget(self.caption_edit, 3)

    self.hashtags_edit = QLineEdit(hashtags_text)
    self.hashtags_edit.setPlaceholderText("Hashtags (ex: #tiktok #viral)")
    self.hashtags_edit.textEdited.connect(self._on_user_edit)
    inputs_row.addWidget(self.hashtags_edit, 2)

    fields_col.addLayout(inputs_row)
    layout.addLayout(fields_col, 1)

    self._update_preview()

  def _on_user_edit(self) -> None:
    self._custom_modified = bool(
      self.caption_edit.text().strip() or self.hashtags_edit.text().strip()
    )
    self._update_preview()
    self.caption_edited.emit(
      self._filename,
      self.caption_edit.text().strip(),
      self.hashtags_edit.text().strip(),
    )

  def _update_preview(self) -> None:
    full = self.full_caption()
    short = (full[:65] + "...") if len(full) > 65 else (full or "(Sem legenda)")
    self.preview_lbl.setText(f"Preview: {short}")

  def full_caption(self) -> str:
    cap = self.caption_edit.text().strip()
    tags = self.hashtags_edit.text().strip()
    if tags:
      formatted_tags = " ".join(
        t if t.startswith("#") else f"#{t}"
        for t in tags.split()
        if t.strip()
      )
      return f"{cap} {formatted_tags}".strip() if cap else formatted_tags
    return cap

  @property
  def is_customized(self) -> bool:
    return self._custom_modified and bool(
      self.caption_edit.text().strip() or self.hashtags_edit.text().strip()
    )

  def set_custom_caption(self, caption_text: str, hashtags_text: str) -> None:
    """Explicitly set custom caption and hashtags on this card and mark it as customized."""
    self.caption_edit.setText(caption_text)
    self.hashtags_edit.setText(hashtags_text)
    self._custom_modified = bool(caption_text.strip() or hashtags_text.strip())
    self._update_preview()

  def apply_default(self, caption_text: str, hashtags_text: str, force: bool = False) -> bool:
    if self.is_customized and not force:
      return False
    self.caption_edit.setText(caption_text)
    self.hashtags_edit.setText(hashtags_text)
    self._custom_modified = False
    self._update_preview()
    self.caption_edited.emit(
      self._filename,
      self.caption_edit.text().strip(),
      self.hashtags_edit.text().strip(),
    )
    return True


class ConfigWizardPage(PageLayout):
  """Wizard Step 3: Configure days, times, per-video captions, and automatic distribution."""

  TITLE = "3. Configurar Dias, Horários e Legendas"
  DESCRIPTION = "Defina os dias da semana ou datas, adicione horários de publicação, personalize legendas e distribua os vídeos."

  distribute_requested = pyqtSignal()
  back_requested = pyqtSignal()
  continue_requested = pyqtSignal()
  per_video_caption_changed = pyqtSignal(str, str, str)

  WEEKDAYS: list[tuple[int, str]] = [
    (0, "Segunda-feira"),
    (1, "Terça-feira"),
    (2, "Quarta-feira"),
    (3, "Quinta-feira"),
    (4, "Sexta-feira"),
    (5, "Sábado"),
    (6, "Domingo"),
  ]

  DEFAULT_TIMES: list[str] = ["09:00", "12:00", "15:00", "18:00", "21:00"]

  def __init__(self, icon_color: str) -> None:
    super().__init__()
    self._icon_color = icon_color
    self._time_slots: list[str] = list(self.DEFAULT_TIMES)
    self._specific_dates: set[str] = set()
    self._caption_cards: dict[str, VideoCaptionRowCard] = {}
    self._build_ui()

  def _build_ui(self) -> None:
    header_card = SurfaceCard()
    header_layout = QVBoxLayout(header_card)
    header_layout.setContentsMargins(20, 18, 20, 18)
    header_layout.setSpacing(8)
    header_layout.addWidget(SectionHeader(
      "ETAPA 3 — CONFIGURAR DIAS, HORÁRIOS E LEGENDAS",
      "Configure os dias de publicação, os horários diários e as legendas individuais ou padrão. O sistema distribuirá os vídeos automaticamente na ordem definida.",
      "fa5s.calendar-alt",
      self._icon_color,
    ))
    self.content_layout.addWidget(header_card)

    top_grid = QHBoxLayout()
    top_grid.setSpacing(16)

    # ================================================================
    # AREA A: CONFIGURAÇÃO DE DIAS
    # ================================================================
    days_card = SurfaceCard()
    days_layout = QVBoxLayout(days_card)
    days_layout.setContentsMargins(18, 18, 18, 18)
    days_layout.setSpacing(10)
    days_layout.addWidget(SectionHeader(
      "A. Configuração de Dias",
      "Escolha o intervalo de datas, os dias da semana ativos ou datas específicas no calendário.",
      "fa5s.calendar-week",
      self._icon_color,
    ))

    range_row = QHBoxLayout()
    range_row.setSpacing(10)
    range_row.addWidget(QLabel("Data inicial:"))
    self.start_date = QDateEdit(QDate.currentDate())
    self.start_date.setCalendarPopup(True)
    self.start_date.setDisplayFormat("dd MMM yyyy")
    range_row.addWidget(self.start_date)

    range_row.addWidget(QLabel("Data final:"))
    self.end_date = QDateEdit(QDate.currentDate().addDays(10))
    self.end_date.setCalendarPopup(True)
    self.end_date.setDisplayFormat("dd MMM yyyy")
    range_row.addWidget(self.end_date)
    range_row.addStretch(1)
    days_layout.addLayout(range_row)

    weekdays_lbl = QLabel("Dias da semana permitidos:")
    weekdays_lbl.setProperty("class", "muted")
    days_layout.addWidget(weekdays_lbl)

    weekdays_grid = QGridLayout()
    weekdays_grid.setHorizontalSpacing(14)
    weekdays_grid.setVerticalSpacing(6)
    self.weekday_checks: dict[int, QCheckBox] = {}
    for idx, (day_num, day_name) in enumerate(self.WEEKDAYS):
      cb = QCheckBox(day_name)
      cb.setChecked(True)
      self.weekday_checks[day_num] = cb
      weekdays_grid.addWidget(cb, idx // 2, idx % 2)
    days_layout.addLayout(weekdays_grid)

    cal_lbl = QLabel("Calendário (clique em uma data para fixar/remover data específica opcional):")
    cal_lbl.setProperty("class", "muted")
    days_layout.addWidget(cal_lbl)

    self.specific_calendar = QCalendarWidget()
    self.specific_calendar.setMinimumHeight(210)
    self.specific_calendar.clicked.connect(self._on_calendar_date_clicked)
    days_layout.addWidget(self.specific_calendar)

    spec_row = QHBoxLayout()
    self.specific_dates_label = QLabel("Datas específicas: Todas do intervalo nos dias da semana marcados")
    self.specific_dates_label.setProperty("class", "muted")
    self.specific_dates_label.setWordWrap(True)
    spec_row.addWidget(self.specific_dates_label, 1)

    self.clear_specific_dates_btn = QPushButton("Limpar Datas Fixas")
    self.clear_specific_dates_btn.clicked.connect(self.clear_specific_dates)
    spec_row.addWidget(self.clear_specific_dates_btn)
    days_layout.addLayout(spec_row)

    top_grid.addWidget(days_card, 3)

    # ================================================================
    # AREA B: CONFIGURAÇÃO DE HORÁRIOS
    # ================================================================
    times_card = SurfaceCard()
    times_layout = QVBoxLayout(times_card)
    times_layout.setContentsMargins(18, 18, 18, 18)
    times_layout.setSpacing(10)
    times_layout.addWidget(SectionHeader(
      "B. Configuração de Horários",
      "Adicione, edite ou remova os horários diários de publicação (múltiplos de 5 min exigidos pelo TikTok).",
      "fa5s.clock",
      self._icon_color,
    ))

    add_time_row = QHBoxLayout()
    add_time_row.setSpacing(8)

    self.slot_hour_combo = QComboBox()
    self.slot_hour_combo.addItems([f"{h:02d}" for h in range(24)])
    self.slot_hour_combo.setCurrentText("09")
    self.slot_hour_combo.setMaximumWidth(82)
    add_time_row.addWidget(self.slot_hour_combo)

    add_time_row.addWidget(QLabel(":"))

    self.slot_minute_combo = QComboBox()
    self.slot_minute_combo.addItems([f"{m:02d}" for m in range(0, 60, 5)])
    self.slot_minute_combo.setCurrentText("00")
    self.slot_minute_combo.setMaximumWidth(82)
    add_time_row.addWidget(self.slot_minute_combo)

    self.add_time_btn = QPushButton("+ Adicionar horário")
    self.add_time_btn.setProperty("class", "accent")
    self.add_time_btn.clicked.connect(self._on_add_time_slot)
    add_time_row.addWidget(self.add_time_btn)

    self.update_time_btn = QPushButton("Atualizar selecionado")
    self.update_time_btn.clicked.connect(self._on_update_selected_time_slot)
    add_time_row.addWidget(self.update_time_btn)
    add_time_row.addStretch(1)
    times_layout.addLayout(add_time_row)

    self.times_list_widget = QListWidget()
    self.times_list_widget.setMinimumHeight(180)
    self.times_list_widget.currentTextChanged.connect(self._on_time_slot_selected)
    times_layout.addWidget(self.times_list_widget, 1)

    time_actions_row = QHBoxLayout()
    self.remove_time_btn = QPushButton("Remover horário selecionado")
    self.remove_time_btn.setProperty("class", "danger")
    self.remove_time_btn.clicked.connect(self._on_remove_time_slot)
    time_actions_row.addWidget(self.remove_time_btn)

    self.reset_times_btn = QPushButton("Padrão (09h, 12h, 15h, 18h, 21h)")
    self.reset_times_btn.clicked.connect(self._on_reset_default_times)
    time_actions_row.addWidget(self.reset_times_btn)
    time_actions_row.addStretch(1)
    times_layout.addLayout(time_actions_row)

    # Hidden/compatible legacy controls so existing ScheduleControllerMixin methods & tests continue working seamlessly
    compat_box = QFrame()
    compat_lay = QHBoxLayout(compat_box)
    compat_lay.setContentsMargins(0, 4, 0, 0)
    compat_lay.setSpacing(10)
    compat_lay.addWidget(QLabel("Limite do lote:"))
    self.limit_spin = QSpinBox()
    self.limit_spin.setRange(1, 9999)
    self.limit_spin.setValue(1)
    compat_lay.addWidget(self.limit_spin)

    compat_lay.addWidget(QLabel("Intervalo fallback:"))
    self.interval_spin = QSpinBox()
    self.interval_spin.setRange(5, 1440)
    self.interval_spin.setValue(15)
    self.interval_spin.setSuffix(" min")
    compat_lay.addWidget(self.interval_spin)
    compat_lay.addStretch(1)
    times_layout.addWidget(compat_box)

    # Hidden legacy time combos for backward compatibility with existing tests
    self.time_start_hour = QComboBox()
    self.time_start_hour.addItems([f"{h:02d}" for h in range(24)])
    self.time_start_hour.hide()
    self.time_start_minute = QComboBox()
    self.time_start_minute.addItems([f"{m:02d}" for m in range(0, 60, 5)])
    self.time_start_minute.hide()
    self.time_end_hour = QComboBox()
    self.time_end_hour.addItems([f"{h:02d}" for h in range(24)])
    self.time_end_hour.setCurrentText("23")
    self.time_end_hour.hide()
    self.time_end_minute = QComboBox()
    self.time_end_minute.addItems([f"{m:02d}" for m in range(0, 60, 5)])
    self.time_end_minute.setCurrentText("55")
    self.time_end_minute.hide()

    self.time_warning = QLabel("")
    self.time_warning.setStyleSheet("color: #f97373; font-size: 12px; font-weight: 600;")
    self.time_warning.hide()
    times_layout.addWidget(self.time_warning)

    self.schedule_warning = QLabel("")
    self.schedule_warning.setStyleSheet("color: #f97373; font-size: 12px; font-weight: 600;")
    self.schedule_warning.hide()
    times_layout.addWidget(self.schedule_warning)

    top_grid.addWidget(times_card, 3)
    self.content_layout.addLayout(top_grid)

    # ================================================================
    # AREA C: CONFIGURAÇÃO DE LEGENDAS
    # ================================================================
    captions_card = SurfaceCard()
    captions_layout = QVBoxLayout(captions_card)
    captions_layout.setContentsMargins(18, 18, 18, 18)
    captions_layout.setSpacing(12)
    captions_layout.addWidget(SectionHeader(
      "C. Configuração de Legendas (Padrão e Individual por Vídeo)",
      "Escreva legendas e hashtags individualmente para cada vídeo, ou aplique uma legenda padrão sem sobrescrever as personalizadas.",
      "fa5s.closed-captioning",
      self._icon_color,
    ))

    default_cap_row = QHBoxLayout()
    default_cap_row.setSpacing(12)

    self.caption_input = HashtagTextEdit()
    self.caption_input.setPlaceholderText(
      "Legenda padrão / em massa (digite # para sugestões de hashtags)..."
    )
    self.caption_input.setMaximumHeight(68)
    default_cap_row.addWidget(self.caption_input, 3)

    bulk_btns_col = QVBoxLayout()
    bulk_btns_col.setSpacing(6)

    self.apply_default_empty_btn = QPushButton("Aplicar Padrão aos Vídeos Sem Legenda")
    self.apply_default_empty_btn.setProperty("class", "accent")
    self.apply_default_empty_btn.clicked.connect(lambda: self.apply_default_caption_to_cards(force=False))
    bulk_btns_col.addWidget(self.apply_default_empty_btn)

    self.overwrite_custom_check = QCheckBox("Autorizar sobrescrever legendas personalizadas")
    self.overwrite_custom_check.setChecked(False)
    bulk_btns_col.addWidget(self.overwrite_custom_check)

    self.apply_default_all_btn = QPushButton("Aplicar a Todos")
    self.apply_default_all_btn.clicked.connect(self._on_apply_to_all_clicked)
    bulk_btns_col.addWidget(self.apply_default_all_btn)

    default_cap_row.addLayout(bulk_btns_col, 2)
    captions_layout.addLayout(default_cap_row)

    prefix_row = QHBoxLayout()
    self.caption_preview = QLabel("Preview: (empty)")
    self.caption_preview.setProperty("class", "muted")
    prefix_row.addWidget(self.caption_preview, 1)

    self.prefix_caption_check = QCheckBox("Add 'Cre: <videoid>' prefix to caption")
    self.prefix_caption_check.setChecked(False)
    prefix_row.addWidget(self.prefix_caption_check)
    captions_layout.addLayout(prefix_row)

    self.per_video_captions_container = QWidget()
    self.per_video_captions_layout = QVBoxLayout(self.per_video_captions_container)
    self.per_video_captions_layout.setContentsMargins(0, 0, 0, 0)
    self.per_video_captions_layout.setSpacing(10)
    captions_layout.addWidget(self.per_video_captions_container)

    self.content_layout.addWidget(captions_card)

    # ================================================================
    # AREA D: DISTRIBUIÇÃO AUTOMÁTICA E PRÉVIA
    # ================================================================
    dist_card = SurfaceCard()
    dist_layout = QVBoxLayout(dist_card)
    dist_layout.setContentsMargins(18, 18, 18, 18)
    dist_layout.setSpacing(10)
    dist_layout.addWidget(SectionHeader(
      "D. Distribuição Automática",
      "Distribua os vídeos na ordem definida pelos dias e horários disponíveis e confira a prévia antes de avançar.",
      "fa5s.magic",
      self._icon_color,
    ))

    dist_btn_row = QHBoxLayout()
    self.generate_btn = QPushButton(" Distribuir Automaticamente nos Horários")
    self.generate_btn.setProperty("class", "accent")
    self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.generate_btn.setIcon(build_icon("fa5s.cogs", "#ffffff"))
    self.generate_btn.clicked.connect(self.distribute_requested.emit)
    dist_btn_row.addWidget(self.generate_btn)

    self.schedule_result_label = QLabel("")
    self.schedule_result_label.setProperty("class", "muted")
    self.schedule_result_label.setWordWrap(True)
    dist_btn_row.addWidget(self.schedule_result_label, 1)
    dist_layout.addLayout(dist_btn_row)

    self.distribution_preview_list = QListWidget()
    self.distribution_preview_list.setMinimumHeight(140)
    dist_layout.addWidget(self.distribution_preview_list)

    nav_row = QHBoxLayout()
    self.back_btn = QPushButton("← Voltar para Vídeos")
    self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.back_btn.clicked.connect(self.back_requested.emit)
    nav_row.addWidget(self.back_btn)

    nav_row.addStretch(1)

    self.continue_btn = QPushButton("Continuar para Revisão →")
    self.continue_btn.setProperty("class", "accent")
    self.continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.continue_btn.setIcon(build_icon("fa5s.arrow-right", "#ffffff"))
    self.continue_btn.clicked.connect(self.continue_requested.emit)
    nav_row.addWidget(self.continue_btn)
    dist_layout.addLayout(nav_row)

    self.content_layout.addWidget(dist_card)
    self._refresh_times_list()

  # ------------------------------------------------------------------
  # Time slots management
  # ------------------------------------------------------------------

  def _refresh_times_list(self) -> None:
    self._time_slots = sorted(set(self._time_slots))
    self.times_list_widget.clear()
    for t in self._time_slots:
      item = QListWidgetItem(f"🕒  {t}")
      item.setData(Qt.ItemDataRole.UserRole, t)
      self.times_list_widget.addItem(item)

  def get_time_slots(self) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for t in sorted(set(self._time_slots)):
      parts = t.split(":")
      if len(parts) == 2:
        try:
          result.append((int(parts[0]), int(parts[1])))
        except ValueError:
          pass
    return result

  def set_time_slots(self, slots: list[str]) -> None:
    if slots:
      self._time_slots = list(slots)
      self._refresh_times_list()

  def _on_add_time_slot(self) -> None:
    h = self.slot_hour_combo.currentText() or "09"
    m = self.slot_minute_combo.currentText() or "00"
    slot_str = f"{int(h):02d}:{int(m):02d}"
    if slot_str not in self._time_slots:
      self._time_slots.append(slot_str)
      self._refresh_times_list()

  def _on_time_slot_selected(self, text: str) -> None:
    clean = text.replace("🕒", "").strip()
    if ":" in clean:
      h, m = clean.split(":", 1)
      self.slot_hour_combo.setCurrentText(h.strip())
      self.slot_minute_combo.setCurrentText(m.strip())

  def _on_update_selected_time_slot(self) -> None:
    current_item = self.times_list_widget.currentItem()
    if current_item is None:
      return
    old_val = current_item.data(Qt.ItemDataRole.UserRole)
    h = self.slot_hour_combo.currentText() or "09"
    m = self.slot_minute_combo.currentText() or "00"
    new_val = f"{int(h):02d}:{int(m):02d}"
    if old_val in self._time_slots:
      self._time_slots.remove(old_val)
    if new_val not in self._time_slots:
      self._time_slots.append(new_val)
    self._refresh_times_list()

  def _on_remove_time_slot(self) -> None:
    current_item = self.times_list_widget.currentItem()
    if current_item is None:
      return
    val = current_item.data(Qt.ItemDataRole.UserRole)
    if val in self._time_slots:
      self._time_slots.remove(val)
      self._refresh_times_list()

  def _on_reset_default_times(self) -> None:
    self._time_slots = list(self.DEFAULT_TIMES)
    self._refresh_times_list()

  # ------------------------------------------------------------------
  # Weekdays & Specific calendar dates
  # ------------------------------------------------------------------

  def get_allowed_weekdays(self) -> set[int]:
    return {
      day_num
      for day_num, cb in self.weekday_checks.items()
      if cb.isChecked()
    }

  def set_allowed_weekdays(self, days: list[int]) -> None:
    day_set = set(days)
    for day_num, cb in self.weekday_checks.items():
      cb.setChecked(day_num in day_set)

  def _on_calendar_date_clicked(self, qdate: QDate) -> None:
    iso = f"{qdate.year():04d}-{qdate.month():02d}-{qdate.day():02d}"
    if iso in self._specific_dates:
      self._specific_dates.remove(iso)
    else:
      self._specific_dates.add(iso)
    self._update_specific_dates_label()

  def clear_specific_dates(self) -> None:
    self._specific_dates.clear()
    self._update_specific_dates_label()

  def get_specific_dates(self) -> set[str]:
    return set(self._specific_dates)

  def set_specific_dates(self, dates: list[str]) -> None:
    self._specific_dates = set(dates)
    self._update_specific_dates_label()

  def _update_specific_dates_label(self) -> None:
    if not self._specific_dates:
      self.specific_dates_label.setText(
        "Datas específicas: Todas do intervalo nos dias da semana marcados"
      )
    else:
      ordered = ", ".join(sorted(self._specific_dates))
      self.specific_dates_label.setText(
        f"Datas específicas selecionadas ({len(self._specific_dates)}): {ordered}"
      )

  # ------------------------------------------------------------------
  # Per-video captions
  # ------------------------------------------------------------------

  def populate_video_caption_cards(
    self,
    videos: list[dict[str, Any]],
    per_video_meta: dict[str, dict[str, str]],
    thumb_cache_dir: Path | None = None,
  ) -> None:
    while self.per_video_captions_layout.count():
      item = self.per_video_captions_layout.takeAt(0)
      w = item.widget()
      if w is not None:
        w.deleteLater()
    self._caption_cards.clear()

    for v in videos:
      fname = str(v["filename"])
      fpath = Path(str(v["path"]))
      meta = per_video_meta.get(fname, {})
      cap_text = str(meta.get("caption", ""))
      tag_text = str(meta.get("hashtags", ""))
      card = VideoCaptionRowCard(
        filename=fname,
        file_path=fpath,
        caption_text=cap_text,
        hashtags_text=tag_text,
        thumb_cache_dir=thumb_cache_dir,
      )
      card.caption_edited.connect(self.per_video_caption_changed.emit)
      self._caption_cards[fname] = card
      self.per_video_captions_layout.addWidget(card)

  def apply_default_caption_to_cards(self, force: bool = False) -> int:
    raw = self.caption_input.toPlainText().strip()
    words = raw.split()
    tags = [w for w in words if w.startswith("#")]
    body_words = [w for w in words if not w.startswith("#")]
    cap_part = " ".join(body_words).strip()
    tag_part = " ".join(tags).strip()

    updated = 0
    for card in self._caption_cards.values():
      if card.apply_default(cap_part, tag_part, force=force):
        updated += 1
    return updated

  def _on_apply_to_all_clicked(self) -> None:
    force = self.overwrite_custom_check.isChecked()
    self.apply_default_caption_to_cards(force=force)

  def get_video_full_caption(self, filename: str, fallback_caption: str = "") -> str:
    card = self._caption_cards.get(filename)
    if card is not None:
      full = card.full_caption()
      if full:
        return full
    return fallback_caption

  def populate_distribution_preview(self, preview_lines: list[str]) -> None:
    self.distribution_preview_list.clear()
    for line in preview_lines:
      self.distribution_preview_list.addItem(line)
