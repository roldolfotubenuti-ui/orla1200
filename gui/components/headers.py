from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.widgets.icon import build_icon


class SectionHeader(QWidget):
  """Compact section header with icon, title, and helper text.

  :param title: Title text.
  :param description: Optional helper text.
  :param icon_name: qtawesome icon name.
  :param icon_color: Icon color.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    title: str,
    description: str,
    icon_name: str,
    icon_color: str,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the section header.

    :param title: Title text.
    :param description: Helper text.
    :param icon_name: qtawesome icon name.
    :param icon_color: Icon color.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    layout = QHBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    icon_label = QLabel()
    icon_label.setPixmap(build_icon(icon_name, icon_color).pixmap(18, 18))
    layout.addWidget(icon_label)

    text_layout = QVBoxLayout()
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(2)

    title_label = QLabel(title)
    title_label.setProperty("class", "section-title")
    text_layout.addWidget(title_label)

    description_label = QLabel(description)
    description_label.setProperty("class", "muted")
    description_label.setWordWrap(True)
    text_layout.addWidget(description_label)

    layout.addLayout(text_layout, 1)
