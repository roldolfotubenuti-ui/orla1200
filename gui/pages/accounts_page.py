from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.components.headers import SectionHeader
from gui.layouts.page_layout import PageLayout
from gui.tables.accounts_table import AccountsTable
from gui.widgets.cards import SurfaceCard
from gui.widgets.icon import build_icon


class InlineStat(QWidget):
  """Inline metric text block used above data tables.

  :param title: Metric title.
  :param value: Initial value.
  :param caption: Supporting caption.
  :param parent: Parent widget.
  :return: None
  """

  def __init__(
    self,
    title: str,
    value: str,
    caption: str,
    parent: QWidget | None = None,
  ) -> None:
    """Initialize the inline stat widget.

    :param title: Metric title.
    :param value: Initial value.
    :param caption: Supporting caption.
    :param parent: Parent widget.
    :return: None
    """
    super().__init__(parent)
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    self.title_label = QLabel(title)
    self.title_label.setProperty("class", "inline-stat-title")
    layout.addWidget(self.title_label)

    self.value_label = QLabel(value)
    self.value_label.setProperty("class", "inline-stat-value")
    layout.addWidget(self.value_label)

    self.caption_label = QLabel(caption)
    self.caption_label.setProperty("class", "inline-stat-caption")
    layout.addWidget(self.caption_label)

  def set_value(self, value: str) -> None:
    """Update the inline stat value.

    :param value: New value.
    :return: None
    """
    self.value_label.setText(value)

  def set_caption(self, caption: str) -> None:
    """Update the supporting caption.

    :param caption: New supporting caption.
    :return: None
    """
    self.caption_label.setText(caption)


class AccountsPage(PageLayout):
  """Account management page.

  :param icon_color: Accent color used for icons.
  :return: None
  """

  TITLE = "Account Management"
  DESCRIPTION = "Manage TikTok account cookies, inspect account activity, and select a random account from your active pool."

  def __init__(self, icon_color: str) -> None:
    """Initialize the accounts page.

    :param icon_color: Accent color used for icons.
    :return: None
    """
    super().__init__()
    self._icon_color = icon_color
    self._build_ui()

  def _build_ui(self) -> None:
    """Build the accounts page UI.

    :return: None
    """
    details_card = SurfaceCard()
    details_layout = QVBoxLayout(details_card)
    details_layout.setContentsMargins(18, 18, 18, 18)
    details_layout.setSpacing(12)
    details_layout.addWidget(SectionHeader(
      "Account Details",
      '',
      "fa5s.users",
      self._icon_color,
    ))

    stats_row = QHBoxLayout()
    stats_row.setContentsMargins(0, 0, 0, 0)
    stats_row.setSpacing(28)
    self.accounts_total_metric = InlineStat("Account", "0", "Cookie profiles")
    self.accounts_selected_metric = InlineStat("Selected", "0", "Rows highlighted")
    self.accounts_current_metric = InlineStat("Current", "-", "Used for the next execution")
    stats_row.addWidget(self.accounts_total_metric)
    stats_row.addWidget(self.accounts_selected_metric)
    stats_row.addWidget(self.accounts_current_metric)
    stats_row.addStretch(1)
    details_layout.addLayout(stats_row)

    actions = QHBoxLayout()
    actions.setContentsMargins(0, 0, 0, 0)
    actions.setSpacing(10)
    self.add_account_btn = QPushButton("Add")
    self.add_account_btn.setProperty("class", "accent")
    self.add_account_btn.setIcon(build_icon("fa5s.user-plus", "#ffffff"))
    actions.addWidget(self.add_account_btn)

    self.accounts_edit_btn = QPushButton("Edit")
    self.accounts_edit_btn.setIcon(build_icon("fa5s.edit", self._icon_color))
    actions.addWidget(self.accounts_edit_btn)

    self.accounts_delete_btn = QPushButton("Delete")
    self.accounts_delete_btn.setProperty("class", "danger")
    self.accounts_delete_btn.setIcon(build_icon("fa5s.trash-alt", "#ffffff"))
    actions.addWidget(self.accounts_delete_btn)

    self.accounts_random_btn = QPushButton("Shuffle")
    self.accounts_random_btn.setIcon(build_icon("fa5s.random", self._icon_color))
    actions.addWidget(self.accounts_random_btn)

    actions.addStretch(1)
    info_label = QLabel("Tip: multi-select rows to delete several cookie profiles at once.")
    info_label.setProperty("class", "muted")
    actions.addWidget(info_label)
    details_layout.addLayout(actions)
    self.content_layout.addWidget(details_card)

    table_card = SurfaceCard()
    table_layout = QVBoxLayout(table_card)
    table_layout.setContentsMargins(18, 18, 18, 18)
    table_layout.setSpacing(12)
    table_layout.addWidget(SectionHeader(
      "Table Section",
      "Review usernames, activity dates, status badges, and account actions in the user list.",
      "fa5s.table",
      self._icon_color,
    ))
    self.accounts_table = AccountsTable()
    self.accounts_table.setMinimumHeight(460)
    table_layout.addWidget(self.accounts_table, 1)
    self.content_layout.addWidget(table_card, 1)
