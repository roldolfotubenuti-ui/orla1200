from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


class PageLayout(QWidget):
  """Scrollable page shell with shared spacing rules.

  :param parent: Parent widget.
  :return: None
  """

  def __init__(self, parent: QWidget | None = None) -> None:
    """Initialize the page shell.

    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setProperty("class", "page")

    root_layout = QVBoxLayout(self)
    root_layout.setContentsMargins(0, 0, 0, 0)

    self.scroll_area = QScrollArea(self)
    self.scroll_area.setWidgetResizable(True)
    self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    self.scroll_area.viewport().setProperty("class", "page-viewport")
    root_layout.addWidget(self.scroll_area)

    self.content = QWidget()
    self.content.setProperty("class", "page-content")
    self.scroll_area.setWidget(self.content)
    self.content_layout = QVBoxLayout(self.content)
    self.content_layout.setContentsMargins(24, 24, 24, 24)
    self.content_layout.setSpacing(20)
