from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.tables.folders_table import FoldersTable
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon


class FoldersPage(PageLayout):
  """Folder management page.

  :param icon_color: Accent color used for icons.
  :return: None
  """

  TITLE = "Folder Management"
  DESCRIPTION = "Keep reusable source folders organized and only count videos after an explicit scan."

  def __init__(self, icon_color: str) -> None:
    """Initialize the folders page.

    :param icon_color: Accent color used for icons.
    :return: None
    """
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    """Build the folder management UI.

    :return: None
    """
    details_card = SurfaceCard()
    details_layout = QVBoxLayout(details_card)
    details_layout.setContentsMargins(18, 18, 18, 18)
    details_layout.setSpacing(12)
    details_layout.addWidget(SectionHeader(
      "Folder Details",
      "Choose a folder from the explorer, keep a reusable list, and scan on demand to update the video count.",
      "fa5s.folder-open",
      self._icon_color,
    ))

    action_row = QHBoxLayout()
    action_row.setContentsMargins(0, 0, 0, 0)
    action_row.setSpacing(10)
    self.add_folder_btn = QPushButton("Add")
    self.add_folder_btn.setProperty("class", "accent")
    self.add_folder_btn.setIcon(build_icon("fa5s.folder-plus", "#ffffff"))
    action_row.addWidget(self.add_folder_btn)
    action_row.addStretch(1)
    details_layout.addLayout(action_row)
    self.content_layout.addWidget(details_card)

    table_card = SurfaceCard()
    table_layout = QVBoxLayout(table_card)
    table_layout.setContentsMargins(18, 18, 18, 18)
    table_layout.setSpacing(12)
    table_layout.addWidget(SectionHeader(
      "Table Section",
      "Review saved folder paths, scan counts, and row actions in the folder list.",
      "fa5s.table",
      self._icon_color,
    ))
    self.folders_table = FoldersTable()
    self.folders_table.setMinimumHeight(420)
    table_layout.addWidget(self.folders_table, 1)
    self.content_layout.addWidget(table_card, 1)
