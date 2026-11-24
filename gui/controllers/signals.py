from __future__ import annotations


class ControllerSignalsMixin:
  """Connect GUI widget signals to controller handlers."""

  def _connect_signals(self) -> None:
    """Connect all widget signals to their handler methods.

    :return: None
    """
    window = self._window

    # Top Stepper bar navigation
    if hasattr(window, "stepper_bar"):
      window.stepper_bar.step_clicked.connect(self._on_stepper_clicked)

    # Page 1: Accounts
    window.account_dropdown.currentTextChanged.connect(self._on_account_selected)
    window.random_account_btn.clicked.connect(self._on_random_account_requested)
    window.add_account_btn.clicked.connect(self._on_add_account_clicked)
    if hasattr(window, "import_json_btn"):
      window.import_json_btn.clicked.connect(self._on_import_json_clicked)
    window.accounts_edit_btn.clicked.connect(self._on_edit_account_clicked)
    window.accounts_delete_btn.clicked.connect(self._on_delete_accounts_clicked)
    window.accounts_random_btn.clicked.connect(self._on_random_account_requested)
    window.accounts_table.itemSelectionChanged.connect(
      self._update_account_selection_summary
    )
    if hasattr(window.accounts_page, "account_card_selected"):
      window.accounts_page.account_card_selected.connect(self._on_account_card_selected)
      window.accounts_page.account_card_edit.connect(self._edit_account)
      window.accounts_page.account_card_delete.connect(lambda u: self._delete_accounts([u]))
    if hasattr(window.accounts_page, "open_publications_requested") and hasattr(window, "studio_page"):
      window.accounts_page.open_publications_requested.connect(
        lambda: (self._go_to_wizard_step(1), self._refresh_studio_publications(), window.studio_page.show_publications())
      )
    if hasattr(window.accounts_page, "switch_account_requested"):
      window.accounts_page.switch_account_requested.connect(self._load_accounts)

    # TikTok Studio Page (Opção 1 - Imagens 1, 2, 3, 4)
    if hasattr(window, "studio_page"):
      window.studio_page.files_dropped.connect(self._on_files_dropped)
      window.studio_page.select_videos_requested.connect(self._on_select_videos_dialog)
      window.studio_page.select_folder_requested.connect(self._on_browse_clicked)
      window.studio_page.clear_videos_requested.connect(self._on_clear_loaded_videos)
      window.studio_page.back_requested.connect(lambda: self._go_to_wizard_step(0))
      window.studio_page.publish_requested.connect(self._on_studio_publish_clicked)
      window.studio_page.caption_updated.connect(self._on_studio_caption_updated)
      window.studio_page.schedule_updated.connect(self._on_studio_schedule_updated)
      window.studio_page.visibility_updated.connect(self._on_studio_visibility_updated)
      window.studio_page.substitute_file_requested.connect(self._on_studio_substitute_file)
      window.studio_page.remove_video_requested.connect(self._on_remove_loaded_video)
      window.studio_page.batch_schedule_requested.connect(self._on_studio_batch_schedule)
      window.studio_page.reorder_requested.connect(self._on_studio_reorder)
      window.studio_page.publications_requested.connect(
        lambda: (self._refresh_studio_publications(), window.studio_page.show_publications())
      )
      window.studio_page.refresh_publications_requested.connect(self._refresh_studio_publications)
      window.studio_page.pause_upload_requested.connect(self._on_pause_resume)
      window.studio_page.resume_upload_requested.connect(self._on_resume_clicked)
      window.studio_page.stop_upload_requested.connect(self._on_stop_clicked)
      if hasattr(window, "_open_logs_dialog"):
        window.studio_page.logs_requested.connect(window._open_logs_dialog)

    # Page 2: Load Videos (Compatibility)
    window.browse_button.clicked.connect(self._on_browse_clicked)
    window.scan_button.clicked.connect(self._on_scan_clicked)
    window.add_folder_btn.clicked.connect(self._on_browse_clicked)
    if hasattr(window, "videos_page"):
      window.videos_page.files_dropped.connect(self._on_files_dropped)
      window.videos_page.select_videos_requested.connect(self._on_select_videos_dialog)
      window.videos_page.move_up_requested.connect(self._on_move_video_up)
      window.videos_page.move_down_requested.connect(self._on_move_video_down)
      window.videos_page.remove_video_requested.connect(self._on_remove_loaded_video)
      window.videos_page.clear_videos_requested.connect(self._on_clear_loaded_videos)
      window.videos_page.back_requested.connect(lambda: self._go_to_wizard_step(0))
      window.videos_page.continue_requested.connect(self._on_step2_continue)

    # Page 3: Configure Days, Times, Captions & Distribute
    window.generate_btn.clicked.connect(self._on_wizard_distribute)
    if hasattr(window, "config_page"):
      window.config_page.per_video_caption_changed.connect(self._on_per_video_caption_changed)
      window.config_page.back_requested.connect(lambda: self._go_to_wizard_step(1))
      window.config_page.continue_requested.connect(self._on_step3_continue)

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
    if hasattr(window, "prefix_caption_check"):
      window.prefix_caption_check.stateChanged.connect(
        lambda _: self._update_caption_preview()
      )

    # Page 4: Review Scheduled Publications
    if hasattr(window, "review_page"):
      window.review_page.edit_task_requested.connect(self._on_edit_review_task)
      window.review_page.delete_task_requested.connect(self._on_delete_review_task)
      window.review_page.back_requested.connect(lambda: self._go_to_wizard_step(2))
      window.review_page.confirm_requested.connect(self._on_confirm_schedules_clicked)

    # Page 5: Execute Publications
    window.start_btn.clicked.connect(self._on_start_upload)
    window.stop_btn.clicked.connect(self._on_stop_clicked)
    window.pause_btn.clicked.connect(self._on_pause_resume)
    if hasattr(window, "resume_btn"):
      window.resume_btn.clicked.connect(self._on_resume_clicked)
    window.export_btn.clicked.connect(self._on_export_report)
    if hasattr(window.executor_page, "back_requested"):
      window.executor_page.back_requested.connect(lambda: self._go_to_wizard_step(1))

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
