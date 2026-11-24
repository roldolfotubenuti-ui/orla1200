from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
  QAbstractItemView,
  QComboBox,
  QFrame,
  QHBoxLayout,
  QHeaderView,
  QLabel,
  QPushButton,
  QTableWidget,
  QTableWidgetItem,
  QVBoxLayout,
  QWidget,
)

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.tables.folders_table import FoldersTable
from gui.tables.video_table import build_status_badge
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon
from utils.video_media import VideoMediaUtils


class VideoDropZone(QFrame):
  """Drag-and-drop area for loading video files or folders."""

  files_dropped = pyqtSignal(list)
  select_files_clicked = pyqtSignal()
  select_folder_clicked = pyqtSignal()

  def __init__(self, icon_color: str, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self._icon_color = icon_color
    self.setAcceptDrops(True)
    self.setProperty("class", "muted-card")
    self.setMinimumHeight(165)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(10)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    icon_lbl = QLabel()
    icon_lbl.setPixmap(build_icon("fa5s.cloud-upload-alt", icon_color).pixmap(42, 42))
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(icon_lbl)

    title_lbl = QLabel("Arraste e solte seus vídeos aqui")
    title_lbl.setProperty("class", "section-title")
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_lbl)

    sub_lbl = QLabel("Suporte a MP4 e formatos compatíveis (.mp4, .mov, .webm) • Seleção de múltiplos vídeos")
    sub_lbl.setProperty("class", "muted")
    sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(sub_lbl)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(12)
    btn_row.addStretch(1)

    self.select_videos_btn = QPushButton(" Selecionar vídeos")
    self.select_videos_btn.setProperty("class", "accent")
    self.select_videos_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.select_videos_btn.setIcon(build_icon("fa5s.file-video", "#ffffff"))
    self.select_videos_btn.clicked.connect(self.select_files_clicked.emit)
    btn_row.addWidget(self.select_videos_btn)

    self.select_folder_btn = QPushButton(" Carregar pasta")
    self.select_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.select_folder_btn.setIcon(build_icon("fa5s.folder-open", icon_color))
    self.select_folder_btn.clicked.connect(self.select_folder_clicked.emit)
    btn_row.addWidget(self.select_folder_btn)

    btn_row.addStretch(1)
    layout.addLayout(btn_row)

  def dragEnterEvent(self, event) -> None:  # noqa: N802
    if event.mimeData().hasUrls():
      event.acceptProposedAction()
    else:
      event.ignore()

  def dropEvent(self, event) -> None:  # noqa: N802
    paths: list[str] = []
    for url in event.mimeData().urls():
      local = url.toLocalFile()
      if local:
        paths.append(local)
    if paths:
      self.files_dropped.emit(paths)
      event.acceptProposedAction()


class VideosWizardPage(PageLayout):
  """Wizard Step 2: Load, validate, preview thumbnails, reorder, and remove videos."""

  TITLE = "2. Carregar Vídeos"
  DESCRIPTION = "Arraste arquivos MP4, confira miniaturas, duração, tamanho e organize a ordem de publicação."

  files_dropped = pyqtSignal(list)
  select_videos_requested = pyqtSignal()
  move_up_requested = pyqtSignal(int)
  move_down_requested = pyqtSignal(int)
  remove_video_requested = pyqtSignal(int)
  clear_videos_requested = pyqtSignal()
  back_requested = pyqtSignal()
  continue_requested = pyqtSignal()

  def __init__(self, icon_color: str) -> None:
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    header_card = SurfaceCard()
    header_layout = QVBoxLayout(header_card)
    header_layout.setContentsMargins(20, 18, 20, 18)
    header_layout.setSpacing(12)
    header_layout.addWidget(SectionHeader(
      "ETAPA 2 — CARREGAR VÍDEOS",
      "Adicione os vídeos da campanha, valide a compatibilidade dos arquivos e ajuste a ordem antes de configurar dias e horários.",
      "fa5s.photo-video",
      self._icon_color,
    ))

    self.drop_zone = VideoDropZone(self._icon_color)
    self.drop_zone.files_dropped.connect(self.files_dropped.emit)
    self.drop_zone.select_files_clicked.connect(self.select_videos_requested.emit)
    header_layout.addWidget(self.drop_zone)

    folder_bar = QHBoxLayout()
    folder_bar.setSpacing(10)
    folder_lbl = QLabel("Pasta rápida:")
    folder_lbl.setProperty("class", "muted")
    folder_bar.addWidget(folder_lbl)

    self.folder_dropdown = QComboBox()
    self.folder_dropdown.setMinimumWidth(340)
    folder_bar.addWidget(self.folder_dropdown, 1)

    self.browse_button = QPushButton(" Escolher Pasta")
    self.browse_button.setIcon(build_icon("fa5s.folder-open", self._icon_color))
    folder_bar.addWidget(self.browse_button)

    self.scan_button = QPushButton(" Escanear Pasta")
    self.scan_button.setIcon(build_icon("fa5s.search", self._icon_color))
    folder_bar.addWidget(self.scan_button)

    self.drop_zone.select_folder_clicked.connect(self.browse_button.click)
    header_layout.addLayout(folder_bar)

    # Hidden compatibility widgets for FolderControllerMixin
    self.add_folder_btn = QPushButton("Add")
    self.add_folder_btn.hide()
    self.folders_table = FoldersTable()
    self.folders_table.hide()

    self.content_layout.addWidget(header_card)

    list_card = SurfaceCard()
    list_layout = QVBoxLayout(list_card)
    list_layout.setContentsMargins(20, 18, 20, 18)
    list_layout.setSpacing(12)

    meta_row = QHBoxLayout()
    self.total_loaded_label = QLabel("Total de vídeos carregados: 0")
    self.total_loaded_label.setProperty("class", "section-title")
    meta_row.addWidget(self.total_loaded_label)

    self.validation_summary_label = QLabel("")
    self.validation_summary_label.setProperty("class", "muted")
    meta_row.addWidget(self.validation_summary_label)
    meta_row.addStretch(1)

    self.clear_all_btn = QPushButton(" Limpar Lista")
    self.clear_all_btn.setIcon(build_icon("fa5s.trash", "#f97373"))
    self.clear_all_btn.clicked.connect(self.clear_videos_requested.emit)
    meta_row.addWidget(self.clear_all_btn)
    list_layout.addLayout(meta_row)

    self.loaded_videos_table = QTableWidget()
    self.loaded_videos_table.setProperty("class", "grid-table")
    self.loaded_videos_table.setColumnCount(7)
    self.loaded_videos_table.setHorizontalHeaderLabels([
      "Ordem",
      "Miniatura",
      "Nome do Arquivo",
      "Duração",
      "Tamanho",
      "Validação / Status",
      "Ações",
    ])
    self.loaded_videos_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.loaded_videos_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.loaded_videos_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.loaded_videos_table.verticalHeader().setVisible(False)
    self.loaded_videos_table.verticalHeader().setDefaultSectionSize(72)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    self.loaded_videos_table.setColumnWidth(1, 110)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
    self.loaded_videos_table.setColumnWidth(5, 190)
    self.loaded_videos_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
    self.loaded_videos_table.setColumnWidth(6, 150)
    self.loaded_videos_table.setMinimumHeight(320)
    list_layout.addWidget(self.loaded_videos_table, 1)

    nav_row = QHBoxLayout()
    self.back_btn = QPushButton("← Voltar para Contas")
    self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.back_btn.clicked.connect(self.back_requested.emit)
    nav_row.addWidget(self.back_btn)

    nav_row.addStretch(1)

    self.continue_btn = QPushButton("Continuar para Configuração →")
    self.continue_btn.setProperty("class", "accent")
    self.continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.continue_btn.setIcon(build_icon("fa5s.arrow-right", "#ffffff"))
    self.continue_btn.clicked.connect(self.continue_requested.emit)
    nav_row.addWidget(self.continue_btn)

    list_layout.addLayout(nav_row)
    self.content_layout.addWidget(list_card, 1)

  def populate_loaded_videos(
    self,
    items: list[dict[str, Any]],
    thumb_cache_dir: Path | None = None,
  ) -> None:
    """Populate the loaded videos table with thumbnails, duration, size, validation, and reorder actions."""
    self.loaded_videos_table.setRowCount(len(items))
    valid_count = 0
    invalid_count = 0

    for row_idx, item in enumerate(items):
      path = Path(str(item["path"]))
      is_valid = bool(item.get("is_valid", True))
      if is_valid:
        valid_count += 1
      else:
        invalid_count += 1

      order_item = QTableWidgetItem(f"#{row_idx + 1}")
      order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.loaded_videos_table.setItem(row_idx, 0, order_item)

      thumb_container = QWidget()
      t_lay = QHBoxLayout(thumb_container)
      t_lay.setContentsMargins(6, 4, 6, 4)
      t_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
      thumb_lbl = QLabel()
      thumb_lbl.setPixmap(VideoMediaUtils.get_thumbnail(path, thumb_cache_dir, 88, 56))
      t_lay.addWidget(thumb_lbl)
      self.loaded_videos_table.setCellWidget(row_idx, 1, thumb_container)

      name_item = QTableWidgetItem(str(item.get("filename", path.name)))
      name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
      self.loaded_videos_table.setItem(row_idx, 2, name_item)

      dur_item = QTableWidgetItem(str(item.get("duration_human", "00:05")))
      dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.loaded_videos_table.setItem(row_idx, 3, dur_item)

      size_item = QTableWidgetItem(str(item.get("size_human", "")))
      size_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.loaded_videos_table.setItem(row_idx, 4, size_item)

      val_msg = str(item.get("validation_message", "Compatível"))
      role_status = "Published" if is_valid else "Failed"
      val_item = QTableWidgetItem(val_msg)
      val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      self.loaded_videos_table.setItem(row_idx, 5, val_item)
      badge = build_status_badge(role_status)
      lbl = badge.findChild(QLabel)
      if lbl is not None:
        lbl.setText(val_msg)
      self.loaded_videos_table.setCellWidget(row_idx, 5, badge)

      actions_widget = QWidget()
      a_lay = QHBoxLayout(actions_widget)
      a_lay.setContentsMargins(4, 4, 4, 4)
      a_lay.setSpacing(6)
      a_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

      up_btn = QPushButton("↑")
      up_btn.setFixedSize(32, 32)
      up_btn.setToolTip("Mover para cima")
      up_btn.setEnabled(row_idx > 0)
      up_btn.clicked.connect(lambda _c=False, r=row_idx: self.move_up_requested.emit(r))
      a_lay.addWidget(up_btn)

      down_btn = QPushButton("↓")
      down_btn.setFixedSize(32, 32)
      down_btn.setToolTip("Mover para baixo")
      down_btn.setEnabled(row_idx < len(items) - 1)
      down_btn.clicked.connect(lambda _c=False, r=row_idx: self.move_down_requested.emit(r))
      a_lay.addWidget(down_btn)

      rm_btn = QPushButton("✕")
      rm_btn.setFixedSize(32, 32)
      rm_btn.setProperty("class", "danger")
      rm_btn.setToolTip("Remover vídeo")
      rm_btn.clicked.connect(lambda _c=False, r=row_idx: self.remove_video_requested.emit(r))
      a_lay.addWidget(rm_btn)

      self.loaded_videos_table.setCellWidget(row_idx, 6, actions_widget)
      self.loaded_videos_table.setRowHeight(row_idx, 72)

    self.total_loaded_label.setText(f"Total de vídeos carregados: {len(items)}")
    if invalid_count > 0:
      self.validation_summary_label.setText(
        f"• {valid_count} compatível(is) | ⚠ {invalid_count} incompatível(is)"
      )
      self.validation_summary_label.setStyleSheet("color: #f97373; font-weight: 600;")
    else:
      self.validation_summary_label.setText(f"• {valid_count} vídeo(s) pronto(s) para agendamento")
      self.validation_summary_label.setStyleSheet("color: #22c55e; font-weight: 600;")
