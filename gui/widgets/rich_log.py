from __future__ import annotations

from html import escape

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit, QWidget

try:
  from rich.text import Text
except ImportError:
  class Text:  # type: ignore[override]
    """Minimal fallback used when ``rich`` is unavailable.

    :param plain: Plain text content.
    :param style: Unused style value.
    :return: None
    """

    def __init__(self, plain: str, style: str = "") -> None:
      """Store plain text for compatibility.

      :param plain: Plain text content.
      :param style: Unused style value.
      :return: None
      """
      self.plain = plain

from gui.theme.palette import ThemePalette


class RichLogView(QTextEdit):
  """Read-only rich log view backed by ``rich`` text formatting.

  :param palette: Active theme palette.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    palette: ThemePalette,
    terminal_mode: bool = False,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the log view.

    :param palette: Active theme palette.
    :param terminal_mode: Whether the log should use terminal color rules.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self._palette = palette
    self._terminal_mode = terminal_mode
    self.setReadOnly(True)
    self.setProperty("class", "log-view")

  def set_palette_data(self, palette: ThemePalette) -> None:
    """Update colors used for subsequent log lines.

    :param palette: Active theme palette.
    :return: None
    """
    self._palette = palette

  def append_message(self, message: str, level: int = 20) -> None:
    """Append a styled message to the log view.

    :param message: Log line.
    :param level: Numeric log level.
    :return: None
    """
    rich_text = Text(message, style=self._rich_style(level))
    color = self._css_color(level)
    weight = "700" if level >= 30 else "500"
    self.append(
      f'<span style="color: {color}; font-weight: {weight};">'
      f"{escape(rich_text.plain)}</span>"
    )
    self.moveCursor(QTextCursor.MoveOperation.End)

  def _rich_style(self, level: int) -> str:
    """Map a log level to a rich style string.

    :param level: Numeric log level.
    :return: Rich style string.
    """
    if self._terminal_mode:
      return self._terminal_color(level)
    if level >= 40:
      return f"bold {self._palette.error}"
    if level >= 30:
      return f"bold {self._palette.warning}"
    if level == 25:
      return f"bold {self._palette.success}"
    if level <= 10:
      return self._palette.text_secondary
    return self._palette.text_primary

  def _css_color(self, level: int) -> str:
    """Map a log level to a CSS color.

    :param level: Numeric log level.
    :return: CSS color value.
    """
    if self._terminal_mode:
      return self._terminal_color(level)
    if level >= 40:
      return self._palette.error
    if level >= 30:
      return self._palette.warning
    if level == 25:
      return self._palette.success
    if level <= 10:
      return self._palette.text_secondary
    return self._palette.text_primary

  def _terminal_color(self, level: int) -> str:
    """Map a log level to terminal-friendly colors.

    :param level: Numeric log level.
    :return: CSS color value.
    """
    if level >= 40:
      return "#fca5a5"
    if level >= 30:
      return "#fbbf24"
    if level == 25:
      return "#86efac"
    if level <= 10:
      return "#a6b5c8"
    return self._palette.terminal_text
