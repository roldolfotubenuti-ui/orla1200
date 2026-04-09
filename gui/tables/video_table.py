from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
  QAbstractItemView,
  QHBoxLayout,
  QLabel,
  QHeaderView,
  QTableWidget,
  QWidget,
)


class VideoTable(QTableWidget):
  """Styled video table used by the executor and library pages.

  :param read_only: Whether the table should disable editing and selection.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    read_only: bool = False,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the video table.

    :param read_only: Whether the table should be read only.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setProperty("class", "grid-table")
    self.setColumnCount(6)
    self.setHorizontalHeaderLabels([
      "#",
      "Filename",
      "Size",
      "Schedule",
      "Published",
      "Status",
    ])
    self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    self.setAlternatingRowColors(False)
    self.setSortingEnabled(False)
    self.setShowGrid(True)
    self.viewport().setAutoFillBackground(True)
    self.verticalHeader().setVisible(False)
    self.verticalHeader().setDefaultSectionSize(50)
    self.horizontalHeader().setHighlightSections(False)
    self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
    self.setColumnWidth(5, 110)
    self.horizontalHeader().setStretchLastSection(False)
    if read_only:
      self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
      self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)


def build_status_badge(status: str) -> QWidget:
  """Build a status badge widget for a table cell.

  :param status: Video status text.
  :return: Badge widget.
  """
  role_map = {
    "Pending": "pending",
    "Scheduled": "scheduled",
    "Published": "published",
    "Failed": "failed",
    "Ready": "pending",
  }
  container = QWidget()
  layout = QHBoxLayout(container)
  layout.setContentsMargins(4, 4, 4, 4)
  layout.setSpacing(0)
  layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

  label = QLabel(status)
  label.setProperty("class", "chip")
  label.setProperty("role", role_map.get(status, "pending"))
  label.setAlignment(Qt.AlignmentFlag.AlignCenter)
  layout.addWidget(label)
  return container
