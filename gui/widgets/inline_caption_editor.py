from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
  QFrame,
  QHBoxLayout,
  QLabel,
  QPushButton,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

from gui.widgets.icon import build_icon
from gui.widgets.tiktok_style import TT_BORDER, TT_RED, TT_RED_HOVER, TT_TEXT, TT_TEXT_2


class InlineCaptionEditor(QWidget):
  """TikTok Studio inline caption editor (reference image 4).

  [ text box ............ ]  (↑)
  [ 33 / 4000        @ #  ]
  """

  caption_saved = pyqtSignal(str)
  editing_cancelled = pyqtSignal()

  MAX_CHARS = 4000

  def __init__(self, initial_text: str = "", parent: QWidget | None = None) -> None:
    super().__init__(parent)
    self._initial_text = initial_text
    self._build_ui()
    self.set_text(initial_text)

  def _build_ui(self) -> None:
    row = QHBoxLayout(self)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)

    self.box = QFrame()
    self.box.setObjectName("ttCaptionBox")
    self.box.setStyleSheet(
      f"QFrame#ttCaptionBox {{ background: #FFFFFF; border: 1px solid {TT_BORDER}; border-radius: 6px; }}"
    )
    box_l = QVBoxLayout(self.box)
    box_l.setContentsMargins(10, 6, 10, 6)
    box_l.setSpacing(2)

    self.text_edit = QTextEdit()
    self.text_edit.setAcceptRichText(False)
    self.text_edit.setPlaceholderText("Adicione uma legenda...")
    self.text_edit.setStyleSheet(
      f"QTextEdit {{ border: none; background: transparent; padding: 0; color: {TT_TEXT}; font-size: 14px; }}"
    )
    self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.text_edit.setFixedHeight(46)
    self.text_edit.textChanged.connect(self._on_text_changed)
    box_l.addWidget(self.text_edit)

    bottom = QHBoxLayout()
    bottom.setSpacing(6)
    self.counter_label = QLabel(f"0 / {self.MAX_CHARS}")
    self.counter_label.setStyleSheet(f"color: {TT_TEXT_2}; font-size: 12px;")
    bottom.addWidget(self.counter_label)
    bottom.addStretch(1)
    self.at_btn = self._token_btn("@", "Mencionar")
    self.hash_btn = self._token_btn("#", "Hashtag")
    bottom.addWidget(self.at_btn)
    bottom.addWidget(self.hash_btn)
    box_l.addLayout(bottom)
    row.addWidget(self.box, 1)

    self.submit_btn = QPushButton()
    self.submit_btn.setIcon(build_icon("fa5s.arrow-up", "#FFFFFF"))
    self.submit_btn.setToolTip("Salvar legenda (Ctrl+Enter)")
    self.submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.submit_btn.setFixedSize(28, 28)
    self.submit_btn.setStyleSheet(
      f"QPushButton {{ background: {TT_RED}; border: none; border-radius: 14px; }}"
      f"QPushButton:hover {{ background: {TT_RED_HOVER}; }}"
    )
    self.submit_btn.clicked.connect(self._on_submit)
    row.addWidget(self.submit_btn, 0, Qt.AlignmentFlag.AlignBottom)

    QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._on_submit)
    QShortcut(QKeySequence("Escape"), self, activated=self._on_cancel)

  def _token_btn(self, token: str, tip: str) -> QPushButton:
    b = QPushButton(token)
    b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFixedSize(18, 18)
    b.setStyleSheet(
      f"QPushButton {{ background: transparent; border: none; color: {TT_TEXT}; font-size: 13px; font-weight: 700; }}"
      "QPushButton:hover { color: #FE2C55; }"
    )
    b.clicked.connect(lambda: self._insert_token(token))
    return b

  def _insert_token(self, token: str) -> None:
    self.text_edit.textCursor().insertText(token)
    self.text_edit.setFocus()

  def _on_text_changed(self) -> None:
    text = self.text_edit.toPlainText()
    if len(text) > self.MAX_CHARS:
      self.text_edit.blockSignals(True)
      self.text_edit.setPlainText(text[: self.MAX_CHARS])
      self.text_edit.blockSignals(False)
      text = text[: self.MAX_CHARS]
    self.counter_label.setText(f"{len(text)} / {self.MAX_CHARS}")

  def _on_submit(self) -> None:
    self.caption_saved.emit(self.text_edit.toPlainText().strip())

  def _on_cancel(self) -> None:
    self.set_text(self._initial_text)
    self.editing_cancelled.emit()

  def set_text(self, text: str) -> None:
    self._initial_text = text
    self.text_edit.setPlainText(text)
    self._on_text_changed()

  def text(self) -> str:
    return self.text_edit.toPlainText().strip()

  def focus_editor(self) -> None:
    self.text_edit.setFocus()
    cur = self.text_edit.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    self.text_edit.setTextCursor(cur)
