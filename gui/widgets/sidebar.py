from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QToolButton, QVBoxLayout, QWidget

from gui.widgets.icon import build_icon


class SidebarNavigation(QWidget):
  """Sidebar navigation with mutually exclusive page buttons.

  :param icon_color: Icon tint for default state.
  :param parent: Parent widget.
  :return: None
  """

  page_selected = pyqtSignal(str)

  def __init__(
    self,
    icon_color: str,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the sidebar navigation.

    :param icon_color: Initial icon color.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setProperty("class", "sidebar")
    self._icon_color = icon_color
    self._buttons: dict[str, QToolButton] = {}
    self._button_group = QButtonGroup(self)
    self._button_group.setExclusive(True)

    self._layout = QVBoxLayout(self)
    self._layout.setContentsMargins(16, 20, 16, 20)
    self._layout.setSpacing(8)
    self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

  def add_page(self, key: str, label: str, icon_name: str) -> None:
    """Add a navigation button.

    :param key: Stable page key.
    :param label: Visible label.
    :param icon_name: qtawesome icon name.
    :return: None
    """
    button = QToolButton(self)
    button.setCheckable(True)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setProperty("class", "sidebar-button")
    button.setText(label)
    button.setIcon(build_icon(icon_name, self._icon_color))
    button.setIconSize(QSize(18, 18))
    button.clicked.connect(lambda checked=False, page_key=key: self.page_selected.emit(page_key))
    self._button_group.addButton(button)
    self._buttons[key] = button
    self._layout.addWidget(button)

  def add_stretch(self) -> None:
    """Add a flexible spacer at the end of the list.

    :return: None
    """
    self._layout.addStretch(1)

  def set_current_page(self, key: str) -> None:
    """Mark a page button as active.

    :param key: Page key.
    :return: None
    """
    button = self._buttons.get(key)
    if button is not None:
      button.setChecked(True)

  def set_icon_color(self, color: str) -> None:
    """Refresh icons for the current theme.

    :param color: New icon color.
    :return: None
    """
    self._icon_color = color
    icon_names = {
      "executor": "fa5s.bolt",
      "accounts": "fa5s.users",
      "scheduler": "fa5s.calendar-alt",
      "folders": "fa5s.folder-open",
      "videos": "fa5s.video",
      "settings": "fa5s.sliders-h",
      "logs": "fa5s.terminal",
    }
    for key, button in self._buttons.items():
      icon_name = icon_names.get(key)
      if icon_name is not None:
        button.setIcon(build_icon(icon_name, color))
