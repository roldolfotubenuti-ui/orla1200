from __future__ import annotations

import asyncio
import re
import random
from pathlib import Path

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeout

from core.logger_manager import LoggerManager
from utils.datetime_utils import DateTimeUtils


class SelectorError(Exception):
  """
  Raised when a required DOM element cannot be found or interacted with.
  """


class PostError(Exception):
  """
  Raised when TikTok displays a non-rate-limit error Toast during post submission.
  """


class RateLimitError(Exception):
  """
  Raised when TikTok displays a Toast indicating the account has
  reached its upload/scheduling rate limit.

  The ``message`` attribute contains the Toast text content.
  """


class _Selectors:
  """
  Centralized DOM selectors for the TikTok Studio upload page.

  All values are derived from the DOM.js reference file.
  """

  FILE_INPUT = "input[type='file']"
  UPLOAD_STATUS = 'span[class*="TUXText"]'
  CAPTION_EDITOR = "div[contenteditable='true']"
  SCHEDULE_TOGGLE_TAG = "span"
  SCHEDULE_TOGGLE_TEXT = "Schedule"
  TIME_INPUT = "input[class*='TUXTextInputCore-input']"
  TIMEPICKER_LIST = 'div[class="tiktok-timepicker-option-list"]'
  CALENDAR_WRAPPER = ".calendar-wrapper"
  MONTH_TITLE = ".month-title"
  CALENDAR_ARROW = ".arrow"
  DAY_SPAN = 'span[class*="day"]'
  VISIBILITY_CONTAINER = 'div[class*="view-auth-container"]'
  VISIBILITY_OPTION = 'div[class*="select-option"]'
  POST_BUTTON = 'button[data-e2e="post_video_button"]'
  POST_NOW_BUTTON = "//button[.//div[text()='Post now']]"
  POST_CONFIRMATION = (
    "//*[contains(., 'Your video has been uploaded') or "
    "contains(., 'Video published') or "
    "contains(., 'Your video has been scheduled') or "
    "contains(., 'Video scheduled') or "
    "contains(., 'Vídeo programado') or "
    "contains(., 'Seu vídeo foi programado') or "
    "contains(., 'Vídeo publicado') or "
    "contains(., 'Gerenciar publicações') or "
    "contains(., 'Manage your posts') or "
    "contains(., 'Carregar outro vídeo') or "
    "contains(., 'Upload another video')]"
  )

  # Popup / overlay selectors (from old working code)
  COOKIE_BANNER = "#tiktok-cookie-banner"
  COOKIE_BANNER_BUTTON = "div.button-wrapper"
  SPLIT_WINDOW = "//button[./div[text()='Not now']]"
  CONTENT_CHECK_MODAL = ".TUXModal.common-modal"
  CONTENT_CHECK_CLOSE = ".common-modal-close, .common-modal-close-icon"
  CONTENT_CHECK_CANCEL = (
    "button.Button__root--type-neutral, button:has-text('Cancel')"
  )
  COPYRIGHT_MODAL = ".TUXModal.common-modal-confirm-modal"
  COPYRIGHT_POST_NOW = "button.TUXButton--primary"
  
  # warning modal
  # WARNING_MODAL = 'div[class*="common-modal-close-icon"]'


class DOMHandler:
  """
  Translates all TikTok Studio DOM interactions into Playwright Python calls.

  Encapsulates every UI operation: file upload, caption entry, schedule
  configuration (time picker, calendar navigation), visibility selection,
  and post submission. All selectors and interaction sequences are derived
  from the DOM.js reference file.

  :param page: Active Playwright page for the TikTok Studio upload form.
  :type page: Page
  :param logger: Logger instance for status and debug messages.
  :type logger: LoggerManager
  :param datetime_utils: DateTimeUtils instance for time calculations.
  :type datetime_utils: DateTimeUtils
  """

  VISIBILITY_MAP: dict[str, list[str]] = {
    "private": ["Only you", "Apenas você", "Privado"],
    "public": ["Everyone", "Todos", "Público"],
    "friends": ["Friends", "Amigos"],
  }

  MONTH_NAMES: dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
  }

  MAX_CALENDAR_NAVIGATION: int = 12
  DEFAULT_TYPING_DELAY: int = 0  # Replaced character-by-character typing with native fill()
  UPLOAD_POLL_INTERVAL: int = 2000
  CONTENT_CHECK_POLL_INTERVAL: int = 3  # seconds
  CONTENT_CHECK_TIMEOUT: int = 900      # 15 minutes max

  def __init__(
    self,
    page: Page,
    logger: LoggerManager,
    datetime_utils: DateTimeUtils,
  ) -> None:
    """
    Initialize DOMHandler.

    :param page: Active Playwright page.
    :type page: Page
    :param logger: Logger instance.
    :type logger: LoggerManager
    :param datetime_utils: DateTimeUtils instance for time calculations.
    :type datetime_utils: DateTimeUtils
    """
    self._page = page
    self._logger = logger
    self._datetime_utils = datetime_utils

  def _log_success(self, msg: str) -> None:
    if hasattr(self._logger, "success"):
      self._logger.success(msg)
    elif hasattr(self._logger, "info"):
      self._logger.info(f"SUCCESS: {msg}")

  async def upload_file(self, file_path: Path) -> None:
    """
    Set a video file on the hidden file input element.

    Locates ``input[type='file']`` and uses Playwright's
    ``set_input_files`` to attach the file without clicking.

    :param file_path: Path to the video file to upload.
    :type file_path: Path
    :raises SelectorError: If the file input element is not found.
    """
    self._logger.info(f"Uploading file: {file_path.name}")

    file_input = await self._wait_for_selector(
      _Selectors.FILE_INPUT,
      timeout=15000,
      state="attached",
    )

    await file_input.set_input_files(str(file_path))

    # Wait for TikTok to start processing the file (matches old code)
    await asyncio.sleep(2)
    self._logger.debug("File attached to input element")

  async def wait_upload_complete(self, timeout: int = 120) -> bool:
    """
    Wait for the file upload to complete by polling for completion signals.

    Detects:
    1. Replacement button ('Substituir' or 'replace').
    2. Active caption editor with schedule radio (input[name='postSchedule']).
    3. Action submit button ('Publicar', 'Agendar', data-e2e='post_video_button').
    4. Text indicators ('Carregado', 'Uploaded', 'Enviado', '100%').
    """
    self._logger.info("Waiting for upload to complete...")
    elapsed = 0
    interval = self.UPLOAD_POLL_INTERVAL / 1000

    while elapsed < timeout:
      try:
        result = await self._page.evaluate("""
          () => {
            // 1. Check for Replace / Substituir button
            const replaceBtn = document.querySelector(
              'button[class*="replace"], div[class*="replace"], [data-e2e*="replace"], button[class*="change-btn"]'
            );
            if (replaceBtn) return true;

            // Check if any button has text 'Substituir' or 'Replace'
            const buttons = Array.from(document.querySelectorAll('button'));
            if (buttons.some(b => {
              const t = b.textContent.trim().toLowerCase();
              return t === 'substituir' || t === 'replace';
            })) return true;

            // 2. Check for scheduling radio / form ready
            const scheduleRadio = document.querySelector('input[name="postSchedule"]');
            if (scheduleRadio) return true;

            // 3. Check for Post / Schedule action button with editor
            const postBtn = document.querySelector('button[data-e2e="post_video_button"]');
            const editor = document.querySelector('div[contenteditable="true"]');
            if (postBtn && editor) return true;

            // 4. Text checks in English and Portuguese (Uploaded, Carregado, Enviado, 100%)
            const spans = Array.from(document.querySelectorAll('span, div, p'));
            const hasUploadText = spans.some(s => {
              const txt = s.textContent.trim().toLowerCase();
              return txt.startsWith("uploaded") ||
                     txt.startsWith("carregado") ||
                     txt.startsWith("enviado") ||
                     txt === "100%" ||
                     txt.includes("upload complete") ||
                     txt.includes("carregamento concluído") ||
                     txt.includes("envio concluído");
            });
            if (hasUploadText) return true;

            return false;
          }
        """)

        if result:
          self._log_success("File upload complete")
          return True

      except Exception as e:
        self._logger.debug(f"Upload status check error: {e}")

      await asyncio.sleep(interval)
      elapsed += interval

    self._logger.error(f"Upload timed out after {timeout}s")
    return False

  async def set_caption(self, text: str) -> None:
    """
    Set the video caption/description text using Playwright's native fill() and keyboard.

    Guarantees literal caption transmission without prepending the uploaded filename
    which TikTok Studio automatically inserts into the editor on video upload.
    Preserves accents, emojis, line breaks, and hashtags instantaneously.

    :param text: Caption text to enter (use ``\\n`` for line breaks).
    :type text: str
    :raises SelectorError: If the caption editor is not found.
    """
    self._logger.info("Setting caption")

    editor = self._page.locator(_Selectors.CAPTION_EDITOR).first
    await editor.wait_for(state="visible", timeout=10000)

    # Click to focus with force=True to bypass any transparent overlays
    await editor.click(force=True)

    # Pre-emptively clear any default filename or text TikTok auto-injected on upload
    await self._page.keyboard.press("Control+A")
    await self._page.keyboard.press("Backspace")
    await asyncio.sleep(0.05)

    clean_text = str(text or "")

    if clean_text:
      # Fill caption literally
      try:
        await editor.fill(clean_text)
      except Exception as e:
        self._logger.debug(f"Direct editor.fill() raised: {e}. Using keyboard insert fallback.")
        await self._page.keyboard.press("Control+A")
        await self._page.keyboard.press("Backspace")
        await self._page.keyboard.insert_text(clean_text)

      # Validation: ensure text was recognized and populated literally
      current_text = (await editor.inner_text()).strip()
      if current_text != clean_text.strip():
        # Fallback to direct keyboard insert to avoid framework concatenation
        self._logger.debug("Editor content mismatched expected literal caption; enforcing keyboard insert")
        await editor.click(force=True)
        await self._page.keyboard.press("Control+A")
        await self._page.keyboard.press("Backspace")
        await self._page.keyboard.insert_text(clean_text)
        current_text = (await editor.inner_text()).strip()

      self._logger.debug(
        f"Caption set and validated successfully ({len(current_text)} characters)"
      )
    else:
      # Explicit empty caption requested: ensure editor is completely clear
      current_text = (await editor.inner_text()).strip()
      if current_text:
        await editor.click(force=True)
        await self._page.keyboard.press("Control+A")
        await self._page.keyboard.press("Backspace")
      self._logger.debug("Caption set as empty (0 characters)")

  async def enable_schedule(self) -> None:
    """
    Click the "Schedule" radio/toggle to enable scheduling mode.
    Supports modern radio (input[name='postSchedule'][value='schedule']),
    toggle switches ([role='switch']), and text labels ("Programar", "Schedule").
    """
    self._logger.info("Enabling schedule mode")
    await self.dismiss_all_popups()

    # 1. Try clicking the modern TikTok Studio Schedule radio label via Playwright locator (dispatches React events)
    clicked = False
    try:
      schedule_label = self._page.locator("label:has(input[name='postSchedule'][value='schedule']), label:has-text('Programar'), label:has-text('Schedule')").first
      if await schedule_label.count() > 0:
        await schedule_label.click(force=True, timeout=5000)
        clicked = True
    except Exception as e:
      self._logger.debug(f"Direct locator label click: {e}")

    # 2. Fallback to DOM evaluation if not checked yet
    is_checked = await self._page.evaluate("""
      () => {
        const radio = document.querySelector('input[name="postSchedule"][value="schedule"]');
        if (radio) {
          if (!radio.checked) {
            const parent = radio.closest('label') || radio.parentElement;
            if (parent) parent.click();
            else radio.click();
          }
          return radio.checked;
        }
        return false;
      }
    """)

    if not is_checked and not clicked:
      try:
        await self._click_by_text(_Selectors.SCHEDULE_TOGGLE_TAG, _Selectors.SCHEDULE_TOGGLE_TEXT)
      except Exception:
        pass

    # Wait for schedule picker container to be present in DOM
    try:
      picker_box = self._page.locator(".scheduled-picker, .scheduled-container, div[class*='scheduled']").first
      await picker_box.wait_for(state="attached", timeout=6000)
    except Exception:
      pass

    await asyncio.sleep(0.5)
    await self.dismiss_allow_schedule()
    await self.dismiss_all_popups()
    self._logger.debug("Schedule mode enabled")

  async def _get_schedule_inputs(self):
    """
    Identifies date and time triggers reliably in modern TikTok Studio or legacy inputs.
    In modern TikTok Studio:
    - div.scheduled-picker .Picker__root:nth-of-type(1) is DATE trigger
    - div.scheduled-picker .Picker__root:nth-of-type(2) is TIME trigger
    In legacy TikTok Studio:
    - Inputs with class TUXTextInputCore-input
    """
    # 1. Check modern Picker triggers
    try:
      date_trig = self._page.locator("div.scheduled-picker div[role='combobox'][aria-label*='date' i], div.scheduled-picker .Picker__root:nth-of-type(1) .Picker__trigger, div.scheduled-picker .Picker__trigger").first
      time_trig = self._page.locator("div.scheduled-picker div[role='combobox'][aria-label*='time' i], div.scheduled-picker .Picker__root:nth-of-type(2) .Picker__trigger").first
      if await date_trig.count() > 0 and await time_trig.count() > 0:
        return date_trig, time_trig
    except Exception:
      pass

    selectors = [
        "input[class*='TUXTextInputCore-input']",
        "div[class*='schedule'] input",
        "div[class*='date-picker'] input",
        "div[class*='time-picker'] input",
        "div[class*='timepicker'] input",
        "div[class*='calendar'] input",
    ]

    inputs = None
    for sel in selectors:
        try:
            cand = self._page.locator(sel)
            if await cand.count() >= 2:
                inputs = cand
                break
        except Exception:
            pass

    if inputs is None:
        inputs = self._page.locator(_Selectors.TIME_INPUT)
        try:
            await inputs.first.wait_for(state="attached", timeout=4000)
        except Exception:
            pass

    count = await inputs.count()
    date_input = None
    time_input = None

    for i in range(count):
      try:
        val = (await inputs.nth(i).input_value()).strip()
        if ":" in val:
          time_input = inputs.nth(i)
        elif "-" in val or "/" in val or any(c.isalpha() for c in val):
          date_input = inputs.nth(i)
      except Exception:
        pass

    if time_input is None and count > 0:
      time_input = inputs.nth(0)
    if date_input is None and count > 1:
      date_input = inputs.nth(1)

    return date_input, time_input

  async def set_time(self, hour: str, minute: str) -> None:
    """
    Set the schedule time using Playwright native locator clicks on TikTok time picker.
    Guarantees React state commit by clicking outside on the container (no Escape key rollback).
    """
    hour_str = str(hour).zfill(2)
    rounded_minute = self._round_minute(int(minute))
    self._logger.info(f"Setting time to {hour_str}:{rounded_minute}")

    # Ensure no blocking modal overlay intercepts pointer events
    await self.dismiss_allow_schedule()
    await self.dismiss_all_popups()

    _, time_trigger = await self._get_schedule_inputs()
    if not time_trigger or await time_trigger.count() == 0:
      time_trigger = self._page.locator('div[role="combobox"][aria-label="Select time"], div[role="combobox"][aria-label*="time" i], .scheduled-picker .Picker__root:nth-of-type(2) .Picker__trigger').first

    if not time_trigger or await time_trigger.count() == 0:
      self._logger.warning("Time trigger/input not found")
      return

    # Open TimePicker dropdown
    await time_trigger.click(force=True)
    await asyncio.sleep(0.5)

    # Click Hour and Minute using Playwright native locator clicks
    h_clicked = False
    m_clicked = False
    try:
      h_btn = self._page.locator(f'button.TimePicker__item[aria-label="Hours {hour_str}"], .TimePicker__column:first-child button:has-text("{hour_str}")').first
      if await h_btn.count() > 0:
        await h_btn.click(force=True)
        h_clicked = True
        await asyncio.sleep(0.3)

      m_btn = self._page.locator(f'button.TimePicker__item[aria-label="Minutes {rounded_minute}"], .TimePicker__column:last-child button:has-text("{rounded_minute}")').first
      if await m_btn.count() > 0:
        await m_btn.click(force=True)
        m_clicked = True
        await asyncio.sleep(0.3)
    except Exception as e:
      self._logger.debug(f"Native time button click error: {e}")

    # Fallback via DOM evaluation if native button click didn't execute
    if not h_clicked or not m_clicked:
      try:
        await self._page.evaluate(
          """
          ([targetHour, targetMin]) => {
            const hBtn = document.querySelector(`button.TimePicker__item[aria-label="Hours ${targetHour}"]`);
            const mBtn = document.querySelector(`button.TimePicker__item[aria-label="Minutes ${targetMin}"]`);
            if (hBtn) hBtn.click();
            if (mBtn) mBtn.click();
          }
          """,
          [hour_str, rounded_minute],
        )
      except Exception:
        pass

    # Commit time selection by clicking outside (CRITICAL: Do NOT press Escape as Escape cancels the selection)
    try:
      commit_target = self._page.locator('.scheduled-title-container, .scheduled-container, div[class*="scheduled-title"]').first
      if await commit_target.count() > 0:
        await commit_target.click(force=True)
      else:
        await self._page.mouse.click(10, 10)
    except Exception:
      pass

    await asyncio.sleep(0.5)
    self._logger.debug(f"Time set to {hour_str}:{rounded_minute} (committed without Escape)")

  async def set_date(self, day: int, month: int, year: int) -> None:
    """
    Set the schedule date using the TikTok calendar picker.
    Supports modern DatePicker panel (button.DatePicker__day) and legacy calendar.
    """
    target_month = self.MONTH_NAMES.get(month, "")
    expected_iso = f"{year:04d}-{month:02d}-{day:02d}"
    self._logger.info(f"Setting date to {target_month} {day}, {year} ({expected_iso})")

    await self.dismiss_allow_schedule()
    await self.dismiss_all_popups()

    date_trigger, _ = await self._get_schedule_inputs()
    if not date_trigger:
      self._logger.warning("Date trigger/input not found")
      return

    # Check if target date is already displayed in trigger
    try:
      curr_val = (await date_trigger.text_content() or await date_trigger.input_value() or "").strip()
      if str(day) in curr_val and (str(year) in curr_val or target_month.lower() in curr_val.lower() or f"{month:02d}" in curr_val):
        self._logger.info(f"Target date {day}/{month}/{year} is already displayed in trigger: '{curr_val}'")
    except Exception:
      pass

    clicked_day = False
    for attempt in range(3):
      await date_trigger.click(force=True)
      await asyncio.sleep(0.6)

      # Click day directly via resilient DOM evaluation inside open calendar
      clicked_day = await self._page.evaluate(
        """
        ([targetDay]) => {
          // 1. Modern TikTok Studio DatePicker days
          const modernDays = [...document.querySelectorAll('button.DatePicker__day, div[class*="DatePicker"] button, [role="gridcell"] button, [role="gridcell"]')].filter(b => {
            const txt = b.textContent.trim();
            const disabled = b.getAttribute('data-disabled') === 'true' || b.getAttribute('aria-disabled') === 'true' || b.disabled;
            return txt === String(targetDay) && !disabled;
          });

          if (modernDays.length > 0) {
            modernDays[0].click();
            return true;
          }

          // 2. Candidate day elements fallback
          const allCandidates = [...document.querySelectorAll('span, div, button, td, a')].filter(el => {
            const txt = (el.innerText || el.textContent || '').trim();
            if (txt !== String(targetDay)) return false;
            if (el.offsetParent === null && el.clientHeight === 0 && el.clientWidth === 0) return false;
            const cls = (el.className || '').toString().toLowerCase();
            if (cls.includes('disabled') || cls.includes('prev-month') || cls.includes('next-month') || cls.includes('outside')) return false;
            if (el.children.length > 1) return false;
            return true;
          });

          if (allCandidates.length > 0) {
            const best = allCandidates.find(el => {
              const p = el.closest('div[class*="calendar"], div[class*="picker"], div[class*="popper"], div[data-floating-ui-portal], table');
              return p !== null;
            }) || allCandidates[allCandidates.length - 1];
            best.click();
            return true;
          }
          return false;
        }
        """,
        [day],
      )

      if clicked_day:
        break
      await asyncio.sleep(0.5)

    # Close calendar with a soft outside click
    try:
      commit_target = self._page.locator('.scheduled-title-container, .scheduled-container, div[class*="scheduled-title"]').first
      if await commit_target.count() > 0:
        await commit_target.click(force=True)
      else:
        await self._page.mouse.click(10, 10)
    except Exception:
      pass
    await asyncio.sleep(0.3)
    self._logger.debug(f"Date set to {target_month} {day}, {year} (clicked={clicked_day})")

  async def set_visibility(self, mode: str) -> None:
    """
    Set the video visibility mode.
    Supports both English and Portuguese dropdowns.
    """
    if mode not in self.VISIBILITY_MAP:
      raise ValueError(
        f"Invalid visibility mode '{mode}'. "
        f"Must be one of: {list(self.VISIBILITY_MAP.keys())}"
      )

    target_terms = self.VISIBILITY_MAP[mode]
    self._logger.info(f"Setting visibility to '{mode}' ({target_terms})")

    # Click visibility dropdown button
    container = self._page.locator(_Selectors.VISIBILITY_CONTAINER)
    await container.wait_for(state="visible", timeout=10000)
    button = container.locator("button")
    btn_txt = (await button.text_content() or "").strip()
    if any(term.lower() in btn_txt.lower() for term in target_terms):
      self._logger.debug(f"Visibility already set to '{mode}' ({btn_txt})")
      return

    await button.click()
    await asyncio.sleep(0.5)

    # Select the matching option
    options = self._page.locator(_Selectors.VISIBILITY_OPTION)
    count = await options.count()

    for i in range(count):
      option = options.nth(i)
      text = (await option.text_content() or "").strip()
      if any(term.lower() in text.lower() for term in target_terms):
        await option.click()
        self._logger.debug(f"Visibility set to '{mode}' ({text})")
        return

    raise SelectorError(f"Visibility option '{target_terms}' not found")

  # ----------------------------------------------------------------
  # Copyright & content quality checks
  # ----------------------------------------------------------------

  async def check_music_copyright(self) -> dict:
    """
    Read the music copyright status from the TikTok upload page.

    Looks for ``div[class*="status-success"]`` and reads the inner
    ``<span>`` text.  A value of ``"No issues found."`` means no
    copyright problem.

    :return: ``{"has_copyright": bool, "message": str}``
    :rtype: dict
    """
    self._logger.info("Checking music copyright...")

    try:
      result = await self._page.evaluate("""
        () => {
          const el = document.querySelector('div[class*="status-success"]');
          if (el) {
            const span = el.querySelector('span');
            return span ? span.textContent.trim() : null;
          }
          return null;
        }
      """)

      if result is None:
        self._logger.warning("Music copyright status element not found")
        return {"has_copyright": False, "message": "Status element not found"}

      r_low = result.lower()
      no_issue = r_low.startswith("no issues") or "nenhum problema" in r_low or "sem problemas" in r_low
      if no_issue:
        self._log_success(f"Music copyright: {result}")
      else:
        self._logger.warning(f"Music copyright issue: {result}")

      return {"has_copyright": not no_issue, "message": result}

    except Exception as e:
      self._logger.debug(f"Error checking music copyright: {e}")
      return {"has_copyright": False, "message": f"Check error: {e}"}

  async def is_post_button_enabled(self) -> bool:
    """
    Check if the post/schedule submission button is present, visible, and enabled.

    Verifies DOM presence, visibility, disabled state, aria-disabled attribute,
    and CSS disabled classes.

    :return: True if the button is active and ready to be clicked.
    :rtype: bool
    """
    try:
      btn = self._page.locator(_Selectors.POST_BUTTON).first
      if await btn.count() == 0:
        btn = self._page.locator("button:has-text('Agendar'), button:has-text('Programar'), button:has-text('Schedule'), button:has-text('Publicar')").first
        if await btn.count() == 0:
          return False
      if not await btn.is_visible():
        return False
      try:
        await btn.scroll_into_view_if_needed(timeout=1000)
      except Exception:
        pass
      if not await btn.is_enabled():
        return False

      # Check for disabled classes or attributes in DOM
      is_disabled_attr = await btn.evaluate("""
        (el) => {
          if (!el) return true;
          if (el.disabled) return true;
          const classList = Array.from(el.classList);
          if (classList.some(c => c.toLowerCase().includes('disabled') && !c.toLowerCase().includes('disabled-hover'))) return true;
          return false;
        }
      """)
      return not is_disabled_attr
    except Exception as e:
      self._logger.debug(f"Error checking if post button is enabled: {e}")
      return False

  async def check_content_quality(self, max_wait_seconds: int = 90) -> dict:
    """
    Check the content quality status with dynamic polling up to 45 seconds.

    If the post/schedule button becomes enabled at any point (e.g. 8s, 20s, 35s),
    the method proceeds immediately without waiting out the remaining window.
    If the button remains disabled after 45 seconds, diagnoses the DOM and
    reports a detailed blocking condition.

    States from TikTok upload page:
    - Preparatory/Pending: ``status-ready``, ``status-checking``
    - Concluded: ``status-success``, ``status-warn``, ``status-limit``, ``status-not-eligible``
    - Error: ``status-error``

    :param max_wait_seconds: Maximum time in seconds to poll for status/readiness (default 45s).
    :type max_wait_seconds: int
    :return: Dict containing state, message, blocking status, and timing telemetry.
    :rtype: dict
    """
    self._logger.info(f"Checking content quality status (dynamic window up to {max_wait_seconds}s)...")

    _JS_GET_STATUS = r"""
      () => {
        const el = document.querySelector(
          'div[class*="status-result"][data-show="true"]'
        );
        if (!el) return null;
        if (/try\s+again\s+tomorrow/si.test(el.textContent)) {
          return "status-limit"
        }
        const classes = Array.from(el.classList);
        const statusClass = classes.filter(
          c => c.startsWith('status') && !c.endsWith('result')
        )[0];
        return statusClass || null;
      }
    """

    status_map = {
      "status-ready": {
        "state": "ready",
        "message": "We'll check your content for For You Feed eligibility.",
        "blocking": False,
      },
      "status-checking": {
        "state": "checking",
        "message": "Checking in progress.",
        "blocking": False,
      },
      "status-success": {
        "state": "success",
        "message": (
          "No issues detected. However, your video may still be "
          "removed later if it violates Community Guidelines."
        ),
        "blocking": False,
      },
      "status-warn": {
        "state": "warning",
        "message": (
          "Content may be restricted. You can still post, but "
          "modifying it to follow guidelines may improve visibility."
        ),
        "blocking": False,
      },
      "status-error": {
        "state": "error",
        "message": "Something went wrong. Please try again later.",
        "blocking": True,
      },
      "status-limit": {
        "state": "limitReached",
        "message": (
          "You've reached your check limit for today. "
          "Please try again tomorrow."
        ),
        "blocking": False,
      },
      "status-not-eligible": {
        "state": "notEligible",
        "message": (
          "This feature isn't available for government, politician, "
          "or political party accounts."
        ),
        "blocking": False,
      },
    }

    pending_states = {"status-ready", "status-checking"}
    poll_interval = 1.5
    elapsed = 0.0

    initial_post_ready = await self.is_post_button_enabled()
    button_enable_wait_sec: float | None = 0.0 if initial_post_ready else None

    while elapsed <= max_wait_seconds:
      # Dismiss any lingering popups or modal overlays during polling
      try:
        await self.dismiss_allow_schedule()
        await self.dismiss_all_popups()
      except Exception:
        pass

      try:
        status_key = await self._page.evaluate(_JS_GET_STATUS)
      except Exception as e:
        self._logger.debug(f"Content check poll error: {e}")
        status_key = None

      # Check if post/schedule button is ready
      post_ready = await self.is_post_button_enabled()

      # Track the exact moment the button transitions from disabled to enabled
      if post_ready and button_enable_wait_sec is None:
        button_enable_wait_sec = round(elapsed, 2)
        self._logger.info(
          f"Post/Schedule button transitioned from disabled to enabled after {button_enable_wait_sec}s"
        )

      # If final check state is reached
      if status_key and status_key not in pending_states:
        info = dict(status_map.get(status_key, {
          "state": status_key,
          "message": f"Status: {status_key}",
          "blocking": status_key == "status-error",
        }))
        if status_key == "status-error" and post_ready:
          info["blocking"] = False
        self._logger.info(
          f"Content quality check resolved: {info['state']} — {info['message']}"
        )
        info["content_processing_wait_sec"] = round(elapsed, 2)
        info["button_enable_wait_sec"] = button_enable_wait_sec
        info["content_check_timeout"] = False
        return info

      # Dynamic exit: if post button is enabled, proceed immediately without waiting for background check
      if post_ready:
        current_state = status_map.get(status_key, {}).get("state", status_key or "checking")
        self._logger.info(
          f"Post button is enabled after {round(elapsed, 2)}s (check '{current_state}') — proceeding immediately."
        )
        return {
          "state": current_state,
          "status_key": status_key,
          "message": "Check in progress — platform permits scheduling",
          "blocking": False,
          "pending": True,
          "content_processing_wait_sec": round(elapsed, 2),
          "button_enable_wait_sec": button_enable_wait_sec,
          "content_check_timeout": False,
        }

      # Button not ready yet; wait short interval
      await asyncio.sleep(poll_interval)
      elapsed += poll_interval

    # If 45s window elapsed, check post button readiness one last time
    final_post_ready = await self.is_post_button_enabled()
    if final_post_ready:
      if button_enable_wait_sec is None:
        button_enable_wait_sec = round(elapsed, 2)
      self._logger.info(
        f"Post button became enabled at the end of window ({round(elapsed, 2)}s) — proceeding."
      )
      return {
        "state": "pending",
        "message": "Check in progress — platform permits scheduling",
        "blocking": False,
        "pending": True,
        "content_processing_wait_sec": round(elapsed, 2),
        "button_enable_wait_sec": button_enable_wait_sec,
        "content_check_timeout": False,
      }

    # Button remained disabled after 45s: diagnose DOM and report
    rejection_diag = await self.diagnose_disabled_button()
    self._logger.warning(
      f"Content quality check window elapsed ({max_wait_seconds}s) and post button remains disabled: {rejection_diag}"
    )
    return {
      "state": "button_disabled",
      "message": f"Post button remained disabled after {max_wait_seconds}s: {rejection_diag}",
      "blocking": True,
      "pending": False,
      "content_processing_wait_sec": round(elapsed, 2),
      "button_enable_wait_sec": None,
      "content_check_timeout": True,
      "schedule_rejection_reason": rejection_diag,
    }

  async def diagnose_disabled_button(self) -> str:
    """Investigate DOM state when post button remains disabled."""
    try:
      return await self._page.evaluate("""
        () => {
          const btn = document.querySelector('button[data-e2e="post_video_button"]');
          if (!btn) return "Botão de publicação não encontrado no DOM";

          // 1. Check for specific schedule / time validation error messages
          const errorNodes = Array.from(document.querySelectorAll(
            "div[class*='error'], span[class*='error'], div[class*='hint'], div[class*='warning'], div[class*='form-item-error'], div[class*='modal-error']"
          ));
          for (const node of errorNodes) {
            const txt = node.textContent ? node.textContent.trim() : "";
            if (txt && (/15\\s*min|20\\s*min|25\\s*min|30\\s*min|escolha\\s+um\\s+horário|choose\\s+a\\s+time|horário|data|invalid|pelo menos|limite|10\\s+dias|antecedência/i.test(txt))) {
              return "Mensagem de validação no formulário: " + txt;
            }
          }

          // 2. Check if video preview is still processing/transcoding
          const loading = document.querySelector('div[class*="loading"], div[class*="spinner"], span[class*="upload-progress"]');
          if (loading && loading.offsetParent !== null) {
            return "Vídeo ainda em processamento/transcodificação pelo TikTok Studio";
          }

          // 3. Check for open blocking modals
          const modalTitle = document.querySelector('div[class*="modal-title"], div[class*="TUXModal-header"]');
          if (modalTitle && modalTitle.offsetParent !== null) {
            return "Modal bloqueador aberto: " + modalTitle.textContent.trim();
          }

          const disabledAttr = btn.disabled ? "disabled=true" : "disabled=false";
          const ariaDisabled = btn.getAttribute('aria-disabled') === 'true' ? "aria-disabled=true" : "aria-disabled=false";
          const classes = Array.from(btn.classList).filter(c => c.includes("disabled")).join(" ") || "sem classe disabled";
          return `Botão inativo (${disabledAttr}, ${ariaDisabled}, ${classes})`;
        }
      """)
    except Exception as e:
      return f"Falha ao diagnosticar estado do botão no DOM: {e}"

  async def click_post(self) -> None:
    """
    Click the post/schedule submission button.

    Locates ``button[data-e2e="post_video_button"]`` or localized action buttons
    ('Agendar', 'Programar', 'Schedule', 'Publicar') and clicks it with force=True.

    :raises SelectorError: If the post button is not found.
    """
    self._logger.info("Clicking post button")

    # Dismiss any leftover blocking overlays first
    await self.dismiss_allow_schedule()
    await self.dismiss_all_popups()

    clicked = False
    try:
      post_button = await self._wait_for_selector(
        _Selectors.POST_BUTTON,
        timeout=5000,
      )
      await post_button.click(force=True)
      clicked = True
    except Exception:
      # Fallback to text-based matching
      try:
        clicked = await self._page.evaluate("""
          () => {
            const btns = Array.from(document.querySelectorAll('button'));
            const actionBtn = btns.find(b => {
              const t = b.textContent.trim().toLowerCase();
              return t === 'agendar' || t === 'programar' || t === 'schedule' || t === 'publicar' || t === 'post';
            });
            if (actionBtn && !actionBtn.disabled) {
              actionBtn.click();
              return true;
            }
            return false;
          }
        """)
      except Exception:
        clicked = False

    if not clicked:
      raise SelectorError("Post/Schedule button not found or not clickable")

    self._logger.debug("Post button clicked")


  # ----------------------------------------------------------------
  # Popup / overlay dismissal (ported from old working code)
  # ----------------------------------------------------------------

  async def dismiss_all_popups(self) -> None:
    """
    Dismiss all potential blocking popups and overlays.

    Called before file upload and after upload completes (before
    caption entry) to clear any modals that TikTok may have shown.
    """
    await self._dismiss_cookie_banner()
    await self._dismiss_content_check_modal()
    await self._dismiss_joyride_overlay()
    await self._dismiss_split_window()
    await self._dismiss_allow_autochecking()

  async def _dismiss_cookie_banner(self) -> None:
    """Dismiss the cookie consent banner if present."""
    try:
      banner = self._page.locator(_Selectors.COOKIE_BANNER)
      if await banner.count() > 0:
        button = banner.locator(_Selectors.COOKIE_BANNER_BUTTON)
        await button.click(timeout=5000)
        await asyncio.sleep(0.5)
        self._logger.debug("Cookie banner dismissed")
    except PlaywrightTimeout:
      pass

  async def _dismiss_joyride_overlay(self) -> None:
    """Dismiss the joyride tutorial overlay if present by removing it from the DOM."""
    try:
      await self._page.evaluate("""() => {
        document.querySelectorAll('#react-joyride-portal, .react-joyride__overlay, .react-joyride__tooltip').forEach(el => el.remove());
      }""")
      self._logger.debug("Joyride overlay removed from DOM")
    except Exception:
      pass

    try:
      close_btn = self._page.locator("button[aria-label='Close'], button:has-text('Skip')")
      if await close_btn.count() > 0:
        await close_btn.first.click(timeout=1000)
        await asyncio.sleep(0.3)
    except Exception:
      pass

  async def _dismiss_split_window(self) -> None:
    """Dismiss the 'Not now' split window popup if present."""
    try:
      not_now = self._page.locator(_Selectors.SPLIT_WINDOW)
      if await not_now.count() > 0:
        await not_now.click(timeout=5000)
        await asyncio.sleep(0.5)
        self._logger.debug("Split window dismissed")
    except PlaywrightTimeout:
      pass

  async def _dismiss_content_check_modal(self) -> None:
    """Dismiss any content checking, guide, or tutorial modal if present (PT & EN)."""
    try:
      clicked = await self._page.evaluate("""
        () => {
          const portal = document.querySelector('div[data-floating-ui-portal], div.TUXModal-overlay, div[class*="common-modal"]');
          if (!portal) return false;
          const btns = Array.from(document.querySelectorAll("button"));
          const b = btns.find(btn => {
            const t = btn.textContent.trim().toLowerCase();
            return t === "ativar" || t === "entendi" || t === "cancelar" || t === "cancel" || t === "permitir" || t === "allow";
          });
          if (b) {
            b.click();
            return true;
          }
          const closeIcon = portal.querySelector('.common-modal-close, button[aria-label="Close"], svg');
          if (closeIcon) {
            closeIcon.click();
            return true;
          }
          return false;
        }
      """)
      if clicked:
        self._logger.debug("Content check / portal modal dismissed")
        await asyncio.sleep(0.5)
    except Exception as e:
      self._logger.debug(f"Error dismissing content check modal: {e}")

  async def _dismiss_allow_autochecking(self) -> None:
    """Dismiss the 'Turn on automatic content checking' modal for fresh accounts."""
    try:
      clicked = await self._page.evaluate("""
        () => {
          const btns = Array.from(document.querySelectorAll("button"));
          const btn = btns.find(b => {
            const t = b.textContent.trim().toLowerCase();
            return t === "turn on" || t === "ativar" || t === "entendi" || t === "got it";
          });
          if (btn) {
            btn.click();
            return true;
          }
          return false;
        }
      """)
      if clicked:
        self._logger.debug("Auto content checking modal dismissed")
        await asyncio.sleep(0.5)
    except Exception as e:
      self._logger.debug(f"Error dismissing auto content checking modal: {e}")

  async def dismiss_allow_schedule(self) -> None:
    """Dismiss the 'Allow scheduling' / 'Permitir publicação agendada' modal for accounts."""
    for _ in range(5):
      try:
        clicked = await self._page.evaluate("""
          () => {
            const btns = Array.from(document.querySelectorAll("button"));
            const allowBtn = btns.find(b => {
              const t = b.textContent.trim().toLowerCase();
              return t === "permitir" || t === "allow" || t === "ativar" || t === "turn on" || t === "entendi" || t === "sim" || t === "ok";
            });
            if (allowBtn && allowBtn.offsetParent !== null) {
              allowBtn.click();
              return true;
            }
            return false;
          }
        """)
        if clicked:
          self._logger.info("Allow scheduling modal dismissed")
          await asyncio.sleep(0.8)
        else:
          break
      except Exception as e:
        self._logger.debug(f"Error dismissing allow schedule modal: {e}")
        break

  async def handle_copyright_modal(self) -> None:
    """
    Handle the 'Continue to post?' copyright confirmation modal.

    After clicking post, TikTok may show a copyright check modal.
    If present, click the 'Post now' primary button to proceed.
    """
    try:
      modal = self._page.locator(_Selectors.COPYRIGHT_MODAL)
      if await modal.count() > 0:
        post_now_btn = modal.locator(_Selectors.COPYRIGHT_POST_NOW)
        if await post_now_btn.count() > 0:
          self._logger.info("Copyright modal detected — clicking 'Post now'")
          await post_now_btn.click()
          await asyncio.sleep(1)
    except PlaywrightTimeout:
      pass
    except Exception as e:
      self._logger.debug(f"Error handling copyright modal: {e}")

  async def handle_post_confirmation_modal(self) -> None:
    """
    Handle any modal prompting confirmation after clicking post
    (e.g., 'Content check in progress. Post anyway?').
    Restricts search strictly inside visible modal containers to avoid
    accidental interaction with background buttons.
    """
    modal_containers = [
      'div[class*="modal"][data-show="true"]',
      'div[class*="TUXModal"]',
      'div[class*="modal"]',
      'div[role="dialog"]',
      'div[class*="dialog"]',
      'div[class*="notification"]',
    ]
    modal_button_texts = [
      "Agendar mesmo assim",
      "Publicar mesmo assim",
      "Schedule anyway",
      "Post anyway",
      "Publicar agora",
      "Post now",
      "Agendar",
      "Schedule",
      "Continuar",
      "Continue",
      "Confirmar",
      "Confirm",
      "Sim",
      "Yes",
    ]

    for container_sel in modal_containers:
      try:
        container = self._page.locator(container_sel)
        if await container.count() > 0 and await container.first.is_visible():
          for btn_text in modal_button_texts:
            btn = container.first.locator(f"button:has-text('{btn_text}')")
            if await btn.count() > 0 and await btn.first.is_visible():
              self._logger.info(
                f"Platform confirmation modal detected ({container_sel}) with '{btn_text}' — clicking to confirm"
              )
              await btn.first.click()
              await asyncio.sleep(0.5)
              return
      except Exception as e:
        self._logger.debug(f"Post confirmation modal check error for {container_sel}: {e}")

  async def handle_all_post_modals(self) -> None:
    """
    Handle any post-click popups, including copyright modal and
    in-progress check confirmation dialogs.
    """
    await asyncio.sleep(0.5)
    await self.handle_copyright_modal()
    await self.handle_post_confirmation_modal()

  async def wait_post_complete(self, timeout: int = 60) -> bool:
    """
    Wait for explicit post or schedule submission confirmation.

    Polls for explicit signals in a loop:
    1. Toast inspection (distinguishes success toasts, rate limit toasts,
       and explicit submission error toasts).
    2. URL redirected to ``/content`` (most reliable after post).
    3. Explicit upload/schedule confirmation text in the DOM.
    4. Warning modal dismissal with at most one re-submission, followed
       by continued polling for actual confirmation.

    Does NOT consider a hidden/missing post button alone or a modal re-click
    as confirmation of publication.

    :param timeout: Maximum wait time in seconds.
    :type timeout: int
    :return: True if post/schedule was explicitly confirmed, False on timeout.
    :rtype: bool
    :raises RateLimitError: If a Toast indicates an account rate limit.
    :raises PostError: If a Toast indicates an explicit submission error.
    """
    self._logger.info("Waiting for post confirmation...")
    poll_interval = 2
    elapsed = 0
    modal_resubmitted = False

    success_toast_pattern = re.compile(
      r"(vídeo\s+.*(publicado|programado|carregado|enviado)|seu\s+vídeo|sua\s+publicação|video\s+(has\s+been\s+)?(published|uploaded|scheduled))",
      re.IGNORECASE,
    )
    rate_limit_pattern = re.compile(
      r"(rate\s*limit|too\s+many|reached.*limit|try\s+again\s+(later|tomorrow)|fast|restricted|maximum\s+number)",
      re.IGNORECASE,
    )

    while elapsed < timeout:
      # Check 0: Toast inspection (success / rate limit / error)
      try:
        toast_text = await self._page.evaluate("""
          () => {
            const el = document.querySelector('div[class*="Toast-content"]');
            return el ? el.textContent.trim() : null;
          }
        """)
        if toast_text:
          if success_toast_pattern.search(toast_text):
            self._log_success(f"Post confirmed via Toast: {toast_text}")
            return True
          if rate_limit_pattern.search(toast_text):
            self._logger.error(f"Rate limit Toast detected: {toast_text}")
            raise RateLimitError(toast_text)
          self._logger.error(f"Submission error Toast detected: {toast_text}")
          raise PostError(toast_text)
      except (RateLimitError, PostError):
        raise
      except Exception:
        pass

      # Check 1: URL redirected to /content or /manage (most reliable)
      current_url = self._page.url.rstrip("/")
      if any(p in current_url for p in ("/content", "/manage", "tiktokstudio/content")):
        self._log_success(f"Post submitted successfully (redirected to {current_url})")
        return True

      # Check 2: explicit confirmation text appeared in DOM
      try:
        confirm = self._page.locator(_Selectors.POST_CONFIRMATION)
        if await confirm.count() > 0 and await confirm.first.is_visible():
          confirm_text = (await confirm.first.text_content() or "").strip()
          self._log_success(f"Post submitted successfully (confirmed: '{confirm_text[:60]}')")
          return True
      except Exception:
        pass

      # Check 2b: Success modal in modern TikTok Studio DOM
      try:
        success_dom = await self._page.evaluate("""
          () => {
            const texts = ['vídeo programado', 'seu vídeo foi programado', 'video scheduled', 'your video has been scheduled', 'gerenciar publicações', 'manage your posts', 'carregar outro vídeo', 'upload another video'];
            const allElements = document.querySelectorAll('h1, h2, h3, h4, div[class*="title"], div[class*="success"], div[role="dialog"]');
            for (const el of allElements) {
              const t = (el.textContent || '').toLowerCase();
              if (texts.some(txt => t.includes(txt))) return el.textContent.trim();
            }
            return null;
          }
        """)
        if success_dom:
          self._log_success(f"Post submitted successfully (DOM success: '{success_dom[:60]}')")
          return True
      except Exception:
        pass

      # Check 3: Active confirmation of any blocking prompt modals (e.g. "Agendar mesmo assim", "Publicar mesmo assim")
      try:
        await self.handle_post_confirmation_modal()
      except Exception as e:
        self._logger.debug(f"Confirmation modal handling probe: {e}")

      # Check 4: If upload form disappeared and post button is gone with no error toast
      try:
        form_gone = await self._page.evaluate("""
          () => {
            const hasCaption = !!document.querySelector('div[contenteditable="true"]');
            const hasPostBtn = !!document.querySelector('button[data-e2e="post_video_button"]');
            const hasError = !!document.querySelector('div[class*="Toast-content"], div[class*="error"]');
            return !hasCaption && !hasPostBtn && !hasError;
          }
        """)
        if form_gone and elapsed >= 10:
          self._log_success("Post submitted successfully (upload form exited without errors)")
          return True
      except Exception:
        pass

      await asyncio.sleep(poll_interval)
      elapsed += poll_interval

    # Save diagnostic screenshot on timeout
    try:
      from pathlib import Path
      ss_dir = Path("logs/screenshots")
      ss_dir.mkdir(parents=True, exist_ok=True)
      ss_path = ss_dir / f"timeout_confirm_{int(time.time())}.png"
      await self._page.screenshot(path=str(ss_path))
      self._logger.warning(f"Screenshot on confirmation timeout saved to: {ss_path}")
    except Exception:
      pass

    self._logger.error(f"Post confirmation timed out after {timeout}s")
    return False

  async def _wait_for_selector(
    self,
    selector: str,
    timeout: int = 10000,
    state: str = "visible",
  ) -> Locator:
    """
    Wait for a DOM element to reach the specified state.

    :param selector: CSS selector string.
    :type selector: str
    :param timeout: Maximum wait time in milliseconds.
    :type timeout: int
    :param state: Expected state ('visible', 'attached', 'hidden').
    :type state: str
    :return: The located element.
    :rtype: Locator
    :raises SelectorError: If the element is not found within the timeout.
    """
    try:
      locator = self._page.locator(selector)
      await locator.first.wait_for(state=state, timeout=timeout)
      return locator.first
    except Exception as e:
      raise SelectorError(
        f"Element not found: '{selector}' (state={state}, "
        f"timeout={timeout}ms): {e}"
      )

  async def _click_by_text(self, tag: str, text: str) -> None:
    """
    Find an element by tag name and exact text content, then click it.

    Uses JavaScript evaluation to filter elements by textContent.

    :param tag: HTML tag name (e.g., 'span', 'div').
    :type tag: str
    :param text: Exact text content to match.
    :type text: str
    :raises SelectorError: If no matching element is found.
    """
    clicked = await self._page.evaluate(
      """
      ([tag, text]) => {
        const elements = [...document.querySelectorAll(tag)];
        const target = elements.filter(el => el.textContent.trim() === text)[0];
        if (target) {
          target.click();
          return true;
        }
        return false;
      }
      """,
      [tag, text],
    )

    if not clicked:
      raise SelectorError(
        f"Element <{tag}> with text '{text}' not found"
      )

  async def _navigate_calendar_to_month(self, target_month: str) -> None:
    """
    Click the right arrow in the calendar until the target month is displayed.

    Reads the ``.month-title`` text and compares to the target month name.
    Stops when matched or after MAX_CALENDAR_NAVIGATION iterations.

    :param target_month: Full month name (e.g., 'February').
    :type target_month: str
    :raises SelectorError: If navigation exceeds maximum iterations.
    """
    calendar = self._page.locator(_Selectors.CALENDAR_WRAPPER)

    PT_MONTHS = {
      "january": "janeiro", "february": "fevereiro", "march": "março", "april": "abril",
      "may": "maio", "june": "junho", "july": "julho", "august": "agosto",
      "september": "setembro", "october": "outubro", "november": "novembro", "december": "dezembro"
    }
    tgt_en = target_month.strip().lower()
    tgt_pt = PT_MONTHS.get(tgt_en, "")

    for attempt in range(self.MAX_CALENDAR_NAVIGATION):
      month_title = calendar.locator(_Selectors.MONTH_TITLE)
      current_text = await month_title.text_content()
      cur_lower = (current_text or "").strip().lower()

      if cur_lower and (tgt_en in cur_lower or (tgt_pt and tgt_pt in cur_lower)):
        self._logger.debug(f"Calendar showing {target_month} ({current_text})")
        return

      # Click right arrow to go to next month
      arrows = calendar.locator(_Selectors.CALENDAR_ARROW)
      right_arrow = arrows.nth(1)
      await right_arrow.click()
      await asyncio.sleep(1)

    raise SelectorError(
      f"Could not navigate calendar to {target_month} "
      f"after {self.MAX_CALENDAR_NAVIGATION} attempts"
    )

  async def _click_calendar_day(self, day: int) -> None:
    """
    Click a specific day number in the visible calendar month.

    Filters ``span[class*="day"]`` elements by text content matching
    the target day number and verifies that the day is not disabled.

    :param day: Day of the month to click (1-31).
    :type day: int
    :raises SelectorError: If the target day is not found or is disabled.
    """
    calendar = self._page.locator(_Selectors.CALENDAR_WRAPPER)

    res = await self._page.evaluate(
      """
      (day) => {
        const calendar = document.querySelector('.calendar-wrapper');
        if (!calendar) return { success: false, reason: "Calendar wrapper not found" };
        const days = [...calendar.querySelectorAll('span[class*="day"]')];
        const target = days.filter(s => s.textContent.trim() === String(day))[0];
        if (!target) return { success: false, reason: "Target day " + day + " not found" };
        const isDis = target.classList.contains('disabled') ||
                      target.classList.contains('day-disabled') ||
                      target.getAttribute('aria-disabled') === 'true';
        if (isDis) {
          return {
            success: false,
            reason: "Dia do calendário (" + day + ") está desabilitado pelo TikTok (passado ou acima de 10 dias)"
          };
        }
        target.click();
        return { success: true };
      }
      """,
      day,
    )

    if not isinstance(res, dict) or not res.get("success"):
      reason = res.get("reason", f"Calendar day {day} not found") if isinstance(res, dict) else f"Calendar day {day} not found"
      raise SelectorError(reason)

  async def _click_option_in_list(
    self,
    list_locator: Locator,
    target_text: str,
  ) -> None:
    """
    Click an option within a timepicker list by matching text content.

    Iterates through div children of the list, verifies it is not disabled,
    and clicks its inner span.

    :param list_locator: Locator for the timepicker option list container.
    :type list_locator: Locator
    :param target_text: Text to match (e.g., '03', '30').
    :type target_text: str
    :raises SelectorError: If the target option is not found or is disabled.
    """
    divs = list_locator.locator("div")
    count = await divs.count()

    for i in range(count):
      div = divs.nth(i)
      text = await div.text_content()
      if text and text.strip() == target_text:
        is_disabled = await div.evaluate("""
          (el) => {
            if (!el) return false;
            if (el.classList.contains('disabled') || el.classList.contains('tiktok-timepicker-option-disabled')) return true;
            if (el.getAttribute('aria-disabled') === 'true') return true;
            const span = el.querySelector('span');
            if (span && (span.classList.contains('disabled') || span.getAttribute('aria-disabled') === 'true')) return true;
            return false;
          }
        """)
        if is_disabled:
          raise SelectorError(
            f"Horário '{target_text}' está desabilitado na lista do timepicker do TikTok (antecedência insuficiente)"
          )

        span = div.locator("span")
        if await span.count() > 0:
          await span.first.click()
        else:
          await div.click()
        return

    raise SelectorError(
      f"Option '{target_text}' not found in timepicker list"
    )

  async def verify_schedule_inputs(
    self,
    expected_hour: str,
    expected_minute: str,
    expected_day: int,
    expected_month_name: str = "",
  ) -> dict[str, Any]:
    """
    Verify schedule inputs in the DOM after setting date and time.

    Checks:
    1. Input values match expected values.
    2. Inline validation error messages in the DOM (e.g. 'at least 15 minutes').
    3. Input fields highlighted with error state or red border.
    4. Readiness of the schedule/post button.

    :return: Dict with {valid: bool, reason: str, time_val: str, date_val: str, button_enabled: bool}.
    """
    self._logger.info("Validating schedule configuration in TikTok Studio DOM...")
    await asyncio.sleep(0.5)

    try:
      res = await self._page.evaluate(r"""
        () => {
          let timeVal = "";
          let dateVal = "";

          // Check modern TikTok Studio Pickers
          const pickers = Array.from(document.querySelectorAll(".scheduled-picker .Picker__root, .scheduled-container .Picker__root, div[class*='scheduled'] .Picker__root"));
          if (pickers.length >= 2) {
            dateVal = (pickers[0].querySelector(".Picker__value")?.textContent || "").trim();
            timeVal = (pickers[1].querySelector(".Picker__value")?.textContent || "").trim();
          }

          // Fallback to inputs
          const inputs = Array.from(document.querySelectorAll("input[class*='TUXTextInputCore-input'], div[class*='schedule'] input"));
          if (!timeVal || !dateVal) {
            for (const inp of inputs) {
              const v = (inp.value || "").trim();
              if (v.includes(":") && !timeVal) timeVal = v;
              else if (v.length > 0 && /\d/.test(v) && !dateVal) dateVal = v;
            }
          }

          const errorNodes = Array.from(document.querySelectorAll(
            "div[class*='error'], span[class*='error'], div[class*='hint'], div[class*='warning'], div[class*='form-item-error'], div[class*='modal-error']"
          ));
          let errorMsg = "";
          for (const node of errorNodes) {
            const txt = node.textContent ? node.textContent.trim() : "";
            // Detect schedule validation rejections in PT and EN: 15/20/25/30 min, "escolha um horário", "between 25 min", "data inválida", etc.
            if (/at\s+least|pelo\s+menos|15\s*min|20\s*min|25\s*min|30\s*min|escolha\s+um\s+horário|choose\s+a\s+time|entre\s+\d+\s*min|between\s+\d+\s*min|horário\s+inválido|data\s+inválida|invalid\s+time|invalid\s+date|limite\s+máximo|maximum\s+limit|10\s+dias|10\s+days|futuro|future|antecedência/i.test(txt)) {
              errorMsg = txt;
              break;
            }
          }

          let hasErrorStyle = false;
          for (const input of inputs) {
            const style = window.getComputedStyle(input);
            if (style.borderColor && (
              style.borderColor.includes("255, 76") ||
              style.borderColor.includes("rgb(254, 44") ||
              style.borderColor.includes("red")
            )) {
              hasErrorStyle = true;
            }
          }

          return {
            timeVal: timeVal,
            dateVal: dateVal,
            errorMsg: errorMsg,
            hasErrorStyle: hasErrorStyle
          };
        }
      """)
    except Exception as e:
      self._logger.debug(f"Error checking schedule inputs in DOM: {e}")
      res = {}

    time_val = res.get("timeVal", "")
    date_val = res.get("dateVal", "")
    error_msg = res.get("errorMsg", "")
    has_error_style = res.get("hasErrorStyle", False)

    if error_msg:
      self._logger.error(f"TikTok DOM schedule error detected: {error_msg}")
      return {
        "valid": False,
        "reason": f"TikTok Studio rejeitou o horário: {error_msg}",
        "time_val": time_val,
        "date_val": date_val,
      }

    if has_error_style:
      self._logger.error("TikTok DOM schedule input highlighted in red (validation error)")
      return {
        "valid": False,
        "reason": "Campo de agendamento destacado em vermelho pelo TikTok Studio",
        "time_val": time_val,
        "date_val": date_val,
      }

    btn_enabled = await self.is_post_button_enabled()
    self._logger.debug(
      f"DOM Schedule verification: time='{time_val}', date='{date_val}', post_button_enabled={btn_enabled}"
    )

    return {
      "valid": True,
      "time_val": time_val,
      "date_val": date_val,
      "button_enabled": btn_enabled,
      "reason": "OK",
    }

  def _round_minute(self, minute: int) -> str:
    """
    Round a minute value to the nearest multiple of 5 and zero-pad.

    TikTok's time picker only accepts multiples of 5 (00, 05, ..., 55).
    Mirrors the DOM.js logic: ``Math.round(parseInt(m) / 5) * 5``.

    :param minute: Minute value (0-59).
    :type minute: int
    :return: Zero-padded string of the rounded minute.
    :rtype: str
    """
    rounded = round(minute / 5) * 5
    rounded = max(0, min(55, rounded))
    return str(rounded).zfill(2)

  async def _humanized_delay(
    self,
    min_ms: int = 300,
    max_ms: int = 800,
  ) -> None:
    """
    Sleep for a random duration to simulate human interaction timing.

    :param min_ms: Minimum delay in milliseconds.
    :type min_ms: int
    :param max_ms: Maximum delay in milliseconds.
    :type max_ms: int
    """
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)

  async def get_logged_in_username(self) -> str | None:
    """
    Detect currently authenticated TikTok username from page DOM elements.

    :return: Sanitized username without leading '@', or None if undetected.
    :rtype: str | None
    """
    try:
      anchors = await self._page.locator("a[href*='/@']").all()
      for a in anchors:
        href = await a.get_attribute("href")
        if href:
          m = re.search(r"/@([\w\.\-]+)", href)
          if m:
            return m.group(1).strip()
        txt = await a.text_content()
        if txt and txt.strip():
          return txt.strip().lstrip("@")
    except Exception as exc:
      self._logger.debug(f"Error reading anchor username: {exc}")

    user_selectors = [
      "[data-tt='header-user-info']",
      ".user-info-name",
      "span[class*='user-info']",
      "p[class*='unique-id']",
    ]
    for sel in user_selectors:
      try:
        loc = self._page.locator(sel)
        if await loc.count() > 0:
          for i in range(await loc.count()):
            text = await loc.nth(i).text_content()
            if text and text.strip():
              return text.strip().lstrip("@")
      except Exception:
        pass
    return None

  async def cancel_or_dismiss_upload(self) -> None:
    """
    Safely dismiss or cancel the current upload draft without posting.
    Used during homologation mode to ensure no pending draft blocks subsequent tasks.
    """
    try:
      cancel_btn = self._page.locator(
        "button:has-text('Discard'), button:has-text('Cancel'), button.Button__root--type-neutral"
      ).first
      if await cancel_btn.count() > 0 and await cancel_btn.is_visible():
        await cancel_btn.click()
        await self._humanized_delay(300, 600)
        confirm_discard = self._page.locator(
          "button:has-text('Discard'), button:has-text('Yes')"
        ).first
        if await confirm_discard.count() > 0 and await confirm_discard.is_visible():
          await confirm_discard.click()
          await self._humanized_delay(300, 600)
    except Exception as exc:
      self._logger.debug(f"Non-critical cleanup in cancel_or_dismiss_upload: {exc}")

