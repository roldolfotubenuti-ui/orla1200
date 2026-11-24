"""Windows DPAPI (Data Protection API) encryption module for TKS Engine.

Provides hardware-bound, user-credential-bound encryption for sensitive
credentials (cookies, session tokens) in rest on Windows.
Ensures zero plain-text cookies are stored in files or exposed in logs.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("tks.crypto")

# Check if running on Windows
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    _CryptProtectData = ctypes.windll.crypt32.CryptProtectData
    _CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _CryptProtectData.restype = wintypes.BOOL

    _CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
    _CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _CryptUnprotectData.restype = wintypes.BOOL

    # CRYPTPROTECT_UI_FORBIDDEN = 0x1
    _CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DPAPIError(Exception):
    """Raised when encryption or decryption with DPAPI fails."""


def encrypt_bytes(data: bytes, description: str = "TKS_Engine_Creds") -> bytes:
    """Encrypt raw bytes using Windows DPAPI CryptProtectData.

    :param data: Plaintext bytes to encrypt.
    :param description: Optional description tag for DPAPI blob.
    :return: Ciphertext bytes.
    :raises DPAPIError: If encryption fails.
    """
    if not IS_WINDOWS:
        # Fallback for non-Windows dev environments: obfuscated base64 with marker
        return b"NON_WIN_DEV:" + base64.b64encode(data)

    if not data:
        return b""

    in_blob = _DATA_BLOB(
        len(data),
        ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_char)),
    )
    out_blob = _DATA_BLOB()

    success = _CryptProtectData(
        ctypes.byref(in_blob),
        description,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )

    if not success:
        err = ctypes.GetLastError()
        raise DPAPIError(f"Windows DPAPI CryptProtectData failed with error code {err}")

    try:
        ciphertext = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return ciphertext
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def decrypt_bytes(ciphertext: bytes) -> bytes:
    """Decrypt ciphertext bytes using Windows DPAPI CryptUnprotectData.

    :param ciphertext: Ciphertext bytes previously encrypted by encrypt_bytes.
    :return: Plaintext bytes.
    :raises DPAPIError: If decryption fails.
    """
    if not IS_WINDOWS:
        if ciphertext.startswith(b"NON_WIN_DEV:"):
            return base64.b64decode(ciphertext[len(b"NON_WIN_DEV:"):])
        return ciphertext

    if not ciphertext:
        return b""

    in_blob = _DATA_BLOB(
        len(ciphertext),
        ctypes.cast(ctypes.create_string_buffer(ciphertext), ctypes.POINTER(ctypes.c_char)),
    )
    out_blob = _DATA_BLOB()

    success = _CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )

    if not success:
        err = ctypes.GetLastError()
        raise DPAPIError(f"Windows DPAPI CryptUnprotectData failed with error code {err}")

    try:
        plaintext = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return plaintext
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def save_encrypted_json(file_path: Path, data: Any, description: str = "TKS_Engine_Creds") -> None:
    """Serialize data to JSON, encrypt it with DPAPI, and save to file atomically.

    :param file_path: Target path for encrypted file.
    :param data: JSON-serializable Python object.
    :param description: Optional description for DPAPI metadata.
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(data, ensure_ascii=False)
    raw_bytes = json_str.encode("utf-8")
    encrypted_bytes = encrypt_bytes(raw_bytes, description=description)

    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    with open(temp_path, "wb") as f:
        f.write(encrypted_bytes)

    # Atomic replace
    temp_path.replace(file_path)


def load_encrypted_json(file_path: Path) -> Any:
    """Read an encrypted file, decrypt using DPAPI, and parse as JSON.

    :param file_path: Path to encrypted file.
    :return: Parsed JSON data.
    :raises DPAPIError: If decryption fails.
    :raises json.JSONDecodeError: If decrypted bytes are not valid JSON.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Encrypted credential file not found: {file_path}")

    with open(file_path, "rb") as f:
        ciphertext = f.read()

    plaintext_bytes = decrypt_bytes(ciphertext)
    return json.loads(plaintext_bytes.decode("utf-8"))
