from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QMimeData, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QDrag, QFontMetrics
from PyQt6.QtWidgets import (
  QFrame,
  QHBoxLayout,
  QLabel,
  QMenu,
  QProgressBar,
  QPushButton,
  QScrollArea,
  QSizePolicy,
  QStackedWidget,
  QVBoxLayout,
  QWidget,
)

from gui.dialogs.schedule_popup import TikTokScheduleDialog
from gui.dialogs.studio_dialogs import BatchScheduleDialog, CaptionEditDialog, PublishConfirmDialog
from gui.widgets.icon import build_icon
from gui.widgets.inline_caption_editor import InlineCaptionEditor
from gui.widgets.tiktok_style import (
  TT_BG,
  TT_BG_ALT,
  TT_BG_HOVER,
  TT_BORDER,
  TT_GREEN,
  TT_RED,
  TT_TEXT,
  TT_TEXT_2,
  TT_TEXT_DISABLED,
  ChipButton,
  hline,
  tt_base_stylesheet,
)
from utils.video_media import VideoMediaUtils

# Column widths of the video list (header and rows share them)
COL_IDX = 44
COL_SCHED = 210
COL_VIS = 135
COL_ACT = 76
ROW_H_READ = 76
ROW_H_EDIT = 108

VISIBILITY_OPTIONS = [
  ("Público", "fa5.eye"),
  ("Amigos", "fa5s.user-friends"),
  ("Privado", "fa5s.lock"),
]
VISIBILITY_ICON = {name: icon for name, icon in VISIBILITY_OPTIONS}
MIME_ROW = "application/x-tks-studio-row"


# ======================================================================
# Header & sidebar
# ======================================================================
class StudioHeader(QFrame):
  """Top bar: TikTok Studio wordmark + active account."""

  switch_account_requested = pyqtSignal()
  logs_requested = pyqtSignal()

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("ttHeader")
    self.setFixedHeight(56)
    lay = QHBoxLayout(self)
    lay.setContentsMargins(20, 0, 20, 0)
    lay.setSpacing(8)

    logo = QLabel()
    logo.setPixmap(build_icon("fa5b.tiktok", TT_TEXT).pixmap(22, 22))
    lay.addWidget(logo)
    word = QLabel("TikTok")
    word.setStyleSheet("font-size: 21px; font-weight: 800; letter-spacing: -0.5px;")
    lay.addWidget(word)
    badge = QLabel("Studio")
    badge.setStyleSheet(
      "background: #161823; color: #FFFFFF; font-size: 11px; font-weight: 700;"
      "border-radius: 3px; padding: 1px 6px; border-right: 2px solid #FE2C55;"
    )
    lay.addWidget(badge)
    tks = QLabel("  ·  TKS Engine")
    tks.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 12px; font-weight: 600;")
    lay.addWidget(tks)
    lay.addStretch(1)

    self.logs_btn = QPushButton(" Logs")
    self.logs_btn.setObjectName("ttSecondary")
    self.logs_btn.setIcon(build_icon("fa5s.stream", TT_TEXT))
    self.logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.logs_btn.clicked.connect(self.logs_requested.emit)
    lay.addWidget(self.logs_btn)

    self.account_btn = QPushButton()
    self.account_btn.setObjectName("ttChip")
    self.account_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.account_btn.setToolTip("Trocar conta")
    self.account_btn.clicked.connect(self.switch_account_requested.emit)
    acc_l = QHBoxLayout(self.account_btn)
    acc_l.setContentsMargins(8, 0, 8, 0)
    acc_l.setSpacing(8)
    self._avatar = QLabel("?")
    self._avatar.setFixedSize(28, 28)
    self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._avatar.setStyleSheet(
      "background: #FE2C55; color: #FFFFFF; border-radius: 14px; font-weight: 700; font-size: 13px;"
    )
    self._avatar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    acc_l.addWidget(self._avatar)
    col = QVBoxLayout()
    col.setSpacing(0)
    self._acc_name = QLabel("Nenhuma conta")
    self._acc_name.setStyleSheet("font-size: 13px; font-weight: 700;")
    self._acc_name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    self._acc_status = QLabel("")
    self._acc_status.setStyleSheet(f"font-size: 11px; color: {TT_GREEN};")
    self._acc_status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    col.addWidget(self._acc_name)
    col.addWidget(self._acc_status)
    acc_l.addLayout(col)
    self.account_btn.setFixedHeight(44)
    self.account_btn.setMinimumWidth(170)
    lay.addWidget(self.account_btn)

  def set_account(self, username: str, status: str = "Sessão salva", ok: bool = True) -> None:
    self._acc_name.setText(f"@{username}" if username else "Nenhuma conta")
    self._avatar.setText((username[:1] or "?").upper())
    self._acc_status.setText(("● " + status) if username else "")
    self._acc_status.setStyleSheet(f"font-size: 11px; color: {TT_GREEN if ok else TT_RED};")


class SidebarItem(QPushButton):
  def __init__(self, icon: str, text: str, enabled: bool, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("ttNavItem")
    self.setFixedHeight(38)
    self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
    color = TT_TEXT if enabled else "#A3A3A3"
    lay = QHBoxLayout(self)
    lay.setContentsMargins(12, 0, 8, 0)
    lay.setSpacing(12)
    ic = QLabel()
    ic.setPixmap(build_icon(icon, color).pixmap(16, 16))
    ic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    lay.addWidget(ic)
    tx = QLabel(text)
    tx.setWordWrap(True)
    tx.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {color};")
    tx.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    lay.addWidget(tx, 1)
    if not enabled:
      self.setToolTip("Disponível apenas no TikTok Studio oficial")


class StudioSidebar(QFrame):
  """Left navigation replicating the official TikTok Studio grouping."""

  upload_clicked = pyqtSignal()
  publications_clicked = pyqtSignal()
  switch_account_clicked = pyqtSignal()

  SECTIONS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("GERENCIAR", [
      ("fa5s.home", "Início", ""),
      ("fa5.folder", "Publicações", "publications"),
      ("fa5s.chart-line", "Análise", ""),
      ("fa5.comment-dots", "Comentários", ""),
    ]),
    ("CRESCIMENTO", [
      ("fa5.lightbulb", "Inspiração", ""),
      ("fa5s.graduation-cap", "Academia de Criadores", ""),
    ]),
    ("FERRAMENTAS", [
      ("fa5s.dollar-sign", "Monetização", ""),
      ("fa5s.music", "Sons isentos de royalties", ""),
      ("fa5s.cut", "Smart Split", ""),
    ]),
  ]

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("ttSidebar")
    self.setFixedWidth(220)
    lay = QVBoxLayout(self)
    lay.setContentsMargins(14, 16, 14, 14)
    lay.setSpacing(2)

    self.upload_btn = QPushButton()
    self.upload_btn.setObjectName("ttUploadNav")
    self.upload_btn.setFixedHeight(38)
    self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    up_l = QHBoxLayout(self.upload_btn)
    up_l.setContentsMargins(12, 0, 12, 0)
    up_l.setSpacing(10)
    up_ic = QLabel()
    up_ic.setPixmap(build_icon("fa5s.plus-square", "#FFFFFF").pixmap(15, 15))
    up_ic.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    up_l.addWidget(up_ic)
    up_tx = QLabel("Carregar")
    up_tx.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700;")
    up_tx.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    up_l.addWidget(up_tx, 1)
    up_ch = QLabel()
    up_ch.setPixmap(build_icon("fa5s.chevron-down", "#FFFFFF").pixmap(9, 9))
    up_ch.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    up_l.addWidget(up_ch)
    self.upload_btn.clicked.connect(self.upload_clicked.emit)
    lay.addWidget(self.upload_btn)
    lay.addSpacing(14)

    for title, items in self.SECTIONS:
      sec = QLabel(title)
      sec.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 11px; font-weight: 600; padding: 8px 12px 4px 12px;")
      lay.addWidget(sec)
      for icon, text, action in items:
        item = SidebarItem(icon, text, enabled=bool(action))
        if action == "publications":
          item.clicked.connect(self.publications_clicked.emit)
          item.setToolTip("Fila de publicação, status e execução")
        lay.addWidget(item)
      lay.addSpacing(4)

    lay.addStretch(1)
    lay.addWidget(hline())
    lay.addSpacing(6)
    back = SidebarItem("fa5s.exchange-alt", "Trocar conta", enabled=True)
    back.clicked.connect(self.switch_account_clicked.emit)
    lay.addWidget(back)
    foot = QLabel("TKS Engine 2.0 · local")
    foot.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 11px; padding: 6px 12px 0 12px;")
    lay.addWidget(foot)


# ======================================================================
# Upload (empty) view
# ======================================================================
class SpecItem(QWidget):
  def __init__(self, icon: str, title: str, desc: str, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    lay = QHBoxLayout(self)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    ic = QLabel()
    ic.setPixmap(build_icon(icon, "#6B6B6B").pixmap(16, 16))
    ic.setAlignment(Qt.AlignmentFlag.AlignTop)
    ic.setContentsMargins(0, 2, 0, 0)
    lay.addWidget(ic)
    col = QVBoxLayout()
    col.setSpacing(3)
    t = QLabel(title)
    t.setStyleSheet("font-size: 14px; font-weight: 600;")
    d = QLabel(desc)
    d.setWordWrap(True)
    d.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
    col.addWidget(t)
    col.addWidget(d)
    col.addStretch(1)
    lay.addLayout(col, 1)


class StudioDropZone(QFrame):
  files_dropped = pyqtSignal(list)
  select_videos_clicked = pyqtSignal()
  select_folder_clicked = pyqtSignal()

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("ttDropZone")
    self.setAcceptDrops(True)
    self.setMinimumHeight(300)
    lay = QVBoxLayout(self)
    lay.setContentsMargins(24, 24, 24, 24)
    lay.setSpacing(6)
    lay.addStretch(1)
    ic = QLabel()
    ic.setPixmap(build_icon("fa5s.cloud-upload-alt", "#A8A8A8").pixmap(48, 48))
    ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(ic)
    lay.addSpacing(6)
    t = QLabel("Selecione o vídeo a enviar")
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    t.setStyleSheet("font-size: 18px; font-weight: 700;")
    lay.addWidget(t)
    s = QLabel("Ou arraste e solte aqui — vários arquivos ou uma pasta inteira")
    s.setAlignment(Qt.AlignmentFlag.AlignCenter)
    s.setStyleSheet("font-size: 14px; color: #57575C;")
    lay.addWidget(s)
    lay.addSpacing(14)
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addStretch(1)
    self.select_btn = QPushButton("Selecionar vídeos")
    self.select_btn.setObjectName("ttPrimary")
    self.select_btn.setFixedWidth(200)
    self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.select_btn.clicked.connect(self.select_videos_clicked.emit)
    row.addWidget(self.select_btn)
    self.folder_btn = QPushButton(" Carregar pasta")
    self.folder_btn.setObjectName("ttSecondary")
    self.folder_btn.setIcon(build_icon("fa5.folder-open", TT_TEXT))
    self.folder_btn.setMinimumHeight(36)
    self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.folder_btn.clicked.connect(self.select_folder_clicked.emit)
    row.addWidget(self.folder_btn)
    row.addStretch(1)
    lay.addLayout(row)
    lay.addStretch(1)

  def dragEnterEvent(self, event) -> None:  # noqa: N802
    if event.mimeData().hasUrls():
      self.setProperty("dragging", True)
      self.style().unpolish(self)
      self.style().polish(self)
      event.acceptProposedAction()
    else:
      event.ignore()

  def dragLeaveEvent(self, event) -> None:  # noqa: N802
    self.setProperty("dragging", False)
    self.style().unpolish(self)
    self.style().polish(self)

  def dropEvent(self, event) -> None:  # noqa: N802
    self.dragLeaveEvent(event)
    paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
    if paths:
      self.files_dropped.emit(paths)
      event.acceptProposedAction()


# ======================================================================
# Video row
# ======================================================================
class StudioVideoRow(QFrame):
  """One line of the "Carregar vídeo" list (reference images 2/3/4)."""

  caption_saved = pyqtSignal(int, str)
  schedule_clicked = pyqtSignal(int)
  visibility_picked = pyqtSignal(int, str)
  edit_clicked = pyqtSignal(int)
  delete_clicked = pyqtSignal(int)
  substitute_clicked = pyqtSignal(int)
  edit_mode_changed = pyqtSignal(int, bool)

  def __init__(self, index: int, item: dict[str, Any], thumb_dir: Path | None, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.index = index
    self.item = item
    self.setObjectName("ttRow")
    self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    self.setFixedHeight(ROW_H_READ)

    lay = QHBoxLayout(self)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    # --- index + drag handle
    idx_w = QWidget()
    idx_w.setFixedWidth(COL_IDX)
    idx_l = QHBoxLayout(idx_w)
    idx_l.setContentsMargins(4, 0, 0, 0)
    idx_l.setSpacing(2)
    self.handle = QLabel()
    self.handle.setPixmap(build_icon("fa5s.grip-vertical", "#A8A8A8").pixmap(10, 14))
    self.handle.setToolTip("Arraste para reordenar")
    self.handle.setCursor(Qt.CursorShape.OpenHandCursor)
    self.handle.setFixedWidth(12)
    self.handle.setVisible(False)
    idx_l.addWidget(self.handle)
    self.idx_lbl = QLabel(str(index + 1))
    self.idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.idx_lbl.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 13px;")
    idx_l.addWidget(self.idx_lbl, 1)
    lay.addWidget(idx_w)

    # --- thumbnail
    thumb = QLabel()
    thumb.setFixedSize(42, 56)
    thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    thumb.setStyleSheet(f"background: {TT_BG_HOVER}; border-radius: 2px;")
    try:
      pm = VideoMediaUtils.get_thumbnail(Path(str(item.get("path", ""))), thumb_dir, 42, 56)
      if pm is not None and not pm.isNull():
        thumb.setPixmap(pm)
    except Exception:
      pass
    lay.addWidget(thumb, 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addSpacing(14)

    # --- caption column (read / edit)
    self.cap_stack = QStackedWidget()
    read = QWidget()
    rl = QVBoxLayout(read)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(2)
    rl.addStretch(1)
    self.sub_btn = QPushButton("Substituir arquivo")
    self.sub_btn.setObjectName("ttLink")
    self.sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.sub_btn.setFixedHeight(16)
    self.sub_btn.clicked.connect(lambda: self.substitute_clicked.emit(self.index))
    sp = self.sub_btn.sizePolicy()
    sp.setRetainSizeWhenHidden(True)
    self.sub_btn.setSizePolicy(sp)
    self.sub_btn.setVisible(False)
    rl.addWidget(self.sub_btn, 0, Qt.AlignmentFlag.AlignLeft)
    name_row = QHBoxLayout()
    name_row.setSpacing(6)
    self.name_lbl = QLabel()
    self.name_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {TT_TEXT};")
    self.name_lbl.setCursor(Qt.CursorShape.IBeamCursor)
    self.name_lbl.mousePressEvent = lambda _e: self.enter_edit()  # type: ignore[assignment]
    name_row.addWidget(self.name_lbl, 0)
    self.pen_btn = QPushButton()
    self.pen_btn.setIcon(build_icon("fa5s.pen", TT_TEXT_2))
    self.pen_btn.setIconSize(QSize(11, 11))
    self.pen_btn.setFixedSize(18, 18)
    self.pen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pen_btn.setToolTip("Editar legenda aqui")
    self.pen_btn.clicked.connect(self.enter_edit)
    sp2 = self.pen_btn.sizePolicy()
    sp2.setRetainSizeWhenHidden(True)
    self.pen_btn.setSizePolicy(sp2)
    self.pen_btn.setVisible(False)
    name_row.addWidget(self.pen_btn)
    name_row.addStretch(1)
    rl.addLayout(name_row)
    self.meta_lbl = QLabel()
    self.meta_lbl.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
    rl.addWidget(self.meta_lbl)
    rl.addStretch(1)
    self.cap_stack.addWidget(read)

    edit_w = QWidget()
    el = QVBoxLayout(edit_w)
    el.setContentsMargins(0, 8, 24, 8)
    self.editor = InlineCaptionEditor(initial_text=str(item.get("caption", "")))
    self.editor.caption_saved.connect(self._on_saved)
    self.editor.editing_cancelled.connect(self.leave_edit)
    el.addWidget(self.editor)
    self.cap_stack.addWidget(edit_w)
    lay.addWidget(self.cap_stack, 1)

    # --- schedule
    sched_w = QWidget()
    sched_w.setFixedWidth(COL_SCHED)
    sl = QHBoxLayout(sched_w)
    sl.setContentsMargins(0, 0, 0, 0)
    sl.setAlignment(Qt.AlignmentFlag.AlignLeft)
    self.sched_btn = ChipButton("fa5.calendar", "Publicar agora", chevron=True)
    self.sched_btn.setMinimumWidth(165)
    self.sched_btn.clicked.connect(lambda: self.schedule_clicked.emit(self.index))
    sl.addWidget(self.sched_btn)
    lay.addWidget(sched_w)

    # --- visibility
    vis_w = QWidget()
    vis_w.setFixedWidth(COL_VIS)
    vl = QHBoxLayout(vis_w)
    vl.setContentsMargins(0, 0, 0, 0)
    vl.setAlignment(Qt.AlignmentFlag.AlignLeft)
    self.vis_btn = ChipButton("fa5.eye", "Público", chevron=True)
    self.vis_btn.setMinimumWidth(95)
    self.vis_btn.clicked.connect(self._open_visibility_menu)
    vl.addWidget(self.vis_btn)
    lay.addWidget(vis_w)

    # --- actions
    act_w = QWidget()
    act_w.setFixedWidth(COL_ACT)
    al = QHBoxLayout(act_w)
    al.setContentsMargins(0, 0, 8, 0)
    al.setSpacing(6)
    self.edit_btn = QPushButton()
    self.edit_btn.setObjectName("ttIconBtn")
    self.edit_btn.setIcon(build_icon("fa5s.pen", TT_TEXT))
    self.edit_btn.setIconSize(QSize(13, 13))
    self.edit_btn.setToolTip("Editar legenda e hashtags")
    self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.index))
    al.addWidget(self.edit_btn)
    self.del_btn = QPushButton()
    self.del_btn.setObjectName("ttIconBtn")
    self.del_btn.setIcon(build_icon("fa5.trash-alt", TT_TEXT))
    self.del_btn.setIconSize(QSize(13, 13))
    self.del_btn.setToolTip("Remover da lista (o arquivo não é apagado)")
    self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.index))
    al.addWidget(self.del_btn)
    al.addStretch(1)
    lay.addWidget(act_w)

    self.refresh()

  # ------------------------------------------------------------------
  def refresh(self) -> None:
    it = self.item
    caption = str(it.get("caption") or "")
    filename = str(it.get("filename", ""))
    shown = caption or Path(filename).stem
    fm = QFontMetrics(self.name_lbl.font())
    self.name_lbl.setText(fm.elidedText(shown.replace("\n", " "), Qt.TextElideMode.ElideRight, 420))
    self.name_lbl.setToolTip(f"{filename}\n\n{caption}" if caption else filename)
    meta = [str(it.get("duration_str") or "00:00")]
    if it.get("size_human"):
      meta.append(str(it["size_human"]))
    if not it.get("is_valid", True):
      meta.append("⚠ incompatível")
    elif it.get("status_note"):
      meta.append(str(it["status_note"]))
    self.meta_lbl.setText("  ·  ".join(meta))

    sched = it.get("schedule_dt")
    if isinstance(sched, str) and sched:
      try:
        sched = datetime.fromisoformat(sched)
      except Exception:
        pass
    if isinstance(sched, datetime):
      self.sched_btn.set_label(sched.strftime("%d/%m/%Y %H:%M"), bold=True)
    else:
      self.sched_btn.set_label("Publicar agora")
    vis = str(it.get("visibility") or "Público")
    self.vis_btn.set_label(vis)
    self.vis_btn.set_icon_name(VISIBILITY_ICON.get(vis, "fa5.eye"))

  def enter_edit(self) -> None:
    self.editor.set_text(str(self.item.get("caption") or ""))
    self.cap_stack.setCurrentIndex(1)
    self.setFixedHeight(ROW_H_EDIT)
    self.setProperty("editing", True)
    self._repolish()
    self.editor.focus_editor()
    self.edit_mode_changed.emit(self.index, True)

  def leave_edit(self) -> None:
    self.cap_stack.setCurrentIndex(0)
    self.setFixedHeight(ROW_H_READ)
    self.setProperty("editing", False)
    self._repolish()
    self.edit_mode_changed.emit(self.index, False)

  def is_editing(self) -> bool:
    return self.cap_stack.currentIndex() == 1

  def _on_saved(self, text: str) -> None:
    self.item["caption"] = text
    self.refresh()
    self.leave_edit()
    self.caption_saved.emit(self.index, text)

  def _open_visibility_menu(self) -> None:
    menu = QMenu(self)
    current = str(self.item.get("visibility") or "Público")
    for name, icon in VISIBILITY_OPTIONS:
      act = menu.addAction(build_icon(icon, TT_TEXT), name)
      act.setCheckable(True)
      act.setChecked(name == current)
      act.triggered.connect(lambda _c=False, n=name: self.visibility_picked.emit(self.index, n))
    menu.exec(self.vis_btn.mapToGlobal(QPoint(0, self.vis_btn.height() + 2)))

  def _repolish(self) -> None:
    self.style().unpolish(self)
    self.style().polish(self)

  # hover affordances ---------------------------------------------------
  def enterEvent(self, event) -> None:  # noqa: N802
    self.handle.setVisible(True)
    self.sub_btn.setVisible(True)
    self.pen_btn.setVisible(True)
    super().enterEvent(event)

  def leaveEvent(self, event) -> None:  # noqa: N802
    self.handle.setVisible(False)
    self.sub_btn.setVisible(False)
    self.pen_btn.setVisible(False)
    super().leaveEvent(event)

  # drag to reorder -----------------------------------------------------
  def mousePressEvent(self, event) -> None:  # noqa: N802
    if event.button() == Qt.MouseButton.LeftButton and self.handle.isVisible() and self.handle.geometry().adjusted(-4, -20, 4, 20).contains(
      self.handle.parentWidget().mapFrom(self, event.position().toPoint())
    ):
      drag = QDrag(self)
      mime = QMimeData()
      mime.setData(MIME_ROW, str(self.index).encode())
      drag.setMimeData(mime)
      drag.setPixmap(self.grab().scaledToWidth(min(600, self.width())))
      drag.setHotSpot(QPoint(20, ROW_H_READ // 2))
      drag.exec(Qt.DropAction.MoveAction)
      return
    super().mousePressEvent(event)


class RowsContainer(QWidget):
  """Holds the rows and handles drop-to-reorder."""

  reorder = pyqtSignal(int, int)

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setAcceptDrops(True)
    self.vbox = QVBoxLayout(self)
    self.vbox.setContentsMargins(0, 0, 0, 0)
    self.vbox.setSpacing(0)
    self.vbox.addStretch(1)
    self._indicator = QFrame(self)
    self._indicator.setFixedHeight(2)
    self._indicator.setStyleSheet(f"background: {TT_RED};")
    self._indicator.hide()

  def rows(self) -> list[StudioVideoRow]:
    out = []
    for i in range(self.vbox.count()):
      w = self.vbox.itemAt(i).widget()
      if isinstance(w, StudioVideoRow):
        out.append(w)
    return out

  def _target_index(self, y: int) -> int:
    rows = self.rows()
    for r in rows:
      if y < r.y() + r.height() / 2:
        return r.index
    return len(rows)

  def dragEnterEvent(self, e) -> None:  # noqa: N802
    if e.mimeData().hasFormat(MIME_ROW):
      e.acceptProposedAction()
    else:
      e.ignore()

  def dragMoveEvent(self, e) -> None:  # noqa: N802
    if not e.mimeData().hasFormat(MIME_ROW):
      return
    tgt = self._target_index(int(e.position().y()))
    rows = self.rows()
    y = rows[tgt].y() if tgt < len(rows) else (rows[-1].y() + rows[-1].height() if rows else 0)
    self._indicator.setGeometry(0, max(0, y - 1), self.width(), 2)
    self._indicator.show()
    self._indicator.raise_()
    e.acceptProposedAction()

  def dragLeaveEvent(self, e) -> None:  # noqa: N802
    self._indicator.hide()

  def dropEvent(self, e) -> None:  # noqa: N802
    self._indicator.hide()
    if not e.mimeData().hasFormat(MIME_ROW):
      return
    try:
      src = int(bytes(e.mimeData().data(MIME_ROW)).decode())
    except ValueError:
      return
    tgt = self._target_index(int(e.position().y()))
    if tgt > src:
      tgt -= 1
    if tgt != src:
      self.reorder.emit(src, tgt)
    e.acceptProposedAction()


class PublicationRowWidget(QFrame):
  """Single row inside the TikTok Studio 'Publicações' tab."""

  def __init__(self, item: dict[str, Any], thumb_cache_dir: Path | None = None, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("ttRow")
    self.setFixedHeight(68)
    self.item = item
    lay = QHBoxLayout(self)
    lay.setContentsMargins(20, 0, 20, 0)
    lay.setSpacing(14)

    # 1. Thumbnail
    thumb = QLabel()
    thumb.setFixedSize(38, 50)
    thumb.setStyleSheet("background: #000000; border-radius: 4px;")
    thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    fn = str(item.get("file") or item.get("filename") or "")
    fp = item.get("file_path") or item.get("path")
    loaded = False
    if fp and thumb_cache_dir:
      try:
        p = VideoMediaUtils.cached_thumbnail_path(Path(fp), thumb_cache_dir)
        if p and p.exists():
          pm = QPixmap(str(p)).scaled(38, 50, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
          thumb.setPixmap(pm)
          loaded = True
      except Exception:
        pass
    if not loaded:
      thumb.setPixmap(build_icon("fa5s.film", "#FFFFFF").pixmap(18, 18))
    lay.addWidget(thumb)

    # 2. Title & caption
    cap_col = QVBoxLayout()
    cap_col.setSpacing(2)
    cap = str(item.get("caption") or fn)
    fm = QFontMetrics(self.font())
    lbl_title = QLabel(fm.elidedText(cap.replace("\n", " "), Qt.TextElideMode.ElideRight, 400))
    lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {TT_TEXT};")
    lbl_title.setToolTip(cap)
    lbl_file = QLabel(fn)
    lbl_file.setStyleSheet(f"font-size: 11px; color: {TT_TEXT_2};")
    cap_col.addWidget(lbl_title)
    cap_col.addWidget(lbl_file)
    lay.addLayout(cap_col, 1)

    # 3. Schedule / Publish Date
    date_w = QLabel()
    date_w.setFixedWidth(COL_SCHED)
    raw_dt = item.get("schedule_time") or item.get("schedule_dt") or item.get("timestamp")
    formatted_dt = "Publicação Imediata"
    if raw_dt:
      if isinstance(raw_dt, str):
        try:
          parsed = datetime.fromisoformat(raw_dt)
          formatted_dt = parsed.strftime("%d/%m/%Y %H:%M")
        except Exception:
          formatted_dt = str(raw_dt)
      elif isinstance(raw_dt, datetime):
        formatted_dt = raw_dt.strftime("%d/%m/%Y %H:%M")
    date_w.setText(f"📅  {formatted_dt}")
    date_w.setStyleSheet(f"font-size: 12px; color: {TT_TEXT}; font-weight: 600;")
    lay.addWidget(date_w)

    # 4. Visibility
    vis_w = QLabel()
    vis_w.setFixedWidth(COL_VIS)
    vis = str(item.get("visibility") or "Público")
    vis_w.setText(f"👁  {vis}")
    vis_w.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
    lay.addWidget(vis_w)

    # 5. Status Badge
    st_w = QWidget()
    st_w.setFixedWidth(COL_ACT + 50)
    stl = QHBoxLayout(st_w)
    stl.setContentsMargins(0, 0, 0, 0)
    status_raw = str(item.get("status") or "pending").lower().strip()
    sched_iso = item.get("schedule_time") or item.get("schedule_dt")

    badge = QLabel()
    badge.setFixedHeight(26)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

    # 11 distinct states: received, pending, uploading, verifying, confirming, scheduled, published, failed, unknown, cancelled, conflict
    if status_raw == "scheduled" or (status_raw == "success" and sched_iso):
      badge.setText("📅 Agendado")
      badge.setStyleSheet("background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
    elif status_raw == "published" or (status_raw == "success" and not sched_iso):
      badge.setText("✅ Publicado")
      badge.setStyleSheet("background: #F0FDF4; color: #15803D; border: 1px solid #BBF7D0; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
    elif status_raw in ("uploading", "upload", "enviando"):
      badge.setText("🔄 Enviando...")
      badge.setStyleSheet(f"background: #FFF1F3; color: {TT_RED}; border: 1px solid #FECDD3; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
    elif status_raw in ("verifying", "verificando"):
      badge.setText("🔍 Verificando...")
      badge.setStyleSheet("background: #FEF3C7; color: #D97706; border: 1px solid #FDE68A; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
    elif status_raw in ("confirming", "confirmando"):
      badge.setText("⏳ Confirmando...")
      badge.setStyleSheet("background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
    elif status_raw in ("failed", "falha", "erro") or "fail" in status_raw or "erro" in status_raw:
      badge.setText("❌ Falha")
      badge.setStyleSheet("background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
      err = str(item.get("error") or item.get("message") or "Erro na publicação")
      badge.setToolTip(err)
    elif status_raw == "unknown":
      badge.setText("⚠️ Desconhecido")
      badge.setStyleSheet("background: #FFFBEB; color: #B45309; border: 1px solid #FCD34D; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
      badge.setToolTip("Submissão sem confirmação definitiva do TikTok")
    elif status_raw == "conflict":
      badge.setText("⚠️ Conflito")
      badge.setStyleSheet("background: #FFF7ED; color: #EA580C; border: 1px solid #FED7AA; border-radius: 4px; font-weight: 700; font-size: 11px; padding: 0 8px;")
      badge.setToolTip(str(item.get("error") or "Horário conflitante com publicação existente"))
    elif status_raw == "cancelled":
      badge.setText("⚪ Cancelado")
      badge.setStyleSheet("background: #F1F5F9; color: #64748B; border: 1px solid #CBD5E1; border-radius: 4px; font-weight: 600; font-size: 11px; padding: 0 8px;")
    elif status_raw == "received":
      badge.setText("📥 Recebido")
      badge.setStyleSheet("background: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; border-radius: 4px; font-weight: 600; font-size: 11px; padding: 0 8px;")
    else:
      badge.setText("⏳ Pendente")
      badge.setStyleSheet("background: #F8FAFC; color: #64748B; border: 1px solid #E2E8F0; border-radius: 4px; font-weight: 600; font-size: 11px; padding: 0 8px;")

    stl.addWidget(badge)
    stl.addStretch(1)
    lay.addWidget(st_w)


# ======================================================================
# Page
# ======================================================================
class TikTokStudioPage(QWidget):
  """TikTok Studio–style upload/schedule page (visual layer only).

  All state changes are emitted as signals and handled by the existing
  WizardControllerMixin; no automation code lives here.
  """

  TITLE = "Estúdio TikTok"
  DESCRIPTION = "Carregar e agendar publicações"

  files_dropped = pyqtSignal(list)
  select_videos_requested = pyqtSignal()
  select_folder_requested = pyqtSignal()
  clear_videos_requested = pyqtSignal()
  back_requested = pyqtSignal()
  publish_requested = pyqtSignal()
  publications_requested = pyqtSignal()
  logs_requested = pyqtSignal()
  caption_updated = pyqtSignal(str, str)
  schedule_updated = pyqtSignal(str, object)
  visibility_updated = pyqtSignal(str, str)
  substitute_file_requested = pyqtSignal(str)
  remove_video_requested = pyqtSignal(str)
  batch_schedule_requested = pyqtSignal(int, str, str, int)
  reorder_requested = pyqtSignal(int, int)
  refresh_publications_requested = pyqtSignal()
  pause_upload_requested = pyqtSignal()
  resume_upload_requested = pyqtSignal()
  stop_upload_requested = pyqtSignal()

  def __init__(self, parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self.setObjectName("ttStudioRoot")
    self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    self.setAcceptDrops(True)
    self._items: list[dict[str, Any]] = []
    self._pub_items: list[dict[str, Any]] = []
    self._pub_filter: str = "all"
    self._pub_rows: list[PublicationRowWidget] = []
    self._thumb_cache_dir: Path | None = None
    self._account = ""
    self.rows: list[StudioVideoRow] = []
    self._build_ui()
    self.setStyleSheet(self._stylesheet())

  # ------------------------------------------------------------------
  def _build_ui(self) -> None:
    root = QVBoxLayout(self)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    self.header = StudioHeader()
    self.header.switch_account_requested.connect(self.back_requested.emit)
    self.header.logs_requested.connect(self.logs_requested.emit)
    root.addWidget(self.header)

    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    self.sidebar = StudioSidebar()
    self.sidebar.upload_clicked.connect(self._on_sidebar_upload)
    self.sidebar.publications_clicked.connect(self.publications_requested.emit)
    self.sidebar.switch_account_clicked.connect(self.back_requested.emit)
    body.addWidget(self.sidebar)

    content = QWidget()
    content.setObjectName("ttContent")
    content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    cl = QVBoxLayout(content)
    cl.setContentsMargins(32, 20, 32, 20)
    cl.setSpacing(0)
    self.stack = QStackedWidget()
    cl.addWidget(self.stack, 1)
    body.addWidget(content, 1)
    root.addLayout(body, 1)

    self.stack.addWidget(self._build_empty_view())
    self.stack.addWidget(self._build_list_view())
    self.stack.addWidget(self._build_publications_view())

  def _build_empty_view(self) -> QWidget:
    wrap = QWidget()
    wl = QVBoxLayout(wrap)
    wl.setContentsMargins(0, 0, 0, 0)
    wl.setSpacing(12)

    card = QFrame()
    card.setObjectName("ttCard")
    c = QVBoxLayout(card)
    c.setContentsMargins(24, 24, 24, 22)
    c.setSpacing(20)
    self.drop_zone = StudioDropZone()
    self.drop_zone.files_dropped.connect(self.files_dropped.emit)
    self.drop_zone.select_videos_clicked.connect(self.select_videos_requested.emit)
    self.drop_zone.select_folder_clicked.connect(self.select_folder_requested.emit)
    c.addWidget(self.drop_zone, 1)

    specs = QHBoxLayout()
    specs.setSpacing(24)
    specs.addWidget(SpecItem("fa5s.video", "Tamanho e duração", "Tamanho máximo: 30 GB, duração do vídeo: 60 minutos."), 1)
    specs.addWidget(SpecItem("fa5.file-video", "Formatos de arquivo", "Recomendado: “.mp4”. São suportados outros formatos principais."), 1)
    specs.addWidget(SpecItem("fa5s.tv", "Resoluções de vídeo", "Alta resolução recomendada: 1080p, 1440p e 4K."), 1)
    specs.addWidget(SpecItem("fa5s.crop-alt", "Proporções de apresentação", "Recomendado: 16:9 para paisagem, 9:16 para vertical."), 1)
    c.addLayout(specs)
    wl.addWidget(card, 1)

    tip = QFrame()
    tip.setObjectName("ttCard")
    tl = QHBoxLayout(tip)
    tl.setContentsMargins(16, 12, 16, 12)
    col = QVBoxLayout()
    col.setSpacing(2)
    t1 = QLabel("Carregamento em lote com agendamento")
    t1.setStyleSheet("font-size: 14px; font-weight: 600;")
    t2 = QLabel("Selecione vários vídeos de uma vez e use “Agendar em lote” para distribuir os horários automaticamente.")
    t2.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
    col.addWidget(t1)
    col.addWidget(t2)
    tl.addLayout(col, 1)
    wl.addWidget(tip)
    return wrap

  def _build_list_view(self) -> QWidget:
    wrap = QWidget()
    wl = QVBoxLayout(wrap)
    wl.setContentsMargins(0, 0, 0, 0)
    wl.setSpacing(0)

    self.list_card = QFrame()
    self.list_card.setObjectName("ttCard")
    c = QVBoxLayout(self.list_card)
    c.setContentsMargins(0, 0, 0, 0)
    c.setSpacing(0)

    top = QWidget()
    tl = QVBoxLayout(top)
    tl.setContentsMargins(24, 20, 24, 12)
    tl.setSpacing(10)
    self.loaded_title = QLabel("Carregar vídeo")
    self.loaded_title.setStyleSheet("font-size: 20px; font-weight: 700;")
    tl.addWidget(self.loaded_title)
    actions = QHBoxLayout()
    actions.setSpacing(8)
    actions.addStretch(1)
    self.clear_all_btn = QPushButton(" Limpar lista")
    self.clear_all_btn.setObjectName("ttSecondary")
    self.clear_all_btn.setIcon(build_icon("fa5.trash-alt", TT_TEXT))
    self.clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.clear_all_btn.clicked.connect(self.clear_videos_requested.emit)
    actions.addWidget(self.clear_all_btn)
    self.batch_schedule_btn = QPushButton(" Agendar em lote")
    self.batch_schedule_btn.setObjectName("ttSecondary")
    self.batch_schedule_btn.setIcon(build_icon("fa5.calendar-alt", TT_TEXT))
    self.batch_schedule_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.batch_schedule_btn.clicked.connect(self._open_batch_schedule_dialog)
    actions.addWidget(self.batch_schedule_btn)
    self.add_more_btn = QPushButton(" Adicionar vídeo")
    self.add_more_btn.setObjectName("ttSecondary")
    self.add_more_btn.setIcon(build_icon("fa5s.cloud-upload-alt", TT_TEXT))
    self.add_more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.add_more_btn.clicked.connect(self.select_videos_requested.emit)
    actions.addWidget(self.add_more_btn)
    tl.addLayout(actions)
    c.addWidget(top)

    # table header
    table = QWidget()
    tbl = QVBoxLayout(table)
    tbl.setContentsMargins(24, 0, 24, 0)
    tbl.setSpacing(0)
    tbl.addWidget(hline())
    head = QWidget()
    head.setFixedHeight(40)
    hl = QHBoxLayout(head)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(0)

    def hlabel(text: str, width: int | None = None) -> QLabel:
      lbl = QLabel(text)
      lbl.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 13px; font-weight: 600;")
      if width:
        lbl.setFixedWidth(width)
      return lbl

    hl.addWidget(hlabel("", COL_IDX + 42 + 14))
    hl.addWidget(hlabel("Legenda"), 1)
    hl.addWidget(hlabel("Programados", COL_SCHED))
    hl.addWidget(hlabel("Visibilidade", COL_VIS))
    hl.addWidget(hlabel("Ação", COL_ACT))
    tbl.addWidget(head)
    tbl.addWidget(hline())

    self.rows_container = RowsContainer()
    self.rows_container.reorder.connect(self.reorder_requested.emit)
    self.scroll = QScrollArea()
    self.scroll.setWidgetResizable(True)
    self.scroll.setFrameShape(QFrame.Shape.NoFrame)
    self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self.scroll.setWidget(self.rows_container)
    self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    tbl.addWidget(self.scroll, 1)
    c.addWidget(table, 1)

    c.addWidget(hline())
    foot = QWidget()
    foot.setFixedHeight(72)
    fl = QHBoxLayout(foot)
    fl.setContentsMargins(24, 0, 24, 0)
    fl.setSpacing(16)
    self.summary_badge = QLabel("")
    self.summary_badge.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 13px;")
    fl.addWidget(self.summary_badge)
    fl.addStretch(1)
    self.publish_btn = QPushButton("Publicar (0)")
    self.publish_btn.setObjectName("ttPrimary")
    self.publish_btn.setMinimumWidth(120)
    self.publish_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.publish_btn.clicked.connect(self._on_publish_clicked)
    fl.addWidget(self.publish_btn)
    c.addWidget(foot)

    wl.addWidget(self.list_card, 1)
    self._list_stretch = QWidget()
    wl.addWidget(self._list_stretch, 0)
    return wrap

  def _build_publications_view(self) -> QWidget:
    wrap = QWidget()
    wl = QVBoxLayout(wrap)
    wl.setContentsMargins(0, 0, 0, 0)
    wl.setSpacing(12)

    self.pub_card = QFrame()
    self.pub_card.setObjectName("ttCard")
    pc = QVBoxLayout(self.pub_card)
    pc.setContentsMargins(24, 20, 24, 20)
    pc.setSpacing(14)

    # 1. Header with title & actions
    top = QHBoxLayout()
    top.setSpacing(10)
    col = QVBoxLayout()
    col.setSpacing(2)
    t1 = QLabel("Publicações")
    t1.setStyleSheet("font-size: 20px; font-weight: 700; color: #161823;")
    t2 = QLabel("Vídeos agendados, enviados e pendentes desta conta")
    t2.setStyleSheet(f"font-size: 13px; color: {TT_TEXT_2};")
    col.addWidget(t1)
    col.addWidget(t2)
    top.addLayout(col, 1)

    self.pub_refresh_btn = QPushButton(" Atualizar")
    self.pub_refresh_btn.setObjectName("ttSecondary")
    self.pub_refresh_btn.setIcon(build_icon("fa5s.sync-alt", TT_TEXT))
    self.pub_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pub_refresh_btn.clicked.connect(self.refresh_publications_requested.emit)
    top.addWidget(self.pub_refresh_btn)

    self.pub_upload_more_btn = QPushButton(" Carregar novos vídeos")
    self.pub_upload_more_btn.setObjectName("ttPrimary")
    self.pub_upload_more_btn.setIcon(build_icon("fa5s.plus", "#FFFFFF"))
    self.pub_upload_more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pub_upload_more_btn.clicked.connect(self.show_upload)
    top.addWidget(self.pub_upload_more_btn)
    pc.addLayout(top)

    # 2. Live Upload Progress Card
    self.pub_live_card = QFrame()
    self.pub_live_card.setObjectName("ttLiveBanner")
    plc = QVBoxLayout(self.pub_live_card)
    plc.setContentsMargins(16, 12, 16, 14)
    plc.setSpacing(10)

    l_head = QHBoxLayout()
    l_icon = QLabel()
    l_icon.setPixmap(build_icon("fa5s.paper-plane", TT_RED).pixmap(18, 18))
    l_head.addWidget(l_icon)

    l_txt = QVBoxLayout()
    l_txt.setSpacing(2)
    self.pub_live_title = QLabel("Publicação de vídeos")
    self.pub_live_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #161823;")
    self.pub_live_status = QLabel("Nenhum envio em andamento")
    self.pub_live_status.setStyleSheet(f"font-size: 12px; color: {TT_TEXT_2};")
    l_txt.addWidget(self.pub_live_title)
    l_txt.addWidget(self.pub_live_status)
    l_head.addLayout(l_txt, 1)

    self.pub_pause_btn = QPushButton(" Pausar")
    self.pub_pause_btn.setObjectName("ttSecondary")
    self.pub_pause_btn.setIcon(build_icon("fa5s.pause", TT_TEXT))
    self.pub_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pub_pause_btn.clicked.connect(self._toggle_live_pause)
    self.pub_pause_btn.setEnabled(False)
    l_head.addWidget(self.pub_pause_btn)

    self.pub_stop_btn = QPushButton(" Parar")
    self.pub_stop_btn.setObjectName("ttSecondary")
    self.pub_stop_btn.setIcon(build_icon("fa5s.stop", TT_RED))
    self.pub_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pub_stop_btn.clicked.connect(self.stop_upload_requested.emit)
    self.pub_stop_btn.setEnabled(False)
    l_head.addWidget(self.pub_stop_btn)

    self.pub_live_logs_btn = QPushButton(" Logs")
    self.pub_live_logs_btn.setObjectName("ttSecondary")
    self.pub_live_logs_btn.setIcon(build_icon("fa5s.stream", TT_TEXT))
    self.pub_live_logs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.pub_live_logs_btn.clicked.connect(self.logs_requested.emit)
    l_head.addWidget(self.pub_live_logs_btn)
    plc.addLayout(l_head)

    self.pub_progress_bar = QProgressBar()
    self.pub_progress_bar.setFixedHeight(8)
    self.pub_progress_bar.setRange(0, 100)
    self.pub_progress_bar.setValue(0)
    self.pub_progress_bar.setTextVisible(False)
    plc.addWidget(self.pub_progress_bar)
    pc.addWidget(self.pub_live_card)

    # 3. Filter pills row
    tabs_lay = QHBoxLayout()
    tabs_lay.setSpacing(8)
    self.filter_buttons: dict[str, QPushButton] = {}
    filters = [
      ("all", "Todas"),
      ("sched", "Agendadas"),
      ("pub", "Publicadas"),
      ("pend", "Pendentes"),
      ("fail", "Falhas"),
    ]
    for key, label in filters:
      btn = QPushButton(f"{label} (0)")
      btn.setObjectName("ttFilterTab")
      btn.setCursor(Qt.CursorShape.PointingHandCursor)
      btn.clicked.connect(lambda _c=False, k=key: self._on_pub_filter_clicked(k))
      tabs_lay.addWidget(btn)
      self.filter_buttons[key] = btn
    tabs_lay.addStretch(1)
    pc.addLayout(tabs_lay)

    # 4. Table Header
    head = QWidget()
    head.setFixedHeight(38)
    hl = QHBoxLayout(head)
    hl.setContentsMargins(20, 0, 20, 0)
    hl.setSpacing(14)

    def hlabel(text: str, width: int | None = None) -> QLabel:
      lbl = QLabel(text)
      lbl.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 13px; font-weight: 600;")
      if width:
        lbl.setFixedWidth(width)
      return lbl

    hl.addWidget(hlabel("", 38))
    hl.addWidget(hlabel("Legenda / Vídeo"), 1)
    hl.addWidget(hlabel("Programados", COL_SCHED))
    hl.addWidget(hlabel("Visibilidade", COL_VIS))
    hl.addWidget(hlabel("Status", COL_ACT + 50))
    pc.addWidget(hline())
    pc.addWidget(head)
    pc.addWidget(hline())

    # 5. Rows container inside scroll area
    self.pub_scroll = QScrollArea()
    self.pub_scroll.setWidgetResizable(True)
    self.pub_scroll.setFrameShape(QFrame.Shape.NoFrame)
    self.pub_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    self.pub_container_widget = QWidget()
    self.pub_rows_layout = QVBoxLayout(self.pub_container_widget)
    self.pub_rows_layout.setContentsMargins(0, 0, 0, 0)
    self.pub_rows_layout.setSpacing(0)
    self.pub_rows_layout.addStretch(1)

    self.pub_scroll.setWidget(self.pub_container_widget)
    pc.addWidget(self.pub_scroll, 1)

    self.pub_empty_lbl = QLabel("Nenhuma publicação encontrada.")
    self.pub_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.pub_empty_lbl.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 14px; padding: 40px;")
    self.pub_empty_lbl.hide()
    pc.addWidget(self.pub_empty_lbl)

    wl.addWidget(self.pub_card, 1)
    self._set_pub_filter_active("all")
    return wrap

  def _stylesheet(self) -> str:
    return tt_base_stylesheet() + f"""
      QWidget#ttStudioRoot {{ background: {TT_BG_ALT}; }}
      QWidget#ttContent {{ background: {TT_BG_ALT}; }}
      QFrame#ttHeader {{ background: {TT_BG}; border: none; border-bottom: 1px solid {TT_BORDER}; }}
      QFrame#ttSidebar {{ background: {TT_BG}; border: none; border-right: 1px solid {TT_BORDER}; }}
      QFrame#ttCard {{ background: {TT_BG}; border: none; border-radius: 8px; }}
      QFrame#ttDropZone {{ background: #FCFCFC; border: 1px dashed #D0D0D0; border-radius: 4px; }}
      QFrame#ttDropZone:hover, QFrame#ttDropZone[dragging="true"] {{ border-color: {TT_RED}; background: #FFF7F9; }}
      QFrame#ttRow {{ background: {TT_BG}; border: none; border-bottom: 1px solid #F1F1F2; }}
      QFrame#ttRow:hover {{ background: #FAFAFA; }}
      QFrame#ttRow[editing="true"] {{ background: {TT_BG_ALT}; }}
      QPushButton#ttNavItem {{ border-radius: 6px; text-align: left; }}
      QPushButton#ttNavItem:hover {{ background: {TT_BG_HOVER}; }}
      QPushButton#ttUploadNav {{ background: {TT_RED}; border-radius: 6px; }}
      QPushButton#ttUploadNav:hover {{ background: #E8264C; }}
      QFrame#ttLiveBanner {{ background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 8px; }}
      QProgressBar {{ border: none; background: #F1F1F2; border-radius: 4px; }}
      QProgressBar::chunk {{ background: {TT_RED}; border-radius: 4px; }}
      QPushButton#ttFilterTab {{
        border: 1px solid #E5E5E5; background: #FFFFFF; color: {TT_TEXT};
        border-radius: 15px; padding: 4px 14px; font-size: 13px; font-weight: 600;
      }}
      QPushButton#ttFilterTab:hover {{ background: #F8F8F8; }}
      QPushButton#ttFilterTab[active="true"] {{
        background: #161823; color: #FFFFFF; border-color: #161823;
      }}
    """

  # ------------------------------------------------------------------
  # Public API used by the controller
  # ------------------------------------------------------------------
  def set_account(self, username: str, status: str = "Sessão salva", ok: bool = True) -> None:
    self._account = username
    self.header.set_account(username, status, ok)

  def populate_videos(self, items: list[dict[str, Any]], thumb_cache_dir: Path | None = None) -> None:
    """Render rows, or the upload view when there are no videos."""
    self._items = [dict(it) for it in items]
    self._thumb_cache_dir = thumb_cache_dir

    for r in self.rows:
      r.setParent(None)
      r.deleteLater()
    self.rows = []

    n = len(self._items)
    self.publish_btn.setText(f"Publicar ({n})")
    self.publish_btn.setEnabled(n > 0)
    if not n:
      self.summary_badge.setText("")
      self.stack.setCurrentIndex(0)
      return

    for i, it in enumerate(self._items):
      row = StudioVideoRow(i, it, thumb_cache_dir)
      row.caption_saved.connect(self._on_row_caption)
      row.schedule_clicked.connect(self._on_row_schedule)
      row.visibility_picked.connect(self._on_row_visibility)
      row.edit_clicked.connect(self._on_row_edit_dialog)
      row.delete_clicked.connect(lambda idx: self._emit_for(idx, self.remove_video_requested))
      row.substitute_clicked.connect(lambda idx: self._emit_for(idx, self.substitute_file_requested))
      row.edit_mode_changed.connect(lambda *_: self._update_card_height())
      self.rows_container.vbox.insertWidget(i, row)
      self.rows.append(row)

    scheduled = sum(1 for it in self._items if isinstance(it.get("schedule_dt"), datetime))
    invalid = sum(1 for it in self._items if not it.get("is_valid", True))
    parts = [f"{n} vídeo(s)", f"{scheduled} programado(s)", f"{n - scheduled} publicar agora"]
    if invalid:
      parts.append(f"{invalid} incompatível(is)")
    self.summary_badge.setText("  ·  ".join(parts))
    self.stack.setCurrentIndex(1)
    self._update_card_height()

  def items(self) -> list[dict[str, Any]]:
    return [dict(it) for it in self._items]

  # ------------------------------------------------------------------
  def _update_card_height(self) -> None:
    """Card wraps its rows like the web page; list scrolls when it overflows."""
    rows_h = sum(r.height() for r in self.rows) + 2
    overhead = 20 + 28 + 10 + 32 + 12 + 1 + 40 + 1 + 1 + 72
    self.list_card.setMaximumHeight(overhead + rows_h)
    self.wrap_stretch_policy()

  def wrap_stretch_policy(self) -> None:
    self._list_stretch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

  def _emit_for(self, idx: int, signal) -> None:
    if 0 <= idx < len(self._items):
      signal.emit(str(self._items[idx].get("filename", "")))

  def _on_row_caption(self, idx: int, text: str) -> None:
    if 0 <= idx < len(self._items):
      self._items[idx]["caption"] = text
      self.caption_updated.emit(str(self._items[idx]["filename"]), text)

  def _on_row_edit_dialog(self, idx: int) -> None:
    if not (0 <= idx < len(self._items)):
      return
    it = self._items[idx]
    dlg = CaptionEditDialog(str(it.get("filename", "")), str(it.get("caption") or ""), parent=self.window())
    if dlg.exec():
      text = dlg.full_caption()
      it["caption"] = text
      self.rows[idx].item["caption"] = text
      self.rows[idx].refresh()
      self.caption_updated.emit(str(it["filename"]), text)

  def _on_row_schedule(self, idx: int) -> None:
    if not (0 <= idx < len(self._items)):
      return
    # Close any existing schedule dialog to prevent overlapping duplicates
    if hasattr(self, "_active_schedule_dlg") and self._active_schedule_dlg is not None:
      try:
        self._active_schedule_dlg.reject()
      except Exception:
        pass
      self._active_schedule_dlg = None

    it = self._items[idx]
    row = self.rows[idx]
    try:
      dlg = TikTokScheduleDialog(
        current_dt=it.get("schedule_dt") if isinstance(it.get("schedule_dt"), datetime) else None,
        filename=str(it.get("filename", "")),
        parent=self.window(),
        anchor=row.sched_btn,
      )
      self._active_schedule_dlg = dlg
      dlg.scheduled.connect(lambda dt, i=idx: self._apply_schedule(i, dt))
      dlg.publish_now.connect(lambda i=idx: self._apply_schedule(i, None))
      dlg.exec()
    except Exception as exc:  # never close the app because of the popup
      import logging
      logging.getLogger("TikTokScheduler").error(f"Erro no seletor de horário: {exc}")
    finally:
      self._active_schedule_dlg = None

  def _apply_schedule(self, idx: int, dt: datetime | None) -> None:
    if not (0 <= idx < len(self._items)):
      return
    self._items[idx]["schedule_dt"] = dt
    self.rows[idx].item["schedule_dt"] = dt
    self.rows[idx].refresh()
    self.schedule_updated.emit(str(self._items[idx]["filename"]), dt)
    self._refresh_summary()

  def _on_row_visibility(self, idx: int, vis: str) -> None:
    if not (0 <= idx < len(self._items)):
      return
    self._items[idx]["visibility"] = vis
    self.rows[idx].item["visibility"] = vis
    self.rows[idx].refresh()
    self.visibility_updated.emit(str(self._items[idx]["filename"]), vis)

  def _refresh_summary(self) -> None:
    n = len(self._items)
    scheduled = sum(1 for it in self._items if isinstance(it.get("schedule_dt"), datetime))
    self.summary_badge.setText(f"{n} vídeo(s)  ·  {scheduled} programado(s)  ·  {n - scheduled} publicar agora")

  def _on_publish_clicked(self) -> None:
    if not self._items:
      return
    valid_items = [it for it in self._items if it.get("is_valid", True)]
    dlg = PublishConfirmDialog(valid_items, self._account, parent=self.window())
    if dlg.exec():
      self.publish_requested.emit()

  def _open_batch_schedule_dialog(self) -> None:
    if not self._items:
      return
    dlg = BatchScheduleDialog(total_videos=len(self._items), parent=self.window())
    dlg.applied.connect(self.batch_schedule_requested.emit)
    dlg.exec()

  def _on_sidebar_upload(self) -> None:
    self.show_upload()

  def show_upload(self) -> None:
    if self._items:
      self.stack.setCurrentIndex(1)
    else:
      self.stack.setCurrentIndex(0)

  def show_publications(self) -> None:
    self.stack.setCurrentIndex(2)

  def _toggle_live_pause(self) -> None:
    if "Continuar" in self.pub_pause_btn.text():
      self.resume_upload_requested.emit()
    else:
      self.pause_upload_requested.emit()

  def _on_pub_filter_clicked(self, filter_name: str) -> None:
    self._pub_filter = filter_name
    self._set_pub_filter_active(filter_name)
    self._render_filtered_publications()

  def _set_pub_filter_active(self, filter_name: str) -> None:
    for k, btn in self.filter_buttons.items():
      is_act = (k == filter_name)
      btn.setProperty("active", is_act)
      btn.style().unpolish(btn)
      btn.style().polish(btn)

  def populate_publications(self, items: list[dict[str, Any]]) -> None:
    self._pub_items = [dict(it) for it in items]
    counts = {"all": len(items), "sched": 0, "pub": 0, "pend": 0, "fail": 0}
    for it in items:
      st = str(it.get("status") or "pending").lower().strip()
      sched_time = it.get("schedule_time") or it.get("schedule_dt")
      is_sched = (st == "scheduled") or (st == "success" and bool(sched_time))
      is_pub = (st == "published") or (st == "success" and not sched_time)
      is_fail = (st in ("failed", "conflict", "unknown")) or ("fail" in st or "erro" in st)

      if is_sched:
        counts["sched"] += 1
      elif is_pub:
        counts["pub"] += 1
      elif is_fail:
        counts["fail"] += 1
      else:
        counts["pend"] += 1

    labels = {
      "all": "Todas",
      "sched": "Agendadas",
      "pub": "Publicadas",
      "pend": "Pendentes",
      "fail": "Falhas",
    }
    for k, btn in self.filter_buttons.items():
      btn.setText(f"{labels.get(k, k)} ({counts.get(k, 0)})")

    self._render_filtered_publications()

  def _render_filtered_publications(self) -> None:
    for r in self._pub_rows:
      r.setParent(None)
      r.deleteLater()
    self._pub_rows = []

    matching = []
    for it in self._pub_items:
      st = str(it.get("status") or "pending").lower().strip()
      sched_time = it.get("schedule_time") or it.get("schedule_dt")
      is_sched = (st == "scheduled") or (st == "success" and bool(sched_time))
      is_pub = (st == "published") or (st == "success" and not sched_time)
      is_fail = (st in ("failed", "conflict", "unknown")) or ("fail" in st or "erro" in st)
      is_pend = not (is_sched or is_pub or is_fail)

      if self._pub_filter == "all":
        matching.append(it)
      elif self._pub_filter == "sched" and is_sched:
        matching.append(it)
      elif self._pub_filter == "pub" and is_pub:
        matching.append(it)
      elif self._pub_filter == "pend" and is_pend:
        matching.append(it)
      elif self._pub_filter == "fail" and is_fail:
        matching.append(it)

    if not matching:
      self.pub_empty_lbl.show()
      self.pub_scroll.hide()
      return

    self.pub_empty_lbl.hide()
    self.pub_scroll.show()

    for i, it in enumerate(matching):
      row = PublicationRowWidget(it, thumb_cache_dir=self._thumb_cache_dir)
      self.pub_rows_layout.insertWidget(i, row)
      self._pub_rows.append(row)

  def update_live_upload(
    self,
    current: int,
    total: int,
    status_text: str = "",
    filename: str = "",
    percent: int = 0,
    is_running: bool = True,
    is_paused: bool = False,
    scheduled_count: int = 0,
    published_count: int = 0,
    failed_count: int = 0,
    unknown_count: int = 0,
  ) -> None:
    self.pub_pause_btn.setEnabled(is_running)
    self.pub_stop_btn.setEnabled(is_running)

    if is_running:
      if is_paused:
        self.pub_live_title.setText("⏸ Publicação Pausada")
        self.pub_live_status.setText(status_text or "Clique em Continuar para retomar.")
        self.pub_pause_btn.setText(" Continuar")
        self.pub_pause_btn.setIcon(build_icon("fa5s.play", TT_TEXT))
      else:
        title = f"🚀 Enviando ({current}/{total}): {filename}" if filename else f"🚀 Enviando publicações ({current}/{total})..."
        self.pub_live_title.setText(title)
        self.pub_live_status.setText(status_text or f"{current} de {total} processado(s)")
        self.pub_pause_btn.setText(" Pausar")
        self.pub_pause_btn.setIcon(build_icon("fa5s.pause", TT_TEXT))
      val = percent if percent > 0 else (int((current / total) * 100) if total else 0)
      self.pub_progress_bar.setValue(min(100, max(0, val)))
    else:
      self.pub_pause_btn.setText(" Pausar")
      self.pub_pause_btn.setIcon(build_icon("fa5s.pause", TT_TEXT))
      if total > 0 and current >= total:
        if failed_count > 0 or unknown_count > 0:
          self.pub_live_title.setText("⚠️ Fila finalizada com alertas")
          parts = []
          if scheduled_count > 0:
            parts.append(f"{scheduled_count} agendado(s)")
          if published_count > 0:
            parts.append(f"{published_count} publicado(s)")
          if failed_count > 0:
            parts.append(f"{failed_count} com falha")
          if unknown_count > 0:
            parts.append(f"{unknown_count} desconhecido(s)")
          summary = " · ".join(parts) if parts else f"{failed_count} falha(s) identificada(s)"
          self.pub_live_status.setText(summary)
        else:
          self.pub_live_title.setText("✓ Todas as publicações foram concluídas")
          parts = []
          if scheduled_count > 0:
            parts.append(f"{scheduled_count} agendamento(s) confirmado(s)")
          if published_count > 0:
            parts.append(f"{published_count} publicação(ões) realizada(s)")
          summary = " e ".join(parts) if parts else f"{total} finalizada(s) com sucesso"
          self.pub_live_status.setText(summary)
        self.pub_progress_bar.setValue(100)
      elif status_text:
        self.pub_live_title.setText("Status da Publicação")
        self.pub_live_status.setText(status_text)
      else:
        self.pub_live_title.setText("Publicações")
        self.pub_live_status.setText("Aguardando novas publicações.")
        self.pub_progress_bar.setValue(0)

  # page-level drop (works on the list view too)
  def dragEnterEvent(self, e) -> None:  # noqa: N802
    if e.mimeData().hasUrls():
      e.acceptProposedAction()

  def dropEvent(self, e) -> None:  # noqa: N802
    paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
    if paths:
      self.files_dropped.emit(paths)
      e.acceptProposedAction()
