from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
  QAbstractItemView,
  QComboBox,
  QDateEdit,
  QDialog,
  QHBoxLayout,
  QHeaderView,
  QLabel,
  QLineEdit,
  QPushButton,
  QTableWidget,
  QTableWidgetItem,
  QVBoxLayout,
  QWidget,
)

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.pages.accounts_page import InlineStat
from gui.tables.video_table import build_status_badge
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon
from utils.video_media import VideoMediaUtils


class EditScheduledTaskDialog(QDialog):
  """Modal dialog to edit an individual scheduled publication before confirming."""

  def __init__(
    self,
    filename: str,
    caption: str,
    schedule_dt: datetime,
    parent: QWidget | None = None,
  ) -> None:
    super().__init__(parent)
    self.setWindowTitle(f"Editar Agendamento — {filename}")
    self.setModal(True)
    self.resize(480, 290)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(22, 22, 22, 22)
    layout.setSpacing(12)

    title_lbl = QLabel(f"Editar: {filename}")
    title_lbl.setProperty("class", "section-title")
    layout.addWidget(title_lbl)

    layout.addWidget(QLabel("Legenda completa (incluindo hashtags):"))
    self.caption_edit = QLineEdit(caption)
    layout.addWidget(self.caption_edit)

    dt_row = QHBoxLayout()
    dt_row.setSpacing(10)
    dt_row.addWidget(QLabel("Data:"))
    self.date_edit = QDateEdit(QDate(schedule_dt.year, schedule_dt.month, schedule_dt.day))
    self.date_edit.setCalendarPopup(True)
    self.date_edit.setDisplayFormat("dd MMM yyyy")
    dt_row.addWidget(self.date_edit)

    dt_row.addWidget(QLabel("Horário:"))
    self.hour_combo = QComboBox()
    self.hour_combo.addItems([f"{h:02d}" for h in range(24)])
    self.hour_combo.setCurrentText(f"{schedule_dt.hour:02d}")
    dt_row.addWidget(self.hour_combo)

    dt_row.addWidget(QLabel(":"))
    self.minute_combo = QComboBox()
    self.minute_combo.addItems([f"{m:02d}" for m in range(0, 60, 5)])
    self.minute_combo.setCurrentText(f"{(schedule_dt.minute // 5) * 5:02d}")
    dt_row.addWidget(self.minute_combo)
    dt_row.addStretch(1)
    layout.addLayout(dt_row)

    self.error_label = QLabel("")
    self.error_label.setStyleSheet("color: #f97373; font-weight: 600;")
    self.error_label.hide()
    layout.addWidget(self.error_label)

    layout.addStretch(1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    cancel_btn = QPushButton("Cancelar")
    cancel_btn.clicked.connect(self.reject)
    btn_row.addWidget(cancel_btn)

    self.save_btn = QPushButton("Salvar Alterações")
    self.save_btn.setProperty("class", "accent")
    self.save_btn.clicked.connect(self.accept)
    btn_row.addWidget(self.save_btn)
    layout.addLayout(btn_row)

  def get_updated_values(self) -> tuple[str, datetime]:
    qd = self.date_edit.date()
    h = int(self.hour_combo.currentText() or "9")
    m = int(self.minute_combo.currentText() or "0")
    return self.caption_edit.text().strip(), datetime(qd.year(), qd.month(), qd.day(), h, m)


class ReviewWizardPage(PageLayout):
  """Wizard Step 4: Review all scheduled publications, edit/delete individual items, and confirm to storage."""

  TITLE = "4. Revisar Publicações"
  DESCRIPTION = "Confira cada vídeo, legenda, data e horário antes de salvar e avançar para a execução."

  edit_task_requested = pyqtSignal(int)
  delete_task_requested = pyqtSignal(int)
  back_requested = pyqtSignal()
  confirm_requested = pyqtSignal()

  def __init__(self, icon_color: str) -> None:
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    summary_card = SurfaceCard()
    summary_layout = QVBoxLayout(summary_card)
    summary_layout.setContentsMargins(20, 18, 20, 18)
    summary_layout.setSpacing(14)
    summary_layout.addWidget(SectionHeader(
      "ETAPA 4 — REVISAR PUBLICAÇÕES PROGRAMADAS",
      "Revise os detalhes de todas as publicações desta campanha. Você pode editar ou remover itens individualmente antes de confirmar os agendamentos.",
      "fa5s.clipboard-check",
      self._icon_color,
    ))

    stats_row = QHBoxLayout()
    stats_row.setSpacing(28)
    self.stat_account = InlineStat("Conta Selecionada", "-", "Perfil de destino")
    self.stat_total_videos = InlineStat("Total de Vídeos", "0", "Carregados")
    self.stat_total_posts = InlineStat("Total de Publicações", "0", "Programadas")
    self.stat_first_slot = InlineStat("Primeiro Horário", "-", "Início da fila")
    self.stat_last_slot = InlineStat("Último Horário", "-", "Fim da fila")
    self.stat_days = InlineStat("Dias Selecionados", "0", "Dias com postagens")

    for st in (
      self.stat_account,
      self.stat_total_videos,
      self.stat_total_posts,
      self.stat_first_slot,
      self.stat_last_slot,
      self.stat_days,
    ):
      stats_row.addWidget(st)
    stats_row.addStretch(1)
    summary_layout.addLayout(stats_row)
    self.content_layout.addWidget(summary_card)

    table_card = SurfaceCard()
    table_layout = QVBoxLayout(table_card)
    table_layout.setContentsMargins(20, 18, 20, 18)
    table_layout.setSpacing(12)

    self.review_table = QTableWidget()
    self.review_table.setProperty("class", "grid-table")
    self.review_table.setColumnCount(9)
    self.review_table.setHorizontalHeaderLabels([
      "#",
      "Conta",
      "Miniatura",
      "Vídeo",
      "Legenda Completa",
      "Data",
      "Horário",
      "Status",
      "Ações",
    ])
    self.review_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.review_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.review_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.review_table.verticalHeader().setVisible(False)
    self.review_table.verticalHeader().setDefaultSectionSize(72)
    self.review_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.review_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    self.review_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    self.review_table.setColumnWidth(2, 106)
    self.review_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self.review_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    self.review_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    self.review_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
    self.review_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
    self.review_table.setColumnWidth(7, 136)
    self.review_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
    self.review_table.setColumnWidth(8, 128)
    self.review_table.setMinimumHeight(350)
    table_layout.addWidget(self.review_table, 1)

    nav_row = QHBoxLayout()
    self.back_btn = QPushButton("← Voltar e editar")
    self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.back_btn.clicked.connect(self.back_requested.emit)
    nav_row.addWidget(self.back_btn)

    nav_row.addStretch(1)

    self.confirm_btn = QPushButton(" Confirmar agendamentos →")
    self.confirm_btn.setProperty("class", "accent")
    self.confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.confirm_btn.setIcon(build_icon("fa5s.check-double", "#ffffff"))
    self.confirm_btn.clicked.connect(self.confirm_requested.emit)
    nav_row.addWidget(self.confirm_btn)

    table_layout.addLayout(nav_row)
    self.content_layout.addWidget(table_card, 1)

  def populate_review(
    self,
    username: str,
    total_videos_loaded: int,
    tasks_info: list[dict[str, Any]],
    thumb_cache_dir: Path | None = None,
  ) -> None:
    """Populate the review table and update summary counters."""
    self.stat_account.set_value(f"@{username}" if username else "-")
    self.stat_total_videos.set_value(str(total_videos_loaded))
    self.stat_total_posts.set_value(str(len(tasks_info)))

    if tasks_info:
      dts = [t["schedule_time"] for t in tasks_info if isinstance(t.get("schedule_time"), datetime)]
      if dts:
        first_dt = min(dts)
        last_dt = max(dts)
        unique_days = len({d.date() for d in dts})
        self.stat_first_slot.set_value(first_dt.strftime("%d/%m/%Y %H:%M"))
        self.stat_last_slot.set_value(last_dt.strftime("%d/%m/%Y %H:%M"))
        self.stat_days.set_value(f"{unique_days} dia(s)")
      else:
        self.stat_first_slot.set_value("-")
        self.stat_last_slot.set_value("-")
        self.stat_days.set_value("0")
    else:
      self.stat_first_slot.set_value("-")
      self.stat_last_slot.set_value("-")
      self.stat_days.set_value("0")

    self.review_table.setRowCount(len(tasks_info))
    for row_idx, info in enumerate(tasks_info):
      file_path = Path(str(info["file_path"]))
      dt: datetime | None = info.get("schedule_time")
      date_str = dt.strftime("%d/%m/%Y") if dt else "-"
      time_str = dt.strftime("%H:%M") if dt else "-"
      status_str = str(info.get("status", "Pending"))

      num_item = QTableWidgetItem(str(row_idx + 1))
      num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.review_table.setItem(row_idx, 0, num_item)

      acc_item = QTableWidgetItem(f"@{username}" if username else "-")
      acc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.review_table.setItem(row_idx, 1, acc_item)

      thumb_wrap = QWidget()
      t_lay = QHBoxLayout(thumb_wrap)
      t_lay.setContentsMargins(4, 4, 4, 4)
      t_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
      t_lbl = QLabel()
      t_lbl.setPixmap(VideoMediaUtils.get_thumbnail(file_path, thumb_cache_dir, 88, 56))
      t_lay.addWidget(t_lbl)
      self.review_table.setCellWidget(row_idx, 2, thumb_wrap)

      vid_item = QTableWidgetItem(file_path.name)
      vid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.review_table.setItem(row_idx, 3, vid_item)

      cap_item = QTableWidgetItem(str(info.get("caption", "")))
      cap_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
      self.review_table.setItem(row_idx, 4, cap_item)

      d_item = QTableWidgetItem(date_str)
      d_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.review_table.setItem(row_idx, 5, d_item)

      tm_item = QTableWidgetItem(time_str)
      tm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.review_table.setItem(row_idx, 6, tm_item)

      st_item = QTableWidgetItem(status_str)
      st_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.review_table.setItem(row_idx, 7, st_item)
      self.review_table.setCellWidget(row_idx, 7, build_status_badge(status_str))

      act_wrap = QWidget()
      a_lay = QHBoxLayout(act_wrap)
      a_lay.setContentsMargins(4, 4, 4, 4)
      a_lay.setSpacing(8)
      a_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

      edit_btn = QPushButton()
      edit_btn.setProperty("class", "icon-button")
      edit_btn.setToolTip("Editar este agendamento")
      edit_btn.setIcon(build_icon("fa5s.edit", self._icon_color))
      edit_btn.clicked.connect(lambda _c=False, r=row_idx: self.edit_task_requested.emit(r))
      a_lay.addWidget(edit_btn)

      del_btn = QPushButton()
      del_btn.setProperty("class", "danger")
      del_btn.setFixedSize(34, 34)
      del_btn.setToolTip("Excluir este agendamento")
      del_btn.setIcon(build_icon("fa5s.trash-alt", "#ffffff"))
      del_btn.clicked.connect(lambda _c=False, r=row_idx: self.delete_task_requested.emit(r))
      a_lay.addWidget(del_btn)

      self.review_table.setCellWidget(row_idx, 8, act_wrap)
      self.review_table.setRowHeight(row_idx, 72)
