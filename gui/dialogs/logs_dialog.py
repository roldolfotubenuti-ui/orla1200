from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
  QCheckBox,
  QDialog,
  QFileDialog,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QPushButton,
  QVBoxLayout,
  QWidget,
)

from gui.theme.palette import ThemePalette
from gui.widgets.rich_log import RichLogView


class LogsDialog(QDialog):
  """Dedicated execution logs viewer dialog with filtering, clear view, and persistent log reload.

  :param palette: Active theme palette.
  :param log_file_path: Path to persistent execution log file.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    palette: ThemePalette,
    log_file_path: Path | None = None,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the logs viewer dialog.

    :param palette: Active theme palette.
    :param log_file_path: Path to persistent execution log file.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self._palette = palette
    self._log_file_path = log_file_path
    self._entries: list[tuple[str, int]] = []

    self.setWindowTitle("TikTok Scheduler — Execution Logs")
    self.setModal(False)
    self.resize(880, 560)

    layout = QVBoxLayout(self)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(12)

    header_row = QHBoxLayout()
    title_label = QLabel("Execution Logs & Diagnostics")
    title_label.setProperty("class", "page-title")
    header_row.addWidget(title_label)
    header_row.addStretch(1)

    if self._log_file_path is not None:
      path_label = QLabel(f"File: {self._log_file_path.name}")
      path_label.setProperty("class", "muted")
      header_row.addWidget(path_label)
    layout.addLayout(header_row)

    filter_row = QHBoxLayout()
    filter_row.setSpacing(12)

    self.filter_info_check = QCheckBox("INFO")
    self.filter_info_check.setChecked(True)
    self.filter_success_check = QCheckBox("SUCCESS")
    self.filter_success_check.setChecked(True)
    self.filter_warning_check = QCheckBox("WARNING")
    self.filter_warning_check.setChecked(True)
    self.filter_error_check = QCheckBox("ERROR")
    self.filter_error_check.setChecked(True)
    self.filter_debug_check = QCheckBox("DEBUG")
    self.filter_debug_check.setChecked(True)

    for cb in (
      self.filter_info_check,
      self.filter_success_check,
      self.filter_warning_check,
      self.filter_error_check,
      self.filter_debug_check,
    ):
      cb.stateChanged.connect(lambda _: self._rebuild_view())
      filter_row.addWidget(cb)

    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("Filter log messages...")
    self.search_input.textChanged.connect(lambda _: self._rebuild_view())
    filter_row.addWidget(self.search_input, 1)
    layout.addLayout(filter_row)

    self.log_view = RichLogView(palette, terminal_mode=True, parent=self)
    self.log_view.setProperty("surface", "terminal")
    layout.addWidget(self.log_view, 1)

    footer_row = QHBoxLayout()
    footer_row.setSpacing(10)

    self.count_label = QLabel("0 log entries")
    self.count_label.setProperty("class", "muted")
    footer_row.addWidget(self.count_label)
    footer_row.addStretch(1)

    self.reload_btn = QPushButton("Load Full History")
    self.reload_btn.clicked.connect(self.load_persistent_history)
    footer_row.addWidget(self.reload_btn)

    self.export_btn = QPushButton("Export Logs")
    self.export_btn.clicked.connect(self._export_logs)
    footer_row.addWidget(self.export_btn)

    self.clear_view_btn = QPushButton("Clear View")
    self.clear_view_btn.setToolTip(
      "Clears the current log view without deleting persistent log files."
    )
    self.clear_view_btn.clicked.connect(self.clear_view_only)
    footer_row.addWidget(self.clear_view_btn)

    self.close_btn = QPushButton("Close")
    self.close_btn.setProperty("class", "accent")
    self.close_btn.clicked.connect(self.hide)
    footer_row.addWidget(self.close_btn)

    layout.addLayout(footer_row)

  def set_palette_data(self, palette: ThemePalette) -> None:
    """Update theme palette for the log viewer.

    :param palette: Active theme palette.
    :return: None
    """
    self._palette = palette
    self.log_view.set_palette_data(palette)

  def set_entries(self, entries: list[tuple[str, int]]) -> None:
    """Replace current view buffer with the given entries and render.

    :param entries: List of (message, level) tuples.
    :return: None
    """
    self._entries = list(entries)
    self._rebuild_view()

  def append_entry(self, message: str, level: int) -> None:
    """Append a real-time log entry to the dialog.

    :param message: Formatted log line.
    :param level: Numeric log level.
    :return: None
    """
    self._entries.append((message, level))
    if self._matches_filter(message, level):
      self.log_view.append_message(message, level)
    self._update_count_label()

  def clear_view_only(self) -> None:
    """Clear the visible log buffer in the dialog without touching persistent files on disk."""
    self._entries.clear()
    self.log_view.clear()
    self._update_count_label()

  def load_persistent_history(self) -> None:
    """Load all historical entries from the persistent log file on disk."""
    if self._log_file_path is None or not self._log_file_path.exists():
      return
    try:
      lines = self._log_file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
      return

    loaded: list[tuple[str, int]] = []
    for line in lines:
      if not line.strip():
        continue
      level = self._infer_level(line)
      loaded.append((line, level))
    self._entries = loaded
    self._rebuild_view()

  @staticmethod
  def _infer_level(line: str) -> int:
    """Infer numeric log level from a formatted log line."""
    upper = line.upper()
    if " ERROR " in upper or " CRITICAL " in upper or "TRACEBACK" in upper:
      return 40
    if " WARNING " in upper:
      return 30
    if " SUCCESS " in upper:
      return 25
    if " DEBUG " in upper:
      return 10
    return 20

  def _matches_filter(self, message: str, level: int) -> bool:
    """Return True if the entry matches active level checkboxes and search query."""
    if level >= 40 and not self.filter_error_check.isChecked():
      return False
    elif 30 <= level < 40 and not self.filter_warning_check.isChecked():
      return False
    elif level == 25 and not self.filter_success_check.isChecked():
      return False
    elif 20 <= level < 25 and not self.filter_info_check.isChecked():
      return False
    elif level < 20 and not self.filter_debug_check.isChecked():
      return False

    query = self.search_input.text().strip().lower()
    if query and query not in message.lower():
      return False
    return True

  def _rebuild_view(self) -> None:
    """Re-render the log view according to active filters."""
    self.log_view.clear()
    shown = 0
    for message, level in self._entries:
      if self._matches_filter(message, level):
        self.log_view.append_message(message, level)
        shown += 1
    self._update_count_label(shown)

  def _update_count_label(self, shown: int | None = None) -> None:
    """Update the footer entry counter."""
    total = len(self._entries)
    if shown is None:
      self.count_label.setText(f"{total} log entries")
    else:
      self.count_label.setText(f"Showing {shown} of {total} log entries")

  def _export_logs(self) -> None:
    """Export currently loaded log entries to a text file."""
    file_path, _ = QFileDialog.getSaveFileName(
      self,
      "Export Execution Logs",
      f"tks_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
      "Log Files (*.log *.txt);;All Files (*)",
    )
    if not file_path:
      return
    try:
      with open(file_path, "w", encoding="utf-8") as fh:
        for msg, level in self._entries:
          if self._matches_filter(msg, level):
            fh.write(msg + "\n")
    except OSError:
      pass
