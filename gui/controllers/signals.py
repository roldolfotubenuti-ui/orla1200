from __future__ import annotations


class ControllerSignalsMixin:
  """Connect GUI widget signals to controller handlers."""

  def _connect_signals(self) -> None:
    """Connect all widget signals to their handler methods.

    :return: None
    """
    window = self._window

    window.account_dropdown.currentTextChanged.connect(self._on_account_selected)
    window.random_account_btn.clicked.connect(self._on_random_account_requested)
    window.add_account_btn.clicked.connect(self._on_add_account_clicked)
    window.accounts_edit_btn.clicked.connect(self._on_edit_account_clicked)
    window.accounts_delete_btn.clicked.connect(self._on_delete_accounts_clicked)
    window.accounts_random_btn.clicked.connect(self._on_random_account_requested)
    window.accounts_table.itemSelectionChanged.connect(
      self._update_account_selection_summary
    )

    window.browse_button.clicked.connect(self._on_browse_clicked)
    window.scan_button.clicked.connect(self._on_scan_clicked)
    window.add_folder_btn.clicked.connect(self._on_browse_clicked)

    window.generate_btn.clicked.connect(self._on_generate_schedule)
    window.start_btn.clicked.connect(self._on_start_upload)
    window.stop_btn.clicked.connect(self._on_stop_clicked)
    window.pause_btn.clicked.connect(self._on_pause_resume)
    window.export_btn.clicked.connect(self._on_export_report)

    window.start_date.dateChanged.connect(lambda _: self._validate_date_range())
    window.end_date.dateChanged.connect(lambda _: self._validate_date_range())
    window.start_date.dateChanged.connect(lambda _: self._update_time_options())

    window.time_start_hour.currentTextChanged.connect(
      lambda _: self._update_start_minutes()
    )
    window.time_start_hour.currentTextChanged.connect(
      lambda _: self._validate_time_selection()
    )
    window.time_start_minute.currentTextChanged.connect(
      lambda _: self._validate_time_selection()
    )

    window.limit_spin.valueChanged.connect(self._on_limit_changed)
    window.caption_input.textChanged.connect(self._update_caption_preview)

    window.filter_pending_check.stateChanged.connect(
      lambda _: self._on_filter_changed()
    )
    window.filter_scheduled_check.stateChanged.connect(
      lambda _: self._on_filter_changed()
    )
    window.filter_published_check.stateChanged.connect(
      lambda _: self._on_filter_changed()
    )
    window.filter_failed_check.stateChanged.connect(
      lambda _: self._on_filter_changed()
    )

    window.video_table.horizontalHeader().sectionClicked.connect(
      self._on_header_clicked
    )
