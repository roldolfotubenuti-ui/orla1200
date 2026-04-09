from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QWidget


class AccountsTable(QTableWidget):
  """Table used for account management.

  :param parent: Parent widget.
  :return: None
  """

  def __init__(self, parent: QWidget | None = None) -> None:
    """Initialize the accounts table.

    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    self.setProperty("class", "grid-table")
    self.setColumnCount(6)
    self.setHorizontalHeaderLabels([
      "#",
      "Username",
      "Date Added",
      "Last Used",
      "Status",
      "Actions",
    ])
    self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    self.setShowGrid(True)
    self.viewport().setAutoFillBackground(True)
    self.verticalHeader().setVisible(False)
    self.verticalHeader().setDefaultSectionSize(58)
    self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
    self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
    self.setColumnWidth(5, 132)
    self.setColumnWidth(4, 100)
