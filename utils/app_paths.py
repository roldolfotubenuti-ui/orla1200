"""Application path resolution and user data isolation for TKS Engine.

Ensures the application runs anywhere without hardcoded paths and safely separates
static read-only app assets from writable user data (AppData/Roaming).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_NAME = "TKS_Engine"


def is_frozen() -> bool:
    """Return True if running as a compiled PyInstaller executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_app_install_dir() -> Path:
    """Return the static installation directory containing binary and bundled assets.

    In development: the repository root.
    When frozen: the folder containing the executable (or _MEIPASS for bundled assets).
    """
    if is_frozen():
        # sys.executable is inside the installation directory
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_app_bundle_dir() -> Path:
    """Return the directory containing bundled files (e.g. assets, default configs).

    In development: repository root.
    When frozen: sys._MEIPASS (PyInstaller temp unpack directory).
    """
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_user_data_dir() -> Path:
    """Return the writable user data directory for storage, cookies, and user configs.

    On Windows: %APPDATA%/TKS_Engine (e.g., C:/Users/<User>/AppData/Roaming/TKS_Engine)
    Fallback: ~/.tks_engine
    In development: can be overridden via TKS_DATA_DIR environment variable.
    """
    env_override = os.environ.get("TKS_DATA_DIR")
    if env_override:
        path = Path(env_override).resolve()
    elif os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            path = Path(app_data) / APP_NAME
        else:
            path = Path.home() / "AppData" / "Roaming" / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower()}"

    # If running in development without explicit override, allow running against repository
    # unless running tests or frozen.
    if not is_frozen() and not env_override and not os.environ.get("TKS_PORTABLE_MODE"):
        # In pure dev mode, if user is working inside the repo root and no APPDATA is forced:
        repo_root = Path(__file__).resolve().parent.parent
        # If repo has storage, allow dev mode to default to repo
        return repo_root

    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_config_path() -> Path:
    """Get the active writable config.json path.

    Copies default config from bundle if user config does not exist yet.
    """
    data_dir = get_user_data_dir()
    user_config = data_dir / "config.json"

    if not user_config.exists():
        default_config = get_app_bundle_dir() / "config.json"
        if default_config.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(default_config, user_config)
            except Exception:
                return default_config
        else:
            return user_config

    return user_config


def get_storage_dir(relative_name: str = "storage") -> Path:
    """Return writable storage directory."""
    path = get_user_data_dir() / relative_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cookies_dir(relative_name: str = "cookies") -> Path:
    """Return writable cookies directory."""
    path = get_user_data_dir() / relative_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    """Return writable logs directory."""
    path = get_storage_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_downloads_dir(relative_name: str = "downloads") -> Path:
    """Return writable downloads directory for cached Google Drive videos.

    Checks primary %APPDATA%/TKS_Engine/downloads, then storage/downloads.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        primary = Path(appdata) / APP_NAME / relative_name
        try:
            primary.mkdir(parents=True, exist_ok=True)
            return primary
        except Exception:
            pass

    path = get_storage_dir() / relative_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_playwright_environment() -> Path:
    """Configure PLAYWRIGHT_BROWSERS_PATH to find bundled or local Chromium.

    Priority:
    1. Existing PLAYWRIGHT_BROWSERS_PATH if already set
    2. 'browsers' directory next to the executable / app root
    3. Standard %LOCALAPPDATA%/ms-playwright
    """
    if "PLAYWRIGHT_BROWSERS_PATH" in os.environ and os.environ["PLAYWRIGHT_BROWSERS_PATH"]:
        return Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])

    # 1. Check next to executable (e.g. C:/Program Files/TKS Engine/browsers)
    install_browsers = get_app_install_dir() / "browsers"
    if install_browsers.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(install_browsers)
        return install_browsers

    # 2. Check bundled dir
    bundle_browsers = get_app_bundle_dir() / "browsers"
    if bundle_browsers.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundle_browsers)
        return bundle_browsers

    # 3. Default to %LOCALAPPDATA%/ms-playwright
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        standard_path = Path(local_app_data) / "ms-playwright"
    else:
        standard_path = Path.home() / "AppData" / "Local" / "ms-playwright"

    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(standard_path)
    return standard_path


def get_playwright_driver_executables() -> tuple[Path | None, Path | None]:
    """Find bundled or environment node.exe and cli.js for Playwright."""
    candidates = [
        get_app_bundle_dir() / "playwright" / "driver",
        get_app_install_dir() / "_internal" / "playwright" / "driver",
    ]
    for c in candidates:
        node = c / "node.exe"
        cli = c / "package" / "cli.js"
        if node.exists() and cli.exists():
            return node, cli

    # Fallback in Python development mode
    try:
        import playwright
        driver_dir = Path(playwright.__file__).parent / "driver"
        node = driver_dir / "node.exe"
        cli = driver_dir / "package" / "cli.js"
        if node.exists() and cli.exists():
            return node, cli
    except Exception:
        pass

    return None, None


def ensure_playwright_chromium(logger_fn=None) -> bool:
    """Verify Chromium is installed; if not, automatically install it using bundled driver."""
    browsers_dir = configure_playwright_environment()
    chromium_found = False

    search_dirs = [
        browsers_dir,
        Path.home() / "AppData" / "Local" / "ms-playwright",
        get_app_install_dir() / "browsers",
    ]
    for d in search_dirs:
        if d.exists():
            for exe in d.rglob("chrome.exe"):
                if exe.exists() and exe.is_file():
                    chromium_found = True
                    break
        if chromium_found:
            break

    if chromium_found:
        return True

    if logger_fn:
        logger_fn("Chromium não encontrado. Baixando e preparando navegador de automação...")

    node_exe, cli_js = get_playwright_driver_executables()
    if node_exe and cli_js:
        import subprocess
        try:
            res = subprocess.run(
                [str(node_exe), str(cli_js), "install", "chromium"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=240,
                text=True,
            )
            return res.returncode == 0
        except Exception:
            return False

    return False
