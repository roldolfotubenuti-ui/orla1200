from __future__ import annotations

import re
from collections.abc import Callable

from PyQt6.QtCore import QStringListModel, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QCompleter, QTextEdit, QWidget


class HashtagTextEdit(QTextEdit):
  """Multiline caption editor with hashtag suggestions.

  :param parent: Parent widget.
  :return: None
  """

  def __init__(self, parent: QWidget | None = None) -> None:
    """Initialize the editor.

    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self._provider: Callable[[str], list[str]] | None = None
    self._model = QStringListModel(self)
    self._completer = QCompleter(self._model, self)
    self._completer.setWidget(self)
    self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    self._completer.activated.connect(self._insert_completion)
    self.setAcceptRichText(False)

  def set_suggestion_provider(
    self,
    provider: Callable[[str], list[str]],
  ) -> None:
    """Set the callable used to resolve tag suggestions.

    :param provider: Suggestion provider.
    :return: None
    """
    self._provider = provider

  def keyPressEvent(self, event) -> None:  # noqa: N802
    """Handle typing and show completion popup when needed.

    :param event: Key event.
    :return: None
    """
    if self._completer.popup().isVisible() and event.key() in (
      Qt.Key.Key_Enter,
      Qt.Key.Key_Return,
      Qt.Key.Key_Tab,
      Qt.Key.Key_Escape,
    ):
      event.ignore()
      return

    super().keyPressEvent(event)
    self._refresh_popup()

  def focusOutEvent(self, event) -> None:  # noqa: N802
    """Hide the popup when the editor loses focus.

    :param event: Focus event.
    :return: None
    """
    self._completer.popup().hide()
    super().focusOutEvent(event)

  def _refresh_popup(self) -> None:
    """Update popup suggestions for the active hashtag fragment.

    :return: None
    """
    if self._provider is None:
      return

    fragment = self._current_fragment()
    if fragment is None:
      self._completer.popup().hide()
      return

    prefix, _, _ = fragment
    suggestions = self._provider(prefix)
    if not suggestions:
      self._completer.popup().hide()
      return

    self._model.setStringList([f"#{tag}" for tag in suggestions])
    rect = self.cursorRect()
    rect.setWidth(max(220, self._completer.popup().sizeHintForColumn(0) + 24))
    self._completer.complete(rect)

  def _current_fragment(self) -> tuple[str, int, int] | None:
    """Return the active hashtag fragment around the cursor.

    :return: Tuple of fragment, start, and end positions.
    """
    cursor = self.textCursor()
    position = cursor.position()
    text = self.toPlainText()[:position]
    match = re.search(r"(?:^|\s)#([A-Za-z0-9_]*)$", text)
    if match is None:
      return None
    start = match.start(1) - 1
    end = position
    return match.group(1), start, end

  def _insert_completion(self, completion: str) -> None:
    """Insert the chosen hashtag suggestion.

    :param completion: Completed suggestion text.
    :return: None
    """
    fragment = self._current_fragment()
    if fragment is None:
      return

    _, start, end = fragment
    cursor = self.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    cursor.insertText(completion)
    if not self.toPlainText()[cursor.position():cursor.position() + 1].isspace():
      cursor.insertText(" ")
    self.setTextCursor(cursor)
