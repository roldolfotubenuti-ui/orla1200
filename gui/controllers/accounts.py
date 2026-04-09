from __future__ import annotations

import json
import random
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QHeaderView, QTableWidgetItem, QWidget

from gui.dialogs.account_dialog import AccountDialog


class AccountsControllerMixin:
  """Handle account management workflows."""

  def _load_accounts(self) -> None:
    """Scan cookie files and refresh account UI surfaces.

    :return: None
    """
    accounts = self._cookie_manager.list_accounts()
    current_username = self._window.account_dropdown.currentText()
    self._window.account_dropdown.clear()
    if accounts:
      self._window.account_dropdown.addItems(accounts)
      index = self._window.account_dropdown.findText(current_username)
      if index >= 0:
        self._window.account_dropdown.setCurrentIndex(index)
      else:
        self._window.account_dropdown.setCurrentIndex(0)
    else:
      self._logger.warning("No cookie files found in /cookies directory")
      self._window.accounts_page.accounts_current_metric.set_value("-")

    self._refresh_accounts_table(accounts)
    self._update_account_selection_summary()

  def _on_account_selected(self, username: str) -> None:
    """Handle account dropdown changes.

    :param username: Selected username.
    :return: None
    """
    if username:
      self._logger.info(f"Selected account: @{username}")
      self._window.accounts_page.accounts_current_metric.set_value(f"@{username}")
      self._window.accounts_page.accounts_current_metric.set_caption(
        "Used for the next execution"
      )
    else:
      self._window.accounts_page.accounts_current_metric.set_value("-")

    self._refresh_accounts_table()

  def _on_add_account_clicked(self) -> None:
    """Open the add-account dialog.

    :return: None
    """
    dialog = AccountDialog("Add account", parent=self._window)
    dialog.save_btn.clicked.connect(lambda: self._save_new_account(dialog))
    dialog.exec()

  def _on_edit_account_clicked(self) -> None:
    """Open an edit dialog for the selected account.

    :return: None
    """
    usernames = self._selected_account_usernames()
    if len(usernames) != 1:
      self._logger.warning("Select exactly one account to edit")
      return

    username = usernames[0]
    cookie_path = self._cookies_dir / f"@{username}-cookie.json"
    try:
      with open(cookie_path, "r", encoding="utf-8") as file_obj:
        cookie_text = file_obj.read()
    except OSError as exc:
      self._logger.error(f"Failed to read @{username}: {exc}")
      return

    dialog = AccountDialog(
      "Edit account",
      username=username,
      cookie_text=cookie_text,
      parent=self._window,
    )
    dialog.save_btn.clicked.connect(
      lambda: self._save_existing_account(username, dialog)
    )
    dialog.exec()

  def _on_random_account_requested(self) -> None:
    """Pick a random account from the selected rows or full list.

    :return: None
    """
    usernames = self._selected_account_usernames()
    if not usernames:
      usernames = self._cookie_manager.list_accounts()
    if not usernames:
      self._logger.warning("No accounts available for random selection")
      return

    username = random.choice(usernames)
    index = self._window.account_dropdown.findText(username)
    if index >= 0:
      self._window.account_dropdown.setCurrentIndex(index)
    self._logger.info(f"Random account selected: @{username}")

  def _refresh_accounts_table(self, accounts: list[str] | None = None) -> None:
    """Populate the account management table.

    :param accounts: Optional list of usernames.
    :return: None
    """
    if accounts is None:
      accounts = self._cookie_manager.list_accounts()

    table = self._window.accounts_table
    table.setRowCount(len(accounts))
    current_username = self._window.account_dropdown.currentText()

    for row_index, username in enumerate(accounts):
      cookie_path = self._cookies_dir / f"@{username}-cookie.json"
      stats = cookie_path.stat() if cookie_path.exists() else None
      date_added = self._format_human_datetime(
        stats.st_ctime if stats is not None else None
      )
      last_used = self._format_human_datetime(
        self._storage_service.last_used_timestamp(username)
      )
      status_text = "Selected" if username == current_username else "Available"
      status_role = "scheduled" if username == current_username else "pending"

      row_item = QTableWidgetItem(str(row_index + 1))
      row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 0, row_item)

      username_item = QTableWidgetItem(f"@{username}")
      username_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 1, username_item)

      date_added_item = QTableWidgetItem(date_added)
      date_added_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 2, date_added_item)

      last_used_item = QTableWidgetItem(last_used)
      last_used_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 3, last_used_item)

      status_item = QTableWidgetItem(status_text)
      status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 4, status_item)
      table.setCellWidget(
        row_index,
        4,
        self._build_role_badge(status_text, status_role),
      )
      table.setCellWidget(
        row_index,
        5,
        self._build_account_actions(username),
      )

    table.resizeColumnsToContents()
    table.setColumnWidth(4, max(table.columnWidth(4), 172))
    table.setColumnWidth(5, max(table.columnWidth(5), 148))
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.resizeRowsToContents()
    for row_index in range(table.rowCount()):
      table.setRowHeight(row_index, max(table.rowHeight(row_index), 68))
    self._window.accounts_page.accounts_total_metric.set_value(str(len(accounts)))

  def _build_account_actions(self, username: str) -> QWidget:
    """Build edit and delete buttons for the accounts table.

    :param username: Account username.
    :return: Action cell widget.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(8, 4, 8, 4)
    layout.setSpacing(10)
    layout.addWidget(
      self._build_table_icon_button(
        "fa5s.edit",
        lambda: self._edit_account(username),
      )
    )
    layout.addWidget(
      self._build_table_icon_button(
        "fa5s.trash-alt",
        lambda: self._delete_accounts([username]),
        danger=True,
      )
    )
    return container

  def _edit_account(self, username: str) -> None:
    """Select a row and open the edit dialog.

    :param username: Account username.
    :return: None
    """
    table = self._window.accounts_table
    for row in range(table.rowCount()):
      item = table.item(row, 1)
      if item is not None and item.text().lstrip("@") == username:
        table.selectRow(row)
        break
    self._on_edit_account_clicked()

  def _update_account_selection_summary(self) -> None:
    """Refresh metrics for the account table selection.

    :return: None
    """
    selected_count = len(self._selected_account_usernames())
    self._window.accounts_page.accounts_selected_metric.set_value(str(selected_count))

  def _save_new_account(self, dialog: AccountDialog) -> None:
    """Validate and save a new account cookie file.

    :param dialog: Active account dialog.
    :return: None
    """
    username, cookie_data = self._validate_account_dialog(dialog)
    if username is None or cookie_data is None:
      return

    cookie_path = self._cookies_dir / f"@{username}-cookie.json"
    if cookie_path.exists():
      dialog.show_error(
        f"Account @{username} already exists. Edit the existing profile instead."
      )
      return

    try:
      self._cookies_dir.mkdir(parents=True, exist_ok=True)
      with open(cookie_path, "w", encoding="utf-8") as file_obj:
        json.dump(cookie_data, file_obj, indent=2, ensure_ascii=False)
    except OSError as exc:
      dialog.show_error(f"Failed to save file: {exc}")
      return

    self._logger.success(f"Account @{username} added successfully")
    dialog.accept()
    self._load_accounts()
    index = self._window.account_dropdown.findText(username)
    if index >= 0:
      self._window.account_dropdown.setCurrentIndex(index)

  def _save_existing_account(
    self,
    original_username: str,
    dialog: AccountDialog,
  ) -> None:
    """Save account edits from the modal dialog.

    :param original_username: Original username.
    :param dialog: Active account dialog.
    :return: None
    """
    username, cookie_data = self._validate_account_dialog(dialog)
    if username is None or cookie_data is None:
      return

    original_path = self._cookies_dir / f"@{original_username}-cookie.json"
    target_path = self._cookies_dir / f"@{username}-cookie.json"
    if username != original_username and target_path.exists():
      dialog.show_error(f"Account @{username} already exists.")
      return

    try:
      self._cookies_dir.mkdir(parents=True, exist_ok=True)
      with open(target_path, "w", encoding="utf-8") as file_obj:
        json.dump(cookie_data, file_obj, indent=2, ensure_ascii=False)
      if original_path.exists() and original_path != target_path:
        original_path.unlink()
        self._storage_service.rename_account_artifacts(
          original_username,
          username,
        )
    except OSError as exc:
      dialog.show_error(f"Failed to save account: {exc}")
      return

    self._logger.success(f"Account @{original_username} updated")
    dialog.accept()
    self._load_accounts()
    index = self._window.account_dropdown.findText(username)
    if index >= 0:
      self._window.account_dropdown.setCurrentIndex(index)

  def _validate_account_dialog(
    self,
    dialog: AccountDialog,
  ) -> tuple[str | None, list[dict] | None]:
    """Validate dialog fields and parse cookie JSON.

    :param dialog: Account dialog.
    :return: Tuple of username and cookie list.
    """
    dialog.clear_error()
    username = dialog.get_username()
    cookie_text = dialog.get_cookie_text()

    if not username:
      dialog.show_error("Username is required.")
      return None, None
    if username.startswith("@"):
      username = username[1:]
    if not username:
      dialog.show_error("Username is required.")
      return None, None
    if not re.match(r"^[\w.]+$", username):
      dialog.show_error(
        "Username contains invalid characters. Use letters, numbers, dots, and underscores only."
      )
      return None, None

    if not cookie_text:
      dialog.show_error("Cookie JSON is required.")
      return None, None

    try:
      cookie_data = json.loads(cookie_text)
    except json.JSONDecodeError as exc:
      dialog.show_error(f"Invalid JSON: {exc}")
      return None, None

    if not isinstance(cookie_data, list):
      dialog.show_error("Cookie JSON must be a JSON array [ ... ].")
      return None, None
    if len(cookie_data) == 0:
      dialog.show_error("Cookie array is empty.")
      return None, None

    required_fields = ["name", "value", "domain", "path"]
    for index, entry in enumerate(cookie_data):
      if not isinstance(entry, dict):
        dialog.show_error(f"Cookie #{index} is not a JSON object.")
        return None, None
      for field in required_fields:
        value = entry.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
          dialog.show_error(
            f'Cookie #{index} is missing required field "{field}".'
          )
          return None, None

    return username, cookie_data

  def _on_delete_accounts_clicked(self) -> None:
    """Delete the selected accounts from disk.

    :return: None
    """
    usernames = self._selected_account_usernames()
    if not usernames:
      self._logger.warning("Select at least one account to delete")
      return
    self._delete_accounts(usernames)

  def _delete_accounts(self, usernames: list[str]) -> None:
    """Delete account cookie files and refresh the UI.

    :param usernames: Usernames to delete.
    :return: None
    """
    deleted = 0
    for username in usernames:
      cookie_path = self._cookies_dir / f"@{username}-cookie.json"
      try:
        if cookie_path.exists():
          cookie_path.unlink()
          deleted += 1
      except OSError as exc:
        self._logger.error(f"Failed to delete @{username}: {exc}")
    if deleted:
      self._logger.success(f"Deleted {deleted} account(s)")
    self._load_accounts()

  def _selected_account_usernames(self) -> list[str]:
    """Return unique usernames selected in the accounts table.

    :return: Selected usernames.
    """
    usernames: list[str] = []
    table = self._window.accounts_table
    for item in table.selectedItems():
      row = item.row()
      username_item = table.item(row, 1)
      if username_item is None:
        continue
      username = username_item.text().lstrip("@")
      if username not in usernames:
        usernames.append(username)
    return usernames
