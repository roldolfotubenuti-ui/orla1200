from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QFileDialog

from core.scheduler import UploadTask
from gui.pages.review_wizard_page import EditScheduledTaskDialog
from utils.datetime_utils import DateTimeUtils
from utils.file_scanner import VideoFile
from utils.video_media import VideoMediaUtils


class WizardControllerMixin:
  """Handle 5-step Wizard navigation, drag-and-drop videos, smart slot distribution, review editing, and state persistence."""

  WIZARD_STATE_FILE = "wizard-state.json"

  def _init_wizard_state(self) -> None:
    """Initialize in-memory wizard structures and restore persisted state if available."""
    self._per_video_meta: dict[str, dict[str, str]] = {}
    self._studio_schedules: dict[str, datetime | None] = {}
    self._studio_visibilities: dict[str, str] = {}
    self._video_probe_cache: dict[str, dict[str, Any]] = {}
    self._thumb_cache_dir = self._storage_dir / ".thumbs"
    self._restoring_wizard = False
    self._restore_wizard_state()

  # ------------------------------------------------------------------
  # Step Navigation & Validation (TKS Engine 2.0 Studio Workflow)
  # ------------------------------------------------------------------

  def _on_stepper_clicked(self, target_step: int) -> None:
    """Allow navigating between wizard pages while validating required prerequisites."""
    current = self._window.current_wizard_step()
    if target_step == current:
      return
    if target_step > current:
      if target_step >= 1 and not self._window.account_dropdown.currentText():
        self._logger.warning("Selecione uma conta TikTok antes de avançar.")
        return
      if target_step >= 2 and not self._get_valid_loaded_videos():
        self._logger.warning("Carregue pelo menos um vídeo compatível antes de publicar.")
        return
      if target_step >= 2 and not self._tasks:
        self._on_studio_publish_clicked()
        if not self._tasks:
          return
    self._go_to_wizard_step(target_step)

  def _go_to_wizard_step(self, step_index: int) -> None:
    """Switch to the requested wizard step and refresh its view data."""
    if step_index == 1:
      self._refresh_studio_page()
      self._refresh_wizard_videos_page()
    elif step_index == 2:
      self._refresh_wizard_execution_page()
    elif step_index == 3:
      self._refresh_wizard_review_page()
    elif step_index == 4:
      self._refresh_wizard_execution_page()

    self._window.set_wizard_step(step_index)
    self._save_wizard_state()

  # ------------------------------------------------------------------
  # TikTok Studio Page Handlers (Images 1, 2, 3, 4)
  # ------------------------------------------------------------------

  def _refresh_studio_page(self) -> None:
    """Populate TikTokStudioPage with loaded videos, thumbnails, captions, schedules, and visibilities."""
    if not hasattr(self._window, "studio_page"):
      return

    items: list[dict[str, Any]] = []
    for v in self._videos:
      fn = v.path.name
      probe = self._video_probe_cache.get(fn, {})
      dur_str = str(probe.get("duration_human", "00:00"))
      dur_sec = int(probe.get("duration_seconds", 0))
      size_human = str(probe.get("size_human", ""))
      is_valid = bool(probe.get("is_valid", True))

      meta = self._per_video_meta.get(fn, {})
      cap = meta.get("caption") if "caption" in meta else fn
      sched = self._studio_schedules.get(fn)
      vis = self._studio_visibilities.get(fn, "Público")

      items.append({
        "filename": fn,
        "path": v.path,
        "duration_str": dur_str,
        "duration_sec": dur_sec,
        "size_human": size_human,
        "caption": cap,
        "schedule_dt": sched,
        "visibility": vis,
        "is_valid": is_valid,
      })

    self._window.studio_page.populate_videos(items, thumb_cache_dir=self._thumb_cache_dir)
    username = self._window.account_dropdown.currentText().strip()
    if hasattr(self._window.studio_page, "header"):
      self._window.studio_page.header.set_account(
        username,
        "Sessão salva" if username else "",
        ok=bool(username),
      )

  def _on_studio_reorder(self, from_idx: int, to_idx: int) -> None:
    """Handle drag-and-drop reordering of studio videos."""
    if not (0 <= from_idx < len(self._videos) and 0 <= to_idx < len(self._videos)):
      return
    item = self._videos.pop(from_idx)
    self._videos.insert(to_idx, item)
    self._refresh_studio_page()
    self._save_wizard_state()

  def _on_studio_caption_updated(self, filename: str, new_caption: str) -> None:
    """Update caption from Image 4 inline editor."""
    if filename not in self._per_video_meta:
      self._per_video_meta[filename] = {}
    self._per_video_meta[filename]["caption"] = new_caption
    for t in self._tasks:
      if t.file_path.name == filename:
        t.caption = new_caption
    self._save_wizard_state()

  def _on_studio_schedule_updated(self, filename: str, dt: datetime | None) -> None:
    """Update schedule date/time from Image 3 pop-up dialog."""
    try:
      self._studio_schedules[filename] = dt
      for t in self._tasks:
        if t.file_path.name == filename:
          t.schedule_time = dt
      self._save_wizard_state()
    except Exception as exc:
      self._logger.error(f"Erro ao salvar data de agendamento: {exc}")

  def _on_studio_visibility_updated(self, filename: str, visibility: str) -> None:
    """Update publication visibility (Público, Amigos, Privado)."""
    try:
      self._studio_visibilities[filename] = visibility
      for t in self._tasks:
        if t.file_path.name == filename:
          t.visibility = "public" if visibility == "Público" else ("friends" if visibility == "Amigos" else "private")
      self._save_wizard_state()
    except Exception as exc:
      self._logger.error(f"Erro ao salvar visibilidade: {exc}")

  def _on_studio_substitute_file(self, filename: str) -> None:
    """Substitute an individual video file preserving caption, schedule, and visibility."""
    files, _ = QFileDialog.getOpenFileNames(
      self._window,
      f"Substituir arquivo para {filename}",
      "",
      "Video Files (*.mp4 *.mov *.webm *.mkv);;All Files (*)",
    )
    if not files:
      return

    new_p = Path(files[0])
    if not new_p.exists():
      return

    replaced = False
    for idx, v in enumerate(self._videos):
      if v.path.name == filename:
        prev_meta = self._per_video_meta.pop(filename, {})
        self._per_video_meta[new_p.name] = prev_meta
        prev_sched = self._studio_schedules.pop(filename, None)
        self._studio_schedules[new_p.name] = prev_sched
        prev_vis = self._studio_visibilities.pop(filename, "Público")
        self._studio_visibilities[new_p.name] = prev_vis

        info = VideoMediaUtils.probe_video(new_p)
        self._video_probe_cache[new_p.name] = {
          "path": str(new_p),
          "filename": info.filename,
          "size_bytes": info.size_bytes,
          "size_human": info.size_human,
          "duration_seconds": info.duration_seconds,
          "duration_human": info.duration_human,
          "is_valid": info.is_valid,
          "validation_message": info.validation_message,
        }
        self._videos[idx] = VideoFile(
          path=new_p,
          filename=info.filename,
          size_bytes=info.size_bytes,
          size_human=info.size_human,
        )
        replaced = True
        break

    if replaced:
      self._logger.info(f"Arquivo {filename} substituído por {new_p.name}.")
      self._sync_loaded_videos_with_account()
      self._refresh_studio_page()
      self._save_wizard_state()

  def _on_studio_batch_schedule(
    self, per_day: int, start_time: str, end_time: str, interval_min: int
  ) -> None:
    """Distribute all loaded videos across schedule slots automatically."""
    if not self._videos:
      return

    start_h, start_m = map(int, start_time.split(":"))
    end_h, end_m = map(int, end_time.split(":"))

    now = datetime.now()
    cur_date = now.date()
    if now.hour >= end_h:
      cur_date += timedelta(days=1)

    cur_time = datetime(cur_date.year, cur_date.month, cur_date.day, start_h, start_m)
    min_allowed = self._rules.min_allowed_datetime(now)
    max_allowed = self._rules.max_allowed_datetime(now)
    if cur_time < min_allowed:
      cur_time = min_allowed

    day_count = 0
    for v in self._videos:
      fn = v.path.name
      if cur_time > max_allowed:
        self._logger.warning(
          f"Limite de {self._rules.max_offset_days} dias do TikTok atingido; limitando agendamento."
        )
        cur_time = max_allowed
      self._studio_schedules[fn] = cur_time
      day_count += 1

      if day_count >= per_day or cur_time.hour >= end_h:
        cur_date += timedelta(days=1)
        cur_time = datetime(cur_date.year, cur_date.month, cur_date.day, start_h, start_m)
        if cur_time < min_allowed:
          cur_time = min_allowed
        day_count = 0
      else:
        cur_time += timedelta(minutes=interval_min)

    self._logger.success(f"Distribuídos {len(self._videos)} vídeos na grade de horários.")
    self._refresh_studio_page()
    self._save_wizard_state()

  def _on_studio_publish_clicked(self) -> None:
    """Advance to Execution Step: build UploadTasks from studio items and update schedule."""
    valid_videos = self._get_valid_loaded_videos()
    if not valid_videos:
      self._logger.warning("Nenhum vídeo válido para publicar.")
      return

    username = self._window.account_dropdown.currentText()
    if not username:
      self._logger.error("Selecione uma conta antes de publicar.")
      return

    new_tasks: list[UploadTask] = []
    for v in valid_videos:
      fn = v.path.name
      meta = self._per_video_meta.get(fn, {})
      cap = meta.get("caption") if "caption" in meta else fn
      sched = self._studio_schedules.get(fn)
      vis_raw = self._studio_visibilities.get(fn, "Público")
      vis = "public" if vis_raw == "Público" else ("friends" if vis_raw == "Amigos" else "private")

      new_tasks.append(
        UploadTask(
          file_path=v.path,
          caption=cap,
          schedule_time=sched,
          visibility=vis,
        )
      )

    self._tasks = new_tasks
    self._update_table_schedule()
    self._window.start_btn.setEnabled(True)

    planned_records = [
      {
        "file": t.file_path.name,
        "file_path": str(t.file_path),
        "caption": t.caption,
        "schedule_time": DateTimeUtils.format_iso(t.schedule_time) if t.schedule_time else None,
        "visibility": t.visibility,
        "status": "pending",
      }
      for t in self._tasks
    ]
    self._storage_service.confirm_planned_schedules(username, planned_records)
    self._logger.success(f"{len(self._tasks)} publicação(ões) confirmada(s) para @{username}.")
    self._refresh_studio_publications()
    if hasattr(self._window, "studio_page"):
      self._window.studio_page.show_publications()
    # Executa diretamente sem exigir clique manual em botões extras nem mudar para tela escura
    self._on_start_upload()

  def _refresh_studio_publications(self) -> None:
    """Load and synchronize all scheduled and historical publications for the Studio tab."""
    if not hasattr(self._window, "studio_page"):
      return
    username = self._window.account_dropdown.currentText()
    if not username:
      self._window.studio_page.populate_publications([])
      return

    scheduled_data = self._storage_service.load_scheduled(username)
    existing_uploads = self._storage_service.get_user_uploads(scheduled_data)

    items_by_file: dict[str, dict[str, Any]] = {}
    for up in existing_uploads:
      fname = Path(str(up.get("file", ""))).name
      if not fname:
        continue
      items_by_file[fname] = dict(up)

    # Active tasks in queue take precedence for live status, but never overwrite terminal execution states
    for t in self._tasks:
      fn = t.file_path.name
      existing_entry = items_by_file.get(fn)
      existing_st = str(existing_entry.get("status", "")).lower() if existing_entry else ""

      # If already recorded with a terminal execution status, preserve that status!
      if existing_st in ("failed", "scheduled", "published", "unknown"):
        continue

      st = "pending"
      if hasattr(self, "_current_processing_filename") and self._current_processing_filename == fn:
        st = "uploading"
      items_by_file[fn] = {
        "file": fn,
        "file_path": str(t.file_path),
        "caption": t.caption,
        "schedule_time": DateTimeUtils.format_iso(t.schedule_time) if t.schedule_time else None,
        "visibility": t.visibility,
        "status": st,
      }

    all_pub_items = list(items_by_file.values())
    self._window.studio_page.populate_publications(all_pub_items)

  # ------------------------------------------------------------------
  # Step 2: Load, Validate, Reorder, and Remove Videos
  # ------------------------------------------------------------------

  def _on_select_videos_dialog(self) -> None:
    """Open file dialog to pick one or multiple video files."""
    files, _ = QFileDialog.getOpenFileNames(
      self._window,
      "Selecionar Vídeos",
      "",
      "Video Files (*.mp4 *.mov *.webm *.mkv);;All Files (*)",
    )
    if files:
      self._add_video_paths(files)

  def _on_files_dropped(self, raw_paths: list[str]) -> None:
    """Handle files or folders dropped onto the Step 2 drop zone."""
    expanded: list[str] = []
    for raw in raw_paths:
      p = Path(raw)
      if p.is_dir():
        for child in sorted(p.rglob("*")):
          if child.is_file() and child.suffix.lower() in VideoMediaUtils.SUPPORTED_EXTENSIONS:
            expanded.append(str(child))
      elif p.is_file():
        expanded.append(str(p))
    if expanded:
      self._add_video_paths(expanded)

  def _add_video_paths(self, paths: list[str]) -> None:
    """Probe and append video files to self._videos without duplicating paths."""
    existing_paths = {str(v.path.resolve()) for v in self._videos if v.path.exists()}
    added = 0
    for raw in paths:
      p = Path(raw)
      resolved_str = str(p.resolve()) if p.exists() else str(p)
      if resolved_str in existing_paths:
        continue
      info = VideoMediaUtils.probe_video(p)
      self._video_probe_cache[p.name] = {
        "path": str(p),
        "filename": info.filename,
        "size_bytes": info.size_bytes,
        "size_human": info.size_human,
        "duration_seconds": info.duration_seconds,
        "duration_human": info.duration_human,
        "is_valid": info.is_valid,
        "validation_message": info.validation_message,
      }
      self._videos.append(
        VideoFile(
          path=p,
          filename=info.filename,
          size_bytes=info.size_bytes,
          size_human=info.size_human,
        )
      )
      existing_paths.add(resolved_str)
      added += 1
      if not info.is_valid:
        self._logger.warning(f"Vídeo incompatível: {info.filename} — {info.validation_message}")

    if added > 0:
      self._logger.info(f"Carregados {added} arquivo(s) na lista de vídeos.")
      self._sync_loaded_videos_with_account()
      self._refresh_studio_page()
      self._refresh_wizard_videos_page()
      self._save_wizard_state()

  def _sync_loaded_videos_with_account(self) -> None:
    """Refresh account history sets and update table and limit spinbox for current self._videos."""
    self._scheduled_basenames = set()
    self._failed_basenames = set()
    self._unknown_basenames = set()
    self._published_video_ids = set()
    self._published_entries = {}

    username = self._window.account_dropdown.currentText()
    existing: list[dict] = []
    if username:
      scheduled_data = self._storage_service.load_scheduled(username)
      existing = self._storage_service.get_user_uploads(scheduled_data)

      latest_status_by_file: dict[str, str] = {}
      for upload in existing:
        fname = Path(str(upload.get("file", ""))).name
        st = str(upload.get("status", ""))
        if fname and st:
          latest_status_by_file[fname] = st

      self._scheduled_basenames = {
        fname
        for fname, st in latest_status_by_file.items()
        if st in ("scheduled", "success", "unknown")
      }
      self._unknown_basenames = {
        fname
        for fname, st in latest_status_by_file.items()
        if st == "unknown"
      }
      self._failed_basenames = {
        fname
        for fname, st in latest_status_by_file.items()
        if st == "failed"
      }

      published_data = self._storage_service.load_published(username)
      for entry in published_data.get("published", []):
        if "|" in entry:
          video_id, date_str = entry.split("|", 1)
        else:
          video_id, date_str = entry, ""
        if video_id:
          self._published_video_ids.add(video_id)
          self._published_entries[video_id] = date_str

    valid_available = [
      v
      for v in self._get_valid_loaded_videos()
      if not self._is_video_unavailable(v.filename)
    ]
    limit_max = max(1, len(valid_available))
    self._window.limit_spin.setMaximum(limit_max)
    self._window.limit_spin.setValue(limit_max)
    self._populate_video_table(existing, username)

  def _get_valid_loaded_videos(self) -> list[VideoFile]:
    """Return only loaded videos that passed format and size validation."""
    valid: list[VideoFile] = []
    for v in self._videos:
      cached = self._video_probe_cache.get(v.filename)
      if cached is None:
        info = VideoMediaUtils.probe_video(v.path)
        cached = {
          "path": str(v.path),
          "filename": info.filename,
          "size_bytes": info.size_bytes,
          "size_human": info.size_human,
          "duration_seconds": info.duration_seconds,
          "duration_human": info.duration_human,
          "is_valid": info.is_valid,
          "validation_message": info.validation_message,
        }
        self._video_probe_cache[v.filename] = cached
      if cached.get("is_valid", True):
        valid.append(v)
    return valid

  def _refresh_wizard_videos_page(self) -> None:
    """Update the Step 2 loaded videos table."""
    if not hasattr(self._window, "videos_page"):
      return
    items: list[dict[str, Any]] = []
    for v in self._videos:
      cached = self._video_probe_cache.get(v.filename)
      if cached is None:
        info = VideoMediaUtils.probe_video(v.path)
        cached = {
          "path": str(v.path),
          "filename": info.filename,
          "size_bytes": info.size_bytes,
          "size_human": info.size_human,
          "duration_seconds": info.duration_seconds,
          "duration_human": info.duration_human,
          "is_valid": info.is_valid,
          "validation_message": info.validation_message,
        }
        self._video_probe_cache[v.filename] = cached

      val_msg = cached["validation_message"]
      if cached["is_valid"] and self._is_video_unavailable(v.filename):
        val_msg = "Já agendado/publicado nesta conta"

      items.append({
        "path": str(v.path),
        "filename": v.filename,
        "size_human": v.size_human,
        "duration_human": cached.get("duration_human", "00:05"),
        "is_valid": cached.get("is_valid", True),
        "validation_message": val_msg,
      })

    self._window.videos_page.populate_loaded_videos(items, self._thumb_cache_dir)

  def _on_move_video_up(self, index: int) -> None:
    if 0 < index < len(self._videos):
      self._videos[index - 1], self._videos[index] = self._videos[index], self._videos[index - 1]
      self._sync_loaded_videos_with_account()
      self._refresh_wizard_videos_page()
      self._save_wizard_state()

  def _on_move_video_down(self, index: int) -> None:
    if 0 <= index < len(self._videos) - 1:
      self._videos[index + 1], self._videos[index] = self._videos[index], self._videos[index + 1]
      self._sync_loaded_videos_with_account()
      self._refresh_wizard_videos_page()
      self._save_wizard_state()

  def _on_remove_loaded_video(self, target: int | str) -> None:
    if isinstance(target, str):
      idx_found = next((i for i, v in enumerate(self._videos) if v.path.name == target), -1)
    else:
      idx_found = target

    if 0 <= idx_found < len(self._videos):
      removed = self._videos.pop(idx_found)
      self._tasks = [t for t in self._tasks if t.file_path.name != removed.filename]
      self._per_video_meta.pop(removed.filename, None)
      self._studio_schedules.pop(removed.filename, None)
      self._studio_visibilities.pop(removed.filename, None)
      self._sync_loaded_videos_with_account()
      self._refresh_studio_page()
      self._refresh_wizard_videos_page()
      self._save_wizard_state()

  def _on_clear_loaded_videos(self) -> None:
    self._videos.clear()
    self._tasks.clear()
    self._studio_schedules.clear()
    self._studio_visibilities.clear()
    self._sync_loaded_videos_with_account()
    self._refresh_studio_page()
    self._refresh_wizard_videos_page()
    self._save_wizard_state()

  def _on_step2_continue(self) -> None:
    valid_vids = self._get_valid_loaded_videos()
    if not valid_vids:
      self._logger.warning("Adicione pelo menos um vídeo compatível (.mp4) para continuar.")
      return
    self._go_to_wizard_step(2)

  # ------------------------------------------------------------------
  # Step 3: Configuration & Smart Automatic Distribution
  # ------------------------------------------------------------------

  def _refresh_wizard_config_page(self) -> None:
    if not hasattr(self._window, "config_page"):
      return
    eligible_videos = [
      {"filename": v.filename, "path": str(v.path)}
      for v in self._get_valid_loaded_videos()
      if not self._is_video_unavailable(v.filename)
    ]
    self._window.config_page.populate_video_caption_cards(
      eligible_videos,
      self._per_video_meta,
      self._thumb_cache_dir,
    )

  def _on_per_video_caption_changed(self, filename: str, caption: str, hashtags: str) -> None:
    self._per_video_meta[filename] = {
      "caption": caption,
      "hashtags": hashtags,
    }
    if hasattr(self._window, "config_page"):
      card = self._window.config_page._caption_cards.get(filename)
      if card is not None and (
        card.caption_edit.text().strip() != caption
        or card.hashtags_edit.text().strip() != hashtags
      ):
        card.set_custom_caption(caption, hashtags)
    self._save_wizard_state()

  def _generate_wizard_Configured_slots(self) -> list[datetime]:
    """Generate ordered schedule datetimes matching Step 3 weekdays, specific dates, and daily time list."""
    cfg_page = self._window.config_page
    time_tuples = cfg_page.get_time_slots()
    if not time_tuples:
      return []

    start_qd = cfg_page.start_date.date()
    end_qd = cfg_page.end_date.date()
    start_day = datetime(start_qd.year(), start_qd.month(), start_qd.day())
    end_day = datetime(end_qd.year(), end_qd.month(), end_qd.day(), 23, 59)

    allowed_weekdays = cfg_page.get_allowed_weekdays()
    specific_dates = cfg_page.get_specific_dates()
    now = datetime.now()

    candidate_slots: list[datetime] = []
    cur_day = start_day
    while cur_day.date() <= end_day.date():
      day_iso = cur_day.strftime("%Y-%m-%d")
      day_allowed = (
        (day_iso in specific_dates)
        if specific_dates
        else (cur_day.weekday() in allowed_weekdays)
      )
      if day_allowed:
        for h, m in time_tuples:
          slot_dt = cur_day.replace(hour=h, minute=m, second=0, microsecond=0)
          rounded = DateTimeUtils.round_to_step(slot_dt, self._rules.minute_step)
          valid, _ = self._rules.validate(rounded, now)
          if valid:
            candidate_slots.append(rounded)
      cur_day += timedelta(days=1)

    candidate_slots.sort()
    return candidate_slots

  def _on_wizard_distribute(self) -> None:
    """Distribute loaded videos across the configured days and daily times in user-defined order."""
    self._window.schedule_result_label.clear()
    self._window.schedule_result_label.hide()

    eligible_videos = [
      v
      for v in self._get_valid_loaded_videos()
      if not self._is_video_unavailable(v.filename)
    ]
    if not eligible_videos:
      self._logger.warning("Nenhum vídeo pendente disponível para distribuir.")
      return

    slots = self._generate_wizard_Configured_slots()
    if not slots:
      # Fallback to interval-based generator if no discrete slot matched
      self._on_generate_schedule()
      return

    # Filter out conflicting slots already scheduled for the active account
    username = self._window.account_dropdown.currentText()
    conflicts_removed = 0
    if username:
      scheduled_data = self._storage_service.load_scheduled(username)
      existing_uploads = [
        u
        for u in self._storage_service.get_user_uploads(scheduled_data)
        if u.get("status") in ("success", "unknown")
      ]
      if existing_uploads:
        conflicting = set(self._scheduler.detect_conflicts(slots, existing_uploads))
        if conflicting:
          conflicts_removed = len(conflicting)
          slots = [s for s in slots if s not in conflicting]

    limit = max(1, min(len(eligible_videos), self._window.limit_spin.value()))
    requested_videos = eligible_videos[:limit]
    available_slots = slots[:len(requested_videos)]

    default_caption_body = self._window.caption_input.toPlainText().strip()
    self._register_tags(default_caption_body)
    use_prefix = (
      hasattr(self._window, "prefix_caption_check")
      and self._window.prefix_caption_check.isChecked()
    )

    captions: list[str] = []
    for v in requested_videos:
      custom_or_default = self._window.config_page.get_video_full_caption(
        v.filename,
        fallback_caption=default_caption_body,
      )
      self._register_tags(custom_or_default)
      captions.append(
        self._build_caption(v.path, custom_or_default, include_prefix=use_prefix)
      )

    video_paths = [v.path for v in requested_videos]
    self._tasks = self._scheduler.assign_videos(video_paths, available_slots, captions)
    self._update_table_schedule()
    self._window.start_btn.setEnabled(len(self._tasks) > 0)

    preview_lines = [
      f"#{idx + 1:02d}  •  {t.schedule_time.strftime('%d/%m/%Y %H:%M') if t.schedule_time else '-'}  →  {t.file_path.name}  ({t.caption[:48] or 'Sem legenda'})"
      for idx, t in enumerate(self._tasks)
    ]
    self._window.config_page.populate_distribution_preview(preview_lines)

    summary_msg = f"Distribuídos {len(self._tasks)} vídeo(s) com sucesso."
    if conflicts_removed > 0:
      summary_msg += f" ({conflicts_removed} horário(s) conflitante(s) ignorado(s))."
    if len(self._tasks) < len(requested_videos):
      skipped = len(requested_videos) - len(self._tasks)
      summary_msg += f" Atenção: {skipped} vídeo(s) sem horário disponível na janela selecionada."

    self._window.schedule_result_label.setText(summary_msg)
    self._window.schedule_result_label.show()
    self._save_wizard_state()

  def _on_step3_continue(self) -> None:
    if not self._tasks:
      self._on_wizard_distribute()
    if not self._tasks:
      self._logger.warning("Distribua os vídeos em horários válidos antes de avançar para a revisão.")
      return
    self._go_to_wizard_step(3)

  # ------------------------------------------------------------------
  # Step 4: Review, Individual Edit / Delete, and Permanent Confirmation
  # ------------------------------------------------------------------

  def _refresh_wizard_review_page(self) -> None:
    if not hasattr(self._window, "review_page"):
      return
    username = self._window.account_dropdown.currentText()
    tasks_info = [
      {
        "file_path": str(t.file_path),
        "caption": t.caption,
        "schedule_time": t.schedule_time,
        "status": "Pending",
      }
      for t in self._tasks
    ]
    self._window.review_page.populate_review(
      username=username,
      total_videos_loaded=len(self._videos),
      tasks_info=tasks_info,
      thumb_cache_dir=self._thumb_cache_dir,
    )

  def _on_edit_review_task(self, task_index: int) -> None:
    if not (0 <= task_index < len(self._tasks)):
      return
    task = self._tasks[task_index]
    dt = task.schedule_time or self._rules.min_allowed_datetime()
    dlg = EditScheduledTaskDialog(
      filename=task.file_path.name,
      caption=task.caption,
      schedule_dt=dt,
      parent=self._window,
    )
    if dlg.exec():
      new_caption, new_dt = dlg.get_updated_values()
      valid, reason = self._rules.validate(new_dt)
      if not valid:
        self._logger.warning(f"Horário inválido ao editar {task.file_path.name}: {reason}")
        return
      task.caption = new_caption
      task.schedule_time = new_dt
      self._per_video_meta[task.file_path.name] = {
        "caption": new_caption,
        "hashtags": "",
      }
      self._update_table_schedule()
      self._refresh_wizard_review_page()
      self._save_wizard_state()
      self._logger.info(
        f"Agendamento atualizado: {task.file_path.name} -> {DateTimeUtils.format_for_display(new_dt)}"
      )

  def _on_delete_review_task(self, task_index: int) -> None:
    if 0 <= task_index < len(self._tasks):
      removed = self._tasks.pop(task_index)
      self._logger.info(f"Agendamento removido da revisão: {removed.file_path.name}")
      self._update_table_schedule()
      self._window.start_btn.setEnabled(len(self._tasks) > 0)
      self._refresh_wizard_review_page()
      self._save_wizard_state()

  def _on_confirm_schedules_clicked(self) -> None:
    """Persist all reviewed schedules permanently to storage and advance to Step 5 (Execution)."""
    if not self._tasks:
      self._logger.warning("Nenhum agendamento na fila para confirmar.")
      return
    username = self._window.account_dropdown.currentText()
    if not username:
      self._logger.error("Selecione uma conta antes de confirmar os agendamentos.")
      return

    planned_records = [
      {
        "file": t.file_path.name,
        "file_path": str(t.file_path),
        "caption": t.caption,
        "schedule_time": DateTimeUtils.format_iso(t.schedule_time) if t.schedule_time else None,
        "status": "pending",
      }
      for t in self._tasks
    ]
    self._storage_service.confirm_planned_schedules(username, planned_records)
    self._logger.success(
      f"Confirmados e salvos {len(planned_records)} agendamento(s) para @{username}. "
      "Pronto para execução (clique em EXECUTE para iniciar)."
    )
    self._window.start_btn.setEnabled(True)
    self._go_to_wizard_step(4)

  # ------------------------------------------------------------------
  # Step 5: Execution Dashboard Metrics
  # ------------------------------------------------------------------

  def _refresh_wizard_execution_page(self) -> None:
    if not hasattr(self._window, "executor_page"):
      return
    username = self._window.account_dropdown.currentText()
    self._window.executor_page.metric_account.set_value(f"@{username}" if username else "-")
    self._update_execution_metrics()
    self._update_table_schedule()
    self._window.start_btn.setEnabled(len(self._tasks) > 0)

  def _update_execution_metrics(self) -> None:
    if not hasattr(self._window, "executor_page") or not hasattr(self._window.executor_page, "metric_total"):
      return
    table = self._window.video_table
    counts = {
      "Pending": 0,
      "Processing": 0,
      "Paused": 0,
      "Scheduled": 0,
      "Published": 0,
      "Failed": 0,
    }
    for row in range(table.rowCount()):
      item = table.item(row, 5)
      st = item.text() if item else "Pending"
      if st in ("Pending", "Processing", "Paused"):
        counts["Pending"] += 1
      elif st in ("Scheduled", "Elapsed (Unverified)"):
        counts["Scheduled"] += 1
      elif st == "Published":
        counts["Published"] += 1
      elif st in ("Failed", "Unknown"):
        counts["Failed"] += 1

    ep = self._window.executor_page
    ep.metric_total.set_value(str(table.rowCount()))
    ep.metric_pending.set_value(str(counts["Pending"]))
    ep.metric_scheduled.set_value(str(counts["Scheduled"]))
    ep.metric_published.set_value(str(counts["Published"]))
    ep.metric_failed.set_value(str(counts["Failed"]))

  # ------------------------------------------------------------------
  # Full State Persistence Across App Restarts
  # ------------------------------------------------------------------

  def _save_wizard_state(self) -> None:
    """Persist current wizard state to storage/wizard-state.json."""
    if getattr(self, "_restoring_wizard", False):
      return
    if not hasattr(self._window, "config_page"):
      return

    cfg = self._window.config_page
    start_qd = cfg.start_date.date()
    end_qd = cfg.end_date.date()

    state = {
      "current_step": self._window.current_wizard_step(),
      "selected_account": self._window.account_dropdown.currentText(),
      "selected_folder": self._window.folder_dropdown.currentText(),
      "loaded_videos": [str(v.path) for v in self._videos],
      "default_caption": self._window.caption_input.toPlainText(),
      "prefix_enabled": self._window.prefix_caption_check.isChecked(),
      "per_video_meta": self._per_video_meta,
      "studio_schedules": {
        k: DateTimeUtils.format_iso(v) if v else None
        for k, v in self._studio_schedules.items()
      },
      "studio_visibilities": self._studio_visibilities,
      "start_date": f"{start_qd.year():04d}-{start_qd.month():02d}-{start_qd.day():02d}",
      "end_date": f"{end_qd.year():04d}-{end_qd.month():02d}-{end_qd.day():02d}",
      "allowed_weekdays": sorted(cfg.get_allowed_weekdays()),
      "specific_dates": sorted(cfg.get_specific_dates()),
      "time_slots": [f"{h:02d}:{m:02d}" for h, m in cfg.get_time_slots()],
      "headless": self._window.headless_check.isChecked(),
      "retry_failures": self._window.retry_check.isChecked(),
      "planned_tasks": [
        {
          "file_path": str(t.file_path),
          "caption": t.caption,
          "schedule_time": DateTimeUtils.format_iso(t.schedule_time) if t.schedule_time else None,
          "visibility": t.visibility,
        }
        for t in self._tasks
      ],
    }
    self._storage_service.save_wizard_state(state, self.WIZARD_STATE_FILE)

  def _restore_wizard_state(self) -> None:
    """Restore saved wizard session state on startup without losing queues or duplicating posts."""
    state = self._storage_service.load_wizard_state(self.WIZARD_STATE_FILE)
    if not state:
      return

    self._restoring_wizard = True
    try:
      saved_account = str(state.get("selected_account", ""))
      if saved_account:
        idx = self._window.account_dropdown.findText(saved_account)
        if idx >= 0:
          self._window.account_dropdown.setCurrentIndex(idx)

      saved_folder = str(state.get("selected_folder", ""))
      if saved_folder:
        f_idx = self._window.folder_dropdown.findText(saved_folder)
        if f_idx >= 0:
          self._window.folder_dropdown.setCurrentIndex(f_idx)

      per_meta = state.get("per_video_meta")
      if isinstance(per_meta, dict):
        self._per_video_meta = {
          str(k): {
            "caption": str(v.get("caption", "")),
            "hashtags": str(v.get("hashtags", "")),
          }
          for k, v in per_meta.items()
          if isinstance(v, dict)
        }

      default_cap = state.get("default_caption")
      if isinstance(default_cap, str):
        self._window.caption_input.setPlainText(default_cap)

      if "prefix_enabled" in state:
        self._window.prefix_caption_check.setChecked(bool(state["prefix_enabled"]))
      if "headless" in state:
        self._window.headless_check.setChecked(bool(state["headless"]))
      if "retry_failures" in state:
        self._window.retry_check.setChecked(bool(state["retry_failures"]))

      cfg = self._window.config_page
      if isinstance(state.get("time_slots"), list) and state["time_slots"]:
        cfg.set_time_slots([str(s) for s in state["time_slots"]])
      if isinstance(state.get("allowed_weekdays"), list):
        cfg.set_allowed_weekdays([int(d) for d in state["allowed_weekdays"]])
      if isinstance(state.get("specific_dates"), list):
        cfg.set_specific_dates([str(d) for d in state["specific_dates"]])

      for key, widget in (("start_date", cfg.start_date), ("end_date", cfg.end_date)):
        raw_d = str(state.get(key, ""))
        if raw_d:
          try:
            dt = datetime.fromisoformat(raw_d)
            if dt.date() >= datetime.now().date():
              widget.setDate(QDate(dt.year, dt.month, dt.day))
          except ValueError:
            pass

      loaded_paths = state.get("loaded_videos", [])
      if isinstance(loaded_paths, list) and loaded_paths:
        existing_files = [p for p in loaded_paths if Path(str(p)).exists()]
        if existing_files:
          self._add_video_paths(existing_files)

      # Restore unexecuted planned tasks
      restored_tasks: list[UploadTask] = []
      raw_tasks = state.get("planned_tasks", [])
      if isinstance(raw_tasks, list):
        for item in raw_tasks:
          if not isinstance(item, dict):
            continue
          fp = Path(str(item.get("file_path", "")))
          if not fp.exists():
            continue
          if self._is_video_unavailable(fp.name):
            continue
          sched_iso = item.get("schedule_time")
          sched_dt = None
          if isinstance(sched_iso, str) and sched_iso:
            try:
              sched_dt = datetime.fromisoformat(sched_iso)
            except ValueError:
              sched_dt = None
          restored_tasks.append(
            UploadTask(
              file_path=fp,
              caption=str(item.get("caption", "")),
              schedule_time=sched_dt,
              visibility=str(item.get("visibility", "public")),
            )
          )

      raw_studio_sched = state.get("studio_schedules")
      if isinstance(raw_studio_sched, dict):
        for k, v in raw_studio_sched.items():
          if isinstance(v, str) and v:
            try:
              self._studio_schedules[str(k)] = datetime.fromisoformat(v)
            except ValueError:
              pass
      raw_studio_vis = state.get("studio_visibilities")
      if isinstance(raw_studio_vis, dict):
        self._studio_visibilities = {str(k): str(v) for k, v in raw_studio_vis.items()}

      if restored_tasks:
        self._tasks = restored_tasks
        self._update_table_schedule()
        self._window.start_btn.setEnabled(True)

      saved_step = int(state.get("current_step", 0))
      if saved_step > 2:
        saved_step = 2
      if 0 <= saved_step <= 2:
        self._go_to_wizard_step(saved_step)
    finally:
      self._restoring_wizard = False
