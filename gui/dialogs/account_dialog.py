from __future__ import annotations

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


class AccountDialog(QDialog):
  """Modal dialog for creating or editing account cookies.

  :param title: Dialog title.
  :param username: Initial username.
  :param cookie_text: Initial cookie JSON.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    title: str,
    username: str = "",
    cookie_text: str = "",
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the dialog.

    :param title: Dialog title.
    :param username: Initial username.
    :param cookie_text: Initial cookie JSON.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setWindowTitle(title)
    self.setModal(True)
    self.resize(540, 460)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(14)

    title_label = QLabel(title)
    title_label.setProperty("class", "page-title")
    layout.addWidget(title_label)

    subtitle = QLabel("Paste the TikTok cookie export and keep usernames consistent with your cookie filenames.")
    subtitle.setProperty("class", "page-description")
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)

    username_label = QLabel("Username")
    username_label.setProperty("class", "muted")
    layout.addWidget(username_label)

    self.username_input = QLineEdit(username)
    self.username_input.setPlaceholderText("e.g. account.name")
    layout.addWidget(self.username_input)

    cookie_label = QLabel("Cookies JSON")
    cookie_label.setProperty("class", "muted")
    layout.addWidget(cookie_label)

    self.cookie_input = QTextEdit()
    self.cookie_input.setPlaceholderText(
      'Paste a JSON cookie array, for example:\n[{"name": "sessionid", "value": "...", "domain": ".tiktok.com", "path": "/"}]'
    )
    self.cookie_input.setPlainText(cookie_text)
    layout.addWidget(self.cookie_input, 1)

    self.error_label = QLabel("")
    self.error_label.setProperty("class", "muted")
    self.error_label.hide()
    layout.addWidget(self.error_label)

    button_row = QHBoxLayout()
    button_row.addStretch(1)

    self.cancel_btn = QPushButton("Cancel")
    self.cancel_btn.clicked.connect(self.reject)
    button_row.addWidget(self.cancel_btn)

    self.save_btn = QPushButton("Save")
    self.save_btn.setProperty("class", "accent")
    button_row.addWidget(self.save_btn)

    layout.addLayout(button_row)

  def show_error(self, message: str) -> None:
    """Display a validation error.

    :param message: Error text.
    :return: None
    """
    self.error_label.setText(message)
    self.error_label.setStyleSheet("color: #d93025; font-size: 12px; font-weight: 600;")
    self.error_label.show()

  def clear_error(self) -> None:
    """Hide the validation error.

    :return: None
    """
    self.error_label.clear()
    self.error_label.hide()

  def get_username(self) -> str:
    """Return the trimmed username.

    :return: Username text.
    """
    return self.username_input.text().strip()

  def get_cookie_text(self) -> str:
    """Return the raw cookie JSON text.

    :return: Cookie JSON text.
    """
    return self.cookie_input.toPlainText().strip()
