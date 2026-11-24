"""Validate the 6 registered accounts in read-only mode via Playwright."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import logging
from core.account_manager import AccountManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tks.validate")

async def main():
    acc_mgr = AccountManager()
    accounts = [acc for acc in acc_mgr.list_accounts() if acc.display_title and "Conta 0" in acc.display_title]
    accounts.sort(key=lambda a: a.display_title)

    logger.info(f"Encontradas {len(accounts)} contas para validação:")
    for acc in accounts:
        logger.info(f" - {acc.display_title} (ID: {acc.account_id}) | Dept: {acc.department_id}")

    results = []
    for idx, acc in enumerate(accounts):
        logger.info(f"\n==========================================")
        logger.info(f"[{idx+1}/6] Validando {acc.display_title}...")
        logger.info(f"==========================================")
        try:
            is_auth, msg, detected_user = await acc_mgr.validate_tiktok_session(acc.account_id, headless=True)
            refreshed = acc_mgr.get_account(acc.account_id)
            res = {
                "account_id": acc.account_id,
                "title": acc.display_title,
                "department": acc.department_id,
                "is_auth": is_auth,
                "status_msg": msg,
                "detected_user": detected_user or refreshed.username,
                "final_status": refreshed.auth_status,
                "last_error": refreshed.last_error,
                "cookie_count": acc.cookie_count,
            }
            results.append(res)
            logger.info(f"Resultado: is_auth={is_auth} | status={refreshed.auth_status} | user=@{detected_user or refreshed.username} | msg={msg}")
        except Exception as exc:
            logger.error(f"Exceção na validação de {acc.display_title}: {exc}")
            results.append({
                "account_id": acc.account_id,
                "title": acc.display_title,
                "department": acc.department_id,
                "is_auth": False,
                "status_msg": str(exc),
                "detected_user": None,
                "final_status": "ERROR",
                "last_error": str(exc),
                "cookie_count": acc.cookie_count,
            })

    with open("storage/validation_results_6_accounts.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("\nValidação concluída! Resultados gravados em storage/validation_results_6_accounts.json")

if __name__ == "__main__":
    asyncio.run(main())
