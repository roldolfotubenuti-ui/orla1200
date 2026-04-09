from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QTableWidgetItem


class FolderControllerMixin:
  """Handle saved folder management workflows."""

  def _load_saved_folder(self) -> None:
    """Load saved folders and refresh dropdown and table views.

    :return: None
    """
    records = self._storage_service.read_folder_records(self.TARGET_PATH_FILE)
    self._refresh_folder_views(records)

  def _refresh_folder_views(self, records: list[dict]) -> None:
    """Refresh the folder dropdown and management table.

    :param records: Folder records.
    :return: None
    """
    current_folder = self._window.folder_dropdown.currentText()
    self._window.folder_dropdown.clear()
    self._window.folder_dropdown.addItems([record["path"] for record in records])
    current_index = self._window.folder_dropdown.findText(current_folder)
    if current_index >= 0:
      self._window.folder_dropdown.setCurrentIndex(current_index)

    table = self._window.folders_table
    table.setRowCount(len(records))
    for row_index, record in enumerate(records):
      row_item = QTableWidgetItem(str(row_index + 1))
      row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
      table.setItem(row_index, 0, row_item)
      table.setItem(
        row_index,
        1,
        QTableWidgetItem(record["path"]),
      )
      table.setItem(
        row_index,
        2,
        QTableWidgetItem(self._format_iso_datetime(record.get("date_added", ""))),
      )
      total_videos = record.get("total_videos")
      table.setItem(
        row_index,
        3,
        QTableWidgetItem("-" if total_videos is None else str(total_videos)),
      )
      table.setCellWidget(
        row_index,
        4,
        self._wrap_centered_cell_widget(
          self._build_table_icon_button(
            "fa5s.search",
            lambda folder_path=record["path"]: self._scan_saved_folder(folder_path),
          )
        ),
      )
      table.setCellWidget(
        row_index,
        5,
        self._wrap_centered_cell_widget(
          self._build_table_icon_button(
            "fa5s.trash-alt",
            lambda folder_path=record["path"]: self._delete_saved_folder(folder_path),
            danger=True,
          )
        ),
      )

    table.resizeColumnsToContents()
    table.setColumnWidth(4, max(table.columnWidth(4), 78))
    table.setColumnWidth(5, max(table.columnWidth(5), 78))
    table.resizeRowsToContents()
    for row_index in range(table.rowCount()):
      table.setRowHeight(row_index, max(table.rowHeight(row_index), 68))

  def _save_folder_path(self, folder: str) -> None:
    """Add a folder to the saved folder list.

    :param folder: Folder path.
    :return: None
    """
    records = self._storage_service.read_folder_records(self.TARGET_PATH_FILE)
    for record in records:
      if record["path"] == folder:
        self._refresh_folder_views(records)
        return

    records.append({
      "path": folder,
      "date_added": datetime.now().isoformat(),
      "total_videos": None,
    })
    self._storage_service.write_folder_records(self.TARGET_PATH_FILE, records)
    self._refresh_folder_views(records)

  def _scan_saved_folder(self, folder: str) -> None:
    """Select and scan a saved folder.

    :param folder: Folder path.
    :return: None
    """
    index = self._window.folder_dropdown.findText(folder)
    if index >= 0:
      self._window.folder_dropdown.setCurrentIndex(index)
    self._on_scan_clicked()

  def _delete_saved_folder(self, folder: str) -> None:
    """Delete a saved folder record.

    :param folder: Folder path.
    :return: None
    """
    records = [
      record
      for record in self._storage_service.read_folder_records(self.TARGET_PATH_FILE)
      if record["path"] != folder
    ]
    self._storage_service.write_folder_records(self.TARGET_PATH_FILE, records)
    self._refresh_folder_views(records)

  def _update_folder_record_total(self, folder: str, total_videos: int) -> None:
    """Update the cached video count for a saved folder.

    :param folder: Folder path.
    :param total_videos: Scanned video count.
    :return: None
    """
    records = self._storage_service.read_folder_records(self.TARGET_PATH_FILE)
    for record in records:
      if record["path"] == folder:
        record["total_videos"] = total_videos
        break
    self._storage_service.write_folder_records(self.TARGET_PATH_FILE, records)
    self._refresh_folder_views(records)

  def _on_browse_clicked(self) -> None:
    """Open the folder dialog and save the selected folder.

    :return: None
    """
    folder = QFileDialog.getExistingDirectory(self._window, "Select Video Folder")
    if folder:
      self._save_folder_path(folder)
      dropdown = self._window.folder_dropdown
      index = dropdown.findText(folder)
      if index >= 0:
        dropdown.setCurrentIndex(index)
      self._logger.info(f"Selected folder: {folder}")
