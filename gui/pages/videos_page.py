from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.tables.video_table import VideoTable


class VideosPage(PageLayout):
  """Interactive video queue page.

  :param icon_color: Accent color used for icons.
  :return: None
  """

  TITLE = "Video Table"
  DESCRIPTION = "Review the scanned queue, filter rows by publishing state, and control the pending selection used for schedule generation."

  def __init__(self, icon_color: str) -> None:
    """Initialize the video queue page.

    :param icon_color: Accent color used for icons.
    :return: None
    """
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    """Build the video queue page UI.

    :return: None
    """
    self.content_layout.addWidget(SectionHeader(
      "Video queue",
      "Manage pending rows here while the Main tab stays focused on account, folder, caption, and terminal activity.",
      "fa5s.video",
      self._icon_color,
    ))

    meta_row = QHBoxLayout()
    meta_row.setContentsMargins(0, 0, 0, 0)
    meta_row.setSpacing(16)
    self.video_total_label = QLabel("Total: 0")
    self.video_total_label.setProperty("class", "muted")
    self.video_selected_label = QLabel("Selected: 0")
    self.video_selected_label.setProperty("class", "muted")
    meta_row.addWidget(self.video_total_label)
    meta_row.addWidget(self.video_selected_label)
    meta_row.addStretch(1)
    self.content_layout.addLayout(meta_row)

    filters_row = QHBoxLayout()
    filters_row.setContentsMargins(0, 0, 0, 0)
    filters_row.setSpacing(16)
    self.filter_pending_check = QCheckBox("Pending")
    self.filter_pending_check.setChecked(True)
    self.filter_scheduled_check = QCheckBox("Scheduled")
    self.filter_scheduled_check.setChecked(True)
    self.filter_published_check = QCheckBox("Published")
    self.filter_published_check.setChecked(True)
    self.filter_failed_check = QCheckBox("Failed")
    self.filter_failed_check.setChecked(True)
    filters_row.addWidget(self.filter_pending_check)
    filters_row.addWidget(self.filter_scheduled_check)
    filters_row.addWidget(self.filter_published_check)
    filters_row.addWidget(self.filter_failed_check)
    filters_row.addStretch(1)
    self.content_layout.addLayout(filters_row)

    self.video_table = VideoTable(read_only=False)
    self.video_table.setMinimumHeight(520)
    self.content_layout.addWidget(self.video_table, 1)
