"""Script to import, encrypt via DPAPI, associate departments, and validate the 6 TikTok accounts."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus
from utils.app_paths import get_cookies_dir, get_user_data_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tks.import")

# Mapping of the 6 drawers to platforms/departments
DRAWER_MAPPING = [
    {"index": 1, "drawer": "Superior esquerda", "department": "Instagram", "title": "Conta 01 — Instagram"},
    {"index": 2, "drawer": "Superior direita", "department": "Mercado Livre", "title": "Conta 02 — Mercado Livre"},
    {"index": 3, "drawer": "Central esquerda", "department": "Shorts", "title": "Conta 03 — Shorts"},
    {"index": 4, "drawer": "Central direita", "department": "TikTok", "title": "Conta 04 — TikTok"},
    {"index": 5, "drawer": "Inferior esquerda", "department": "TikTok Shop", "title": "Conta 05 — TikTok Shop"},
    {"index": 6, "drawer": "Inferior direita", "department": "YouTube", "title": "Conta 06 — YouTube"},
]


async def run_import_and_validation(temp_json_paths: list[Path]):
    acc_mgr = AccountManager()
    logger.info(f"Importando {len(temp_json_paths)} arquivos de cookies com proteção Windows DPAPI...")

    import_results = acc_mgr.import_cookie_files(temp_json_paths)

    imported_records = []
    for idx, (record, report) in enumerate(import_results):
        mapping = DRAWER_MAPPING[idx]
        acc_mgr.update_account(
            record.account_id,
            department_id=mapping["department"],
        )
        record.display_title = mapping["title"]
        acc_mgr._save_registry()

        logger.info(
            f"[{idx+1}/6] {mapping['title']} | Departamento: {mapping['department']} | "
            f"Válido: {report.is_valid} | Cookies: {report.valid_cookies} ({report.session_cookies} sessão) | "
            f"Arquivo DPAPI: {record.cookie_file}"
        )
        imported_records.append(record)

    logger.info("\n--- INICIANDO VALIDAÇÃO REAL DE SESSÕES (MODO LEITURA - ZERO UPLOADS) ---")
    validation_results = []

    for idx, rec in enumerate(imported_records):
        mapping = DRAWER_MAPPING[idx]
        logger.info(f"\nValidando {mapping['title']} (ID: {rec.account_id})...")
        try:
            is_auth, msg, detected_user = await acc_mgr.validate_tiktok_session(rec.account_id, headless=True)
            validation_results.append({
                "account_id": rec.account_id,
                "title": mapping["title"],
                "department": mapping["department"],
                "drawer": mapping["drawer"],
                "is_auth": is_auth,
                "status_msg": msg,
                "detected_user": detected_user,
                "final_status": acc_mgr.get_account(rec.account_id).auth_status,
                "cookie_count": rec.cookie_count,
            })
            logger.info(f"Resultado {mapping['title']}: is_auth={is_auth}, user=@{detected_user}, status={msg}")
        except Exception as exc:
            logger.error(f"Erro ao validar {mapping['title']}: {exc}")
            validation_results.append({
                "account_id": rec.account_id,
                "title": mapping["title"],
                "department": mapping["department"],
                "drawer": mapping["drawer"],
                "is_auth": False,
                "status_msg": str(exc),
                "detected_user": None,
                "final_status": AccountAuthStatus.INVALID_SESSION.value,
                "cookie_count": rec.cookie_count,
            })

    # Save summary report in storage
    summary_path = Path("storage/multiaccount_import_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(validation_results, f, indent=2, ensure_ascii=False)

    logger.info(f"\nResumo da importação gravado em {summary_path}")
    return validation_results
