from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from gui.widgets.icon import build_icon


class ControllerUiMixin:
  """Shared UI helpers for controller mixins."""

  def _build_table_icon_button(
    self,
    icon_name: str,
    callback: Callable[[], None],
    danger: bool = False,
  ) -> QPushButton:
    """Create a compact icon button for table action cells.

    :param icon_name: qtawesome icon name.
    :param callback: Click callback.
    :param danger: Whether to apply danger styling.
    :return: Configured push button.
    """
    palette = self._window._theme_manager.palette
    button = QPushButton()
    button.setFixedSize(34, 34)
    button.setProperty("class", "danger" if danger else "icon-button")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    color = "#ffffff" if danger else palette.text_secondary
    button.setIcon(build_icon(icon_name, color))
    button.clicked.connect(callback)
    return button

  def _build_role_badge(self, text: str, role: str) -> QWidget:
    """Build a small badge widget for management tables.

    :param text: Badge text.
    :param role: Visual role.
    :return: Badge widget.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 6, 4, 6)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label = QLabel(text)
    label.setProperty("class", "chip")
    label.setProperty("role", role)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    return container

  def _wrap_centered_cell_widget(self, widget: QWidget) -> QWidget:
    """Wrap a widget in a centered table cell container.

    :param widget: Inner widget.
    :return: Container widget.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 6, 4, 6)
    layout.setSpacing(0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(widget)
    return container

  def _format_human_datetime(self, timestamp: float | None) -> str:
    """Format a timestamp into a readable UI string.

    :param timestamp: POSIX timestamp.
    :return: Human-readable string.
    """
    if timestamp is None:
      return "-"
    return datetime.fromtimestamp(timestamp).strftime("%d %b %Y %H:%M")

  def _format_iso_datetime(self, raw_value: str) -> str:
    """Format an ISO datetime string for the UI.

    :param raw_value: ISO datetime string.
    :return: Human-readable string.
    """
    if not raw_value:
      return "-"
    try:
      return datetime.fromisoformat(raw_value).strftime("%d %b %Y %H:%M")
    except ValueError:
      return raw_value
