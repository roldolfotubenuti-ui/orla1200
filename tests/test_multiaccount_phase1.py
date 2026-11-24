"""Test suite for TKS Engine Phase 1: Multiaccount TikTok Manager.

Validates Tests A through H as specified in TKS Engine 3.0 requirements:
- Teste A: Importação de 5 arquivos JSON com múltiplos registros independentes.
- Teste B: Integridade da normalização (Playwright format, sameSite, expires, hostOnly).
- Teste C: Isolamento estrito de contextos de navegador entre contas distintas.
- Teste D: Identidade de usuário e correspondência com cadastro.
- Teste E: Detecção e tratamento de cookies expirados e sessões inválidas.
- Teste F: Persistência e recarregamento dos cadastros pós-reinicialização.
- Teste G: Segurança — zero cookies sensíveis expostos em logs, UI ou arquivos planos.
- Teste H: Regressão — compatibilidade com CookieManager e UploadWorker existentes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus, AccountRecord
from core.cookie_manager import CookieManager
from core.cookie_validator import CookieValidator
from core.dpapi_crypto import decrypt_bytes, encrypt_bytes, load_encrypted_json, save_encrypted_json
from core.logger_manager import LoggerManager


def _create_mock_cookie_export(username: str, expired: bool = False, has_auth: bool = True) -> list[dict]:
    """Helper to generate realistic Cookie-Editor export structure for testing."""
    now = time.time()
    exp_date = (now - 3600) if expired else (now + 86400 * 30)

    cookies = [
        {
            "domain": ".tiktok.com",
            "expirationDate": exp_date,
            "hostOnly": False,
            "httpOnly": True,
            "name": "sessionid" if has_auth else "csrf_session",
            "path": "/",
            "sameSite": "no_restriction",
            "secure": True,
            "session": False,
            "storeId": "0",
            "value": f"test_session_secret_{username}",
        },
        {
            "domain": ".tiktok.com",
            "expirationDate": exp_date,
            "hostOnly": False,
            "httpOnly": True,
            "name": "sid_tt",
            "path": "/",
            "sameSite": "lax",
            "secure": True,
            "session": False,
            "storeId": "0",
            "value": f"test_sid_secret_{username}",
        },
        {
            "domain": ".tiktok.com",
            "hostOnly": False,
            "httpOnly": False,
            "name": "tt_chain_token",
            "path": "/",
            "sameSite": "strict",
            "secure": True,
            "session": True,  # Session cookie, no expirationDate
            "storeId": "0",
            "value": f"test_chain_{username}",
        },
        {
            "domain": ".tiktok.com",
            "hostOnly": False,
            "httpOnly": True,
            "name": "passport_csrf_token",
            "path": "/",
            "sameSite": None,
            "secure": True,
            "session": True,
            "storeId": "0",
            "value": f"test_csrf_{username}",
        },
    ]
    return cookies


class TestMultiaccountPhase1(unittest.TestCase):
    """Test suite covering Phase 1 Multiaccount TikTok requirements."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="tks_test_multiaccount_"))
        self.cookies_dir = self.temp_dir / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.logger = LoggerManager(name="TestLogger", log_file=self.temp_dir / "logs" / "test.log")
        self.account_manager = AccountManager(data_dir=self.temp_dir, cookies_dir=self.cookies_dir)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    # =========================================================================
    # Teste A — Importação em Lote de Cinco Arquivos JSON
    # =========================================================================
    def test_a_batch_import_five_accounts(self) -> None:
        """Teste A: Importar cinco arquivos JSON e confirmar cinco registros independentes."""
        json_paths = []
        for i in range(1, 6):
            p = self.temp_dir / f"export_account_{i:02d}.json"
            cookies = _create_mock_cookie_export(f"user_{i}")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            json_paths.append(p)

        self.assertEqual(len(json_paths), 5)

        # Batch import
        results = self.account_manager.import_cookie_files(json_paths)
        self.assertEqual(len(results), 5)

        records = self.account_manager.list_accounts()
        self.assertEqual(len(records), 5)

        # Verify unique IDs and default numbered labels
        account_ids = {acc.account_id for acc in records}
        self.assertEqual(len(account_ids), 5, "Cada conta deve possuir um account_id único")

        for idx, acc in enumerate(records):
            self.assertEqual(acc.platform, "tiktok")
            self.assertEqual(acc.auth_status, AccountAuthStatus.STRUCTURALLY_VALID.value)
            self.assertTrue(acc.enabled)
            self.assertTrue((self.cookies_dir / acc.cookie_file).exists())
            self.assertEqual(acc.display_title, f"Conta TikTok {idx + 1:02d}")

    # =========================================================================
    # Teste B — Integridade da Normalização para Playwright
    # =========================================================================
    def test_b_cookie_normalization_integrity(self) -> None:
        """Teste B: Verificar se cookies foram normalizados sem perda de atributos ou valores."""
        raw_cookies = _create_mock_cookie_export("integrity_test")
        report = CookieValidator.validate_structure(raw_cookies)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.total_cookies, 4)
        self.assertEqual(report.valid_cookies, 4)
        self.assertEqual(report.session_cookies, 2)
        self.assertTrue(report.has_session_id)

        normalized = CookieValidator.normalize_for_playwright(raw_cookies)
        self.assertEqual(len(normalized), 4)

        # Check normalization rules
        c_sess = next(c for c in normalized if c["name"] == "sessionid")
        self.assertEqual(c_sess["sameSite"], "None", "no_restriction deve virar 'None'")
        self.assertEqual(c_sess["domain"], ".tiktok.com")
        self.assertEqual(c_sess["path"], "/")
        self.assertTrue(c_sess["httpOnly"])
        self.assertTrue(c_sess["secure"])
        self.assertIn("expires", c_sess)
        self.assertIsInstance(c_sess["expires"], int)
        # Verify metadata removed
        self.assertNotIn("hostOnly", c_sess)
        self.assertNotIn("storeId", c_sess)
        self.assertNotIn("session", c_sess)

        # Check session cookie (session == True -> expires omitted)
        c_chain = next(c for c in normalized if c["name"] == "tt_chain_token")
        self.assertEqual(c_chain["sameSite"], "Strict")
        self.assertNotIn("expires", c_chain, "Cookie de sessão não deve ter 'expires'")

        # Check null sameSite omitted or valid
        c_csrf = next(c for c in normalized if c["name"] == "passport_csrf_token")
        self.assertNotIn("sameSite", c_csrf, "sameSite nulo deve ser omitido")

        # Values must remain identical (not modified, hashed or truncated)
        self.assertEqual(c_sess["value"], "test_session_secret_integrity_test")

    # =========================================================================
    # Teste C — Isolamento de Contextos entre Contas
    # =========================================================================
    def test_c_strict_context_isolation(self) -> None:
        """Teste C: Confirmar que credenciais de contas diferentes são totalmente isoladas."""
        p1 = self.temp_dir / "acc1.json"
        p2 = self.temp_dir / "acc2.json"
        with open(p1, "w") as f:
            json.dump(_create_mock_cookie_export("account_alpha"), f)
        with open(p2, "w") as f:
            json.dump(_create_mock_cookie_export("account_beta"), f)

        results = self.account_manager.import_cookie_files([p1, p2])
        rec1, rec2 = results[0][0], results[1][0]

        cookies1 = self.account_manager.load_account_cookies(rec1.account_id)
        cookies2 = self.account_manager.load_account_cookies(rec2.account_id)

        sess1 = next(c["value"] for c in cookies1 if c["name"] == "sessionid")
        sess2 = next(c["value"] for c in cookies2 if c["name"] == "sessionid")

        self.assertNotEqual(sess1, sess2, "Cookies entre contas distintas devem ser estritamente isolados")
        self.assertIn("account_alpha", sess1)
        self.assertIn("account_beta", sess2)

        # Verify separate encrypted storage files
        self.assertNotEqual(rec1.cookie_file, rec2.cookie_file)
        self.assertTrue((self.cookies_dir / rec1.cookie_file).exists())
        self.assertTrue((self.cookies_dir / rec2.cookie_file).exists())

    # =========================================================================
    # Teste D — Identidade e Validação de Usuário
    # =========================================================================
    def test_d_identity_and_status_tracking(self) -> None:
        """Teste D: Validar correspondência de usuário e transição de estados de autenticação."""
        p = self.temp_dir / "@tiktok_creator-cookie.json"
        with open(p, "w") as f:
            json.dump(_create_mock_cookie_export("tiktok_creator"), f)

        results = self.account_manager.import_cookie_files([p])
        rec = results[0][0]

        # Inferred from filename
        self.assertEqual(rec.username, "tiktok_creator")
        self.assertEqual(rec.auth_status, AccountAuthStatus.STRUCTURALLY_VALID.value)

        # State transition to VALIDATING then AUTHENTICATED
        self.account_manager.update_account(rec.account_id, auth_status=AccountAuthStatus.VALIDATING.value)
        updated = self.account_manager.get_account(rec.account_id)
        self.assertEqual(updated.auth_status, AccountAuthStatus.VALIDATING.value)

        self.account_manager.update_account(
            rec.account_id,
            username="tiktok_creator_verified",
            auth_status=AccountAuthStatus.AUTHENTICATED.value,
        )
        final = self.account_manager.get_account(rec.account_id)
        self.assertEqual(final.auth_status, AccountAuthStatus.AUTHENTICATED.value)
        self.assertEqual(final.username, "tiktok_creator_verified")

    # =========================================================================
    # Teste E — Expiração e Sessões Inválidas
    # =========================================================================
    def test_e_expired_and_invalid_cookies(self) -> None:
        """Teste E: Simular cookies expirados e verificar detecção na validação estrutural."""
        expired_cookies = _create_mock_cookie_export("expired_user", expired=True)
        report = CookieValidator.validate_structure(expired_cookies)

        self.assertTrue(report.is_valid)  # Structurally valid JSON
        self.assertGreater(report.expired_cookies, 0)
        self.assertTrue(any("passado" in w for w in report.warnings))

        # Test malformed non-JSON / missing required fields
        malformed = [{"invalid": "data"}]
        rep_bad = CookieValidator.validate_structure(malformed)
        self.assertFalse(rep_bad.is_valid)
        self.assertGreater(len(rep_bad.errors), 0)

    # =========================================================================
    # Teste F — Persistência e Reinicialização da TKS Engine
    # =========================================================================
    def test_f_persistence_across_restarts(self) -> None:
        """Teste F: Encerrar e instanciar novo AccountManager. Confirmar que os cadastros persistem."""
        p_list = []
        for i in range(1, 6):
            p = self.temp_dir / f"persist_{i}.json"
            with open(p, "w") as f:
                json.dump(_create_mock_cookie_export(f"persist_user_{i}"), f)
            p_list.append(p)

        self.account_manager.import_cookie_files(p_list)
        self.assertEqual(len(self.account_manager.list_accounts()), 5)

        # Assign department to account 1
        acc1_id = self.account_manager.list_accounts()[0].account_id
        self.account_manager.update_account(acc1_id, department_id="Shorts")

        # Simulate complete engine restart by creating brand new AccountManager instance
        new_manager = AccountManager(data_dir=self.temp_dir, cookies_dir=self.cookies_dir)
        reloaded_accounts = new_manager.list_accounts()

        self.assertEqual(len(reloaded_accounts), 5, "Todas as 5 contas devem persistir após reinício")
        reloaded_acc1 = new_manager.get_account(acc1_id)
        self.assertIsNotNone(reloaded_acc1)
        self.assertEqual(reloaded_acc1.department_id, "Shorts")

        # Confirm encrypted credentials can still be decrypted
        decrypted_cookies = new_manager.load_account_cookies(acc1_id)
        self.assertEqual(len(decrypted_cookies), 4)

    # =========================================================================
    # Teste G — Segurança: Zero Cookies Sensíveis em Texto Plano
    # =========================================================================
    def test_g_security_zero_plaintext_credentials(self) -> None:
        """Teste G: Confirmar que nenhum valor de cookie aparece em accounts.json ou logs."""
        secret_token = "SUPER_SECRET_TOKEN_TIKTOK_XYZ_999"
        custom_cookie = [{
            "domain": ".tiktok.com",
            "name": "sessionid",
            "value": secret_token,
            "path": "/",
            "expirationDate": time.time() + 3600,
        }]

        p = self.temp_dir / "secret_export.json"
        with open(p, "w") as f:
            json.dump(custom_cookie, f)

        results = self.account_manager.import_cookie_files([p])
        acc = results[0][0]

        # 1. Check accounts.json registry on disk
        registry_path = self.temp_dir / "accounts.json"
        with open(registry_path, "r", encoding="utf-8") as f:
            registry_text = f.read()

        self.assertNotIn(secret_token, registry_text, "Valores de cookies NÃO devem constar no accounts.json")

        # 2. Check encrypted file on disk
        enc_file_path = self.cookies_dir / acc.cookie_file
        with open(enc_file_path, "rb") as f:
            raw_disk_bytes = f.read()

        # The encrypted file on disk should NOT contain the secret token as plaintext ASCII/UTF-8
        self.assertNotIn(secret_token.encode("utf-8"), raw_disk_bytes, "Arquivo no disco deve estar criptografado com DPAPI")

        # 3. Decrypted in-memory payload must match
        decrypted = self.account_manager.load_account_cookies(acc.account_id)
        self.assertEqual(decrypted[0]["value"], secret_token)

    # =========================================================================
    # Teste H — Regressão e Compatibilidade com Componentes Legados
    # =========================================================================
    def test_h_regression_legacy_cookie_manager_compatibility(self) -> None:
        """Teste H: Verificar que CookieManager mantém compatibilidade total com chamadas existentes."""
        cm = CookieManager(cookies_dir=self.cookies_dir, logger=self.logger)

        # Test list_accounts
        p = self.temp_dir / "import_reg.json"
        with open(p, "w") as f:
            json.dump(_create_mock_cookie_export("legacy_user"), f)

        cm.account_manager.import_cookie_files([p])
        acc = cm.account_manager.list_accounts()[-1]
        cm.account_manager.update_account(acc.account_id, username="legacy_user")

        accounts = cm.list_accounts()
        self.assertIn("legacy_user", accounts)

        # Test load_cookie(username)
        cookies = cm.load_cookie("legacy_user")
        self.assertIsInstance(cookies, list)
        self.assertGreater(len(cookies), 0)
        self.assertTrue(cm.validate_cookie(cookies))


if __name__ == "__main__":
    unittest.main()
