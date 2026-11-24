"""Cookie validation, structural inspection, and normalization for TKS Engine.

Specifically designed for Chrome Cookie-Editor exports and Playwright Async API.
Ensures zero alteration of sensitive values while adapting fields to Playwright specs.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CookieValidationReport:
    """Detailed structural validation report for a cookie export file."""
    is_valid: bool = False
    total_cookies: int = 0
    valid_cookies: int = 0
    session_cookies: int = 0
    expired_cookies: int = 0
    auth_cookies_found: list[str] = field(default_factory=list)
    has_session_id: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a human-readable summary of the validation report."""
        if not self.is_valid:
            return f"Inválido: {'; '.join(self.errors[:2])}"
        auth_note = f"Auth ({', '.join(self.auth_cookies_found)})" if self.auth_cookies_found else "Sem cookies de auth conhecidos"
        return f"{self.valid_cookies} cookies válidos ({self.session_cookies} sessão, {self.expired_cookies} expirados) - {auth_note}"


class CookieValidator:
    """Validates and normalizes Chrome Cookie-Editor exports for Playwright."""

    REQUIRED_FIELDS = ["name", "value", "domain", "path"]

    KNOWN_FIELDS = {
        "domain", "expirationDate", "expires", "hostOnly", "httpOnly",
        "name", "path", "sameSite", "secure", "session", "storeId", "value", "id"
    }

    AUTH_COOKIE_NAMES = {
        "sessionid", "sessionid_ss", "sid_tt", "uid_tt", "passport_csrf_token",
        "passport_auth_status", "sid_guard", "sid_ucp_v1", "ssid_ucp_v1"
    }

    SAME_SITE_MAP = {
        "no_restriction": "None",
        "none": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": None,
    }

    @classmethod
    def validate_structure(cls, data: Any, current_epoch: float | None = None) -> CookieValidationReport:
        """Perform comprehensive structural validation on raw cookie data.

        :param data: Parsed JSON data (expected list of dicts).
        :param current_epoch: Optional reference epoch timestamp for expiration check.
        :return: CookieValidationReport detailing structural health.
        """
        report = CookieValidationReport()
        if current_epoch is None:
            current_epoch = time.time()

        if not isinstance(data, list):
            report.errors.append("A raiz do JSON deve ser uma lista (array) de objetos de cookies.")
            return report

        if len(data) == 0:
            report.errors.append("O array de cookies está vazio.")
            return report

        report.total_cookies = len(data)
        unknown_fields_set = set()
        auth_found_set = set()

        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                report.errors.append(f"O item #{idx + 1} não é um objeto JSON válido.")
                continue

            # Check required fields
            missing_fields = []
            for rf in cls.REQUIRED_FIELDS:
                val = item.get(rf)
                if val is None or not isinstance(val, str):
                    missing_fields.append(rf)

            if missing_fields:
                report.errors.append(f"Cookie #{idx + 1} ausente ou com tipo inválido nos campos: {', '.join(missing_fields)}.")
                continue

            # Check unknown fields without discarding them
            for k in item.keys():
                if k not in cls.KNOWN_FIELDS:
                    unknown_fields_set.add(k)

            cookie_name = str(item.get("name", "")).strip()
            if cookie_name.lower() in cls.AUTH_COOKIE_NAMES:
                auth_found_set.add(cookie_name)

            # Check expiration and session nature
            is_session = bool(item.get("session", False))
            exp_date = item.get("expirationDate") or item.get("expires")

            if is_session or exp_date is None:
                report.session_cookies += 1
            elif isinstance(exp_date, (int, float)):
                exp_seconds = float(exp_date)
                if exp_seconds > 10_000_000_000:
                    exp_seconds /= 1000.0
                if exp_seconds < current_epoch:
                    report.expired_cookies += 1

            report.valid_cookies += 1

        report.unknown_fields = sorted(list(unknown_fields_set))
        report.auth_cookies_found = sorted(list(auth_found_set))
        report.has_session_id = bool(auth_found_set.intersection({"sessionid", "sessionid_ss", "sid_tt"}))

        if report.valid_cookies > 0 and len(report.errors) == 0:
            report.is_valid = True

        if report.expired_cookies > 0:
            report.warnings.append(f"{report.expired_cookies} cookies estão com data de expiração no passado.")

        if not report.has_session_id:
            report.warnings.append("Nenhum cookie de sessão essencial (sessionid/sid_tt) foi encontrado.")

        return report

    @classmethod
    def normalize_for_playwright(cls, raw_cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw Cookie-Editor cookies into Playwright-accepted format.

        Rules:
        - expirationDate converted to expires (int Unix seconds).
        - If session == True, expires is omitted.
        - sameSite normalized: no_restriction -> 'None', lax -> 'Lax', strict -> 'Strict'.
          If null or unspecified, omit sameSite.
        - Remove Cookie-Editor metadata: hostOnly, storeId, session.
        - Preserve name, value, domain, path, secure, httpOnly.
        - Never modify cookie values or remove httpOnly cookies.
        """
        normalized_list: list[dict[str, Any]] = []

        for item in raw_cookies:
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            value = item.get("value")
            domain = item.get("domain")
            path = item.get("path") or "/"

            if not isinstance(name, str) or not name.strip():
                continue
            if value is None:
                continue
            if not isinstance(value, str):
                value = str(value)
            if not isinstance(domain, str) or not domain.strip():
                continue
            if not isinstance(path, str) or not path.startswith("/"):
                path = "/"

            pw_cookie: dict[str, Any] = {
                "name": name.strip(),
                "value": value,
                "domain": domain.strip(),
                "path": path,
                "secure": bool(item.get("secure", False)),
                "httpOnly": bool(item.get("httpOnly", False)),
            }

            # Normalize sameSite
            raw_samesite = item.get("sameSite")
            if raw_samesite is not None:
                if isinstance(raw_samesite, str):
                    mapped = cls.SAME_SITE_MAP.get(raw_samesite.strip().lower())
                    if mapped in ("Strict", "Lax", "None"):
                        pw_cookie["sameSite"] = mapped
                elif isinstance(raw_samesite, (int, float)):
                    num_map = {0: "None", 1: "Lax", 2: "Strict"}
                    if int(raw_samesite) in num_map:
                        pw_cookie["sameSite"] = num_map[int(raw_samesite)]

            # Normalize expires
            is_session = bool(item.get("session", False))
            exp_val = item.get("expirationDate") or item.get("expires")

            if not is_session and exp_val is not None:
                try:
                    exp_float = float(exp_val)
                    if exp_float > 10_000_000_000:
                        exp_float /= 1000.0
                    pw_cookie["expires"] = int(exp_float)
                except (ValueError, TypeError):
                    pass

            normalized_list.append(pw_cookie)

        return normalized_list

    @classmethod
    def parse_file(cls, file_path: Path) -> tuple[CookieValidationReport, list[dict[str, Any]]]:
        """Read a JSON cookie file, validate structure, and return report plus normalized cookies.

        :param file_path: Path to the cookie JSON file.
        :return: (ValidationReport, normalized_cookies_list)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            rep = CookieValidationReport()
            rep.errors.append(f"Arquivo não encontrado: {file_path}")
            return rep, []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as exc:
            rep = CookieValidationReport()
            rep.errors.append(f"Erro de sintaxe JSON: {exc}")
            return rep, []
        except Exception as exc:
            rep = CookieValidationReport()
            rep.errors.append(f"Erro ao ler arquivo: {exc}")
            return rep, []

        report = cls.validate_structure(raw_data)
        normalized = cls.normalize_for_playwright(raw_data) if report.is_valid else []
        return report, normalized
