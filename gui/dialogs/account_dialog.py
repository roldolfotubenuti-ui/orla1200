from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
  QDialog,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QPushButton,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

from gui.widgets.tiktok_style import (
  TT_BG_HOVER,
  TT_BORDER,
  TT_FONT,
  TT_RED,
  TT_RED_HOVER,
  TT_TEXT,
  TT_TEXT_2,
)


class AccountDialog(QDialog):
  """Modal dialog for creating or editing TikTok account cookies.

  Matches the approved TikTok Studio modal style (white clean card,
  portuguese labels, rounded inputs, #FE2C55 save button).
  """

  def __init__(
    self,
    title: str,
    username: str = "",
    cookie_text: str = "",
    parent: QWidget | None = None,
  ) -> None:
    super().__init__(parent)
    display_title = "Editar conta" if "edit" in title.lower() else "Adicionar conta"
    self.setWindowTitle(display_title)
    self.setModal(True)
    self.resize(520, 480)
    self.setStyleSheet(f"""
      QDialog {{
        background-color: #FFFFFF;
        font-family: {TT_FONT};
        color: {TT_TEXT};
      }}
      QLabel {{
        background: transparent;
        font-family: {TT_FONT};
      }}
      QLineEdit, QTextEdit {{
        background-color: #FFFFFF;
        color: {TT_TEXT};
        border: 1px solid {TT_BORDER};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        selection-background-color: #FFD6DE;
        selection-color: {TT_TEXT};
      }}
      QLineEdit:focus, QTextEdit:focus {{
        border: 1.5px solid #161823;
      }}
      QPushButton#modalCancelBtn {{
        background-color: {TT_BG_HOVER};
        color: {TT_TEXT};
        font-size: 13px;
        font-weight: 600;
        border-radius: 6px;
        padding: 0 20px;
        min-height: 36px;
        border: none;
      }}
      QPushButton#modalCancelBtn:hover {{
        background-color: #E3E3E4;
      }}
      QPushButton#modalSaveBtn {{
        background-color: {TT_RED};
        color: #FFFFFF;
        font-size: 13px;
        font-weight: 600;
        border-radius: 6px;
        padding: 0 24px;
        min-height: 36px;
        border: none;
      }}
      QPushButton#modalSaveBtn:hover {{
        background-color: {TT_RED_HOVER};
      }}
    """)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(28, 28, 28, 24)
    layout.setSpacing(16)

    # 1. Header (Title & Subtitle)
    header_col = QVBoxLayout()
    header_col.setSpacing(6)

    self.title_label = QLabel(display_title)
    self.title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #161823;")
    header_col.addWidget(self.title_label)

    subtitle_text = (
      "Cole o export de cookies do TikTok e mantenha o nome de usuário "
      "consistente com o arquivo de cookies."
    )
    self.subtitle_label = QLabel(subtitle_text)
    self.subtitle_label.setStyleSheet(f"font-size: 13px; color: {TT_TEXT_2}; line-height: 1.4;")
    self.subtitle_label.setWordWrap(True)
    header_col.addWidget(self.subtitle_label)
    layout.addLayout(header_col)

    # 2. Field: Username
    user_col = QVBoxLayout()
    user_col.setSpacing(6)
    user_lbl = QLabel("Usuário")
    user_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #161823;")
    user_col.addWidget(user_lbl)

    self.username_input = QLineEdit(username)
    self.username_input.setPlaceholderText("ex.: conta.exemplo")
    self.username_input.setFixedHeight(38)
    user_col.addWidget(self.username_input)
    layout.addLayout(user_col)

    # 3. Field: Cookies JSON
    cookie_col = QVBoxLayout()
    cookie_col.setSpacing(6)
    cookie_lbl = QLabel("Cookies JSON")
    cookie_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #161823;")
    cookie_col.addWidget(cookie_lbl)

    self.cookie_input = QTextEdit()
    self.cookie_input.setPlaceholderText("Cole aqui o JSON de cookies")
    self.cookie_input.setPlainText(cookie_text)
    cookie_col.addWidget(self.cookie_input, 1)
    layout.addLayout(cookie_col, 1)

    # Error message
    self.error_label = QLabel("")
    self.error_label.setStyleSheet(f"color: {TT_RED}; font-size: 12px; font-weight: 600;")
    self.error_label.hide()
    layout.addWidget(self.error_label)

    # 4. Action Buttons (Cancel / Save)
    button_row = QHBoxLayout()
    button_row.setSpacing(10)
    button_row.addStretch(1)

    self.cancel_btn = QPushButton("Cancelar")
    self.cancel_btn.setObjectName("modalCancelBtn")
    self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.cancel_btn.clicked.connect(self.reject)
    button_row.addWidget(self.cancel_btn)

    self.save_btn = QPushButton("Salvar")
    self.save_btn.setObjectName("modalSaveBtn")
    self.save_btn.setProperty("class", "accent")
    self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    button_row.addWidget(self.save_btn)

    layout.addLayout(button_row)

  def show_error(self, message: str) -> None:
    """Display a validation error."""
    self.error_label.setText(message)
    self.error_label.show()

  def clear_error(self) -> None:
    """Hide the validation error."""
    self.error_label.clear()
    self.error_label.hide()

  def get_username(self) -> str:
    """Return the trimmed username."""
    return self.username_input.text().strip()

  def get_cookie_text(self) -> str:
    """Return the raw cookie JSON text."""
    return self.cookie_input.toPlainText().strip()
