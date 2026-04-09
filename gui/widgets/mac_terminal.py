from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.theme.palette import ThemePalette
from gui.widgets.rich_log import RichLogView


class MacTerminalPanel(QFrame):
  """Mac-style terminal wrapper around the rich log view.

  :param palette: Active theme palette.
  :param title: Terminal title.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    palette: ThemePalette,
    title: str = "Session terminal",
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the terminal panel.

    :param palette: Active theme palette.
    :param title: Terminal title.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self._palette = palette
    self.setProperty("class", "terminal-shell")

    root_layout = QVBoxLayout(self)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    header = QWidget(self)
    header.setProperty("class", "terminal-header")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(14, 10, 14, 10)
    header_layout.setSpacing(10)

    dots_layout = QHBoxLayout()
    dots_layout.setContentsMargins(0, 0, 0, 0)
    dots_layout.setSpacing(6)
    for role in ("red", "yellow", "green"):
      dot = QFrame(header)
      dot.setProperty("class", "terminal-dot")
      dot.setProperty("role", role)
      dot.setFixedSize(10, 10)
      dots_layout.addWidget(dot)
    header_layout.addLayout(dots_layout)

    self.title_label = QLabel(title, header)
    self.title_label.setProperty("class", "terminal-title")
    header_layout.addWidget(self.title_label)
    header_layout.addStretch(1)

    self.open_logs_button = QPushButton("Logs")
    self.open_logs_button.setProperty("class", "terminal-action")
    header_layout.addWidget(self.open_logs_button)

    self.clear_button = QPushButton("Clear")
    self.clear_button.setProperty("class", "terminal-action")
    header_layout.addWidget(self.clear_button)
    root_layout.addWidget(header)

    self.log_view = RichLogView(palette, terminal_mode=True, parent=self)
    self.log_view.setProperty("surface", "terminal")
    self.log_view.setMinimumHeight(280)
    root_layout.addWidget(self.log_view, 1)

  def set_palette_data(self, palette: ThemePalette) -> None:
    """Refresh theme-driven terminal content colors.

    :param palette: Active theme palette.
    :return: None
    """
    self._palette = palette
    self.log_view.set_palette_data(palette)
