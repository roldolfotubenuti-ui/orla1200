from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.browser_manager import AuthenticationError, BrowserManager
from core.config_manager import ConfigManager
from core.cookie_manager import CookieError, CookieManager
from core.dom_handler import DOMHandler, _Selectors
from core.logger_manager import LoggerManager
from core.schedule_rule_engine import ScheduleRuleEngine
from utils.datetime_utils import DateTimeUtils


async def run_dry_run_check(username: str | None = None, hold_seconds: int = 30) -> int:
  """
  Run a safe, visible-browser dry-run up to schedule field verification.
  NEVER clicks the Post or Schedule submission button.
  """
  config = ConfigManager(project_root / "config.json")
  logger = LoggerManager(name="DryRunInspector", level=config.effective_log_level)
  cookies_dir = project_root / config.cookies_dir
  cookie_manager = CookieManager(cookies_dir, logger)
  rules = ScheduleRuleEngine(config)
  dt_utils = DateTimeUtils()

  accounts = cookie_manager.list_accounts()
  if not accounts:
    logger.error(
      "Nenhuma conta cadastrada em cookies/ (@username-cookie.json). "
      "Adicione sua conta na aba 'Accounts' da interface gráfica primeiro."
    )
    return 1

  target_user = username if (username and username in accounts) else accounts[0]
  logger.info(f"Conta selecionada para validação (Dry-Run): @{target_user}")

  # Step 1: Validate cookie loading and normalization (without logging values)
  try:
    normalized_cookies = cookie_manager.load_cookie(target_user)
    cookie_names = [c.get("name", "") for c in normalized_cookies]
    has_session = any(n in ("sessionid", "sessionid_ss", "sid_tt", "uid_tt") for n in cookie_names)
    logger.info(
      f"Cookies normalizados: {len(normalized_cookies)} entradas | "
      f"Cookies de sessão presentes: {has_session}"
    )
  except CookieError as exc:
    logger.error(f"Falha ao validar arquivo de cookies para @{target_user}: {exc}")
    return 1

  # Step 2: Locate the single test video
  test_video = project_root / "test_videos" / "video_teste_01.mp4"
  if not test_video.exists():
    logger.error(f"Vídeo de teste não encontrado em: {test_video}")
    return 1

  # Step 3: Launch visible browser (headless=False) and verify authentication
  browser_manager = BrowserManager(
    cookie_manager=cookie_manager,
    logger=logger,
    headless=False,
  )

  try:
    await browser_manager.launch(target_user)
    logger.success(f"Autenticação confirmada no TikTok Studio para @{target_user}!")

    page = browser_manager.get_page()
    dom = DOMHandler(page, logger, dt_utils)

    # Dismiss initial popups
    await dom.dismiss_all_popups()

    # Attach test video to inspect the form and schedule selectors
    logger.info(f"Anexando vídeo de teste ({test_video.name}) para habilitar o formulário...")
    await dom.upload_file(test_video)
    upload_ok = await dom.wait_upload_complete(timeout=120)
    if not upload_ok:
      logger.error("Timeout aguardando processamento do vídeo de teste no formulário.")
      return 1

    await dom.dismiss_all_popups()

    # Test caption field
    test_caption = "Teste controlado TKS Engine (Dry-Run - Nao Publicar)"
    await dom.set_caption(test_caption)
    logger.success("Seletor de legenda (CAPTION_EDITOR) validado com sucesso.")

    # Test schedule toggle and date/time pickers
    target_dt = rules.min_allowed_datetime(datetime.now()) + timedelta(minutes=30)
    target_dt = rules.round_minute_up(target_dt)
    hour_str, minute_str = DateTimeUtils.parse_hour_minute(target_dt)
    day, month, year = DateTimeUtils.parse_day_month_year(target_dt)

    logger.info("Testando seletor de agendamento (enable_schedule)...")
    await dom.enable_schedule()
    await dom.dismiss_allow_schedule()
    logger.success("Toggle de agendamento ('Schedule') ativado com sucesso.")

    logger.info(f"Testando seletor de horário ({hour_str}:{minute_str})...")
    await dom.set_time(hour_str, minute_str)
    logger.success(f"Horário ({hour_str}:{minute_str}) preenchido com sucesso.")

    logger.info(f"Testando seletor de calendário ({day:02d}/{month:02d}/{year})...")
    await dom.set_date(day, month, year)
    logger.success(f"Data ({day:02d}/{month:02d}/{year}) selecionada com sucesso.")

    # Verify Post/Schedule button presence WITHOUT clicking it
    post_btn = page.locator(_Selectors.POST_BUTTON)
    btn_visible = await post_btn.count() > 0 and await post_btn.first.is_visible()
    btn_text = (await post_btn.first.text_content() or "").strip() if btn_visible else "N/A"
    logger.success(
      f"Botão de submissão localizado (visível={btn_visible}, texto='{btn_text}'). "
      "PARADA DE SEGURANÇA ATINGIDA — Nenhum clique em Post/Schedule foi executado!"
    )

    logger.info(
      f"Mantendo navegador aberto por {hold_seconds}s para inspeção visual (sem submeter)..."
    )
    await asyncio.sleep(hold_seconds)
    return 0

  except AuthenticationError as exc:
    logger.error(f"Falha de autenticação no TikTok Studio: {exc}")
    return 2
  except Exception as exc:
    logger.error(f"Erro durante verificação de seletores no TikTok Studio: {exc}")
    return 3
  finally:
    await browser_manager.close()


if __name__ == "__main__":
  user_arg = sys.argv[1] if len(sys.argv) > 1 else None
  sys.exit(asyncio.run(run_dry_run_check(user_arg)))
