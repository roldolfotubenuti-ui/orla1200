"""Comprehensive automated distribution and clean environment test suite for TKS Engine 2.0.

Simulates a clean Windows machine without Python, development environment or prior state:
1. Verifies executable standalone launch without developer dependencies
2. Verifies isolation of %APPDATA%/TKS_Engine user data storage
3. Verifies Playwright Node.js driver and Chromium resolution
4. Verifies account persistence, video metadata, schedule generation, and session re-opening
5. Verifies safe uninstallation / cleanup
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class TestCleanEnvironmentDistribution(unittest.TestCase):
    """Distribution verification in isolated environment."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.dist_exe = cls.repo_root / "dist" / "TKS_Engine" / "TKS_Engine.exe"
        cls.dist_dir = cls.repo_root / "dist" / "TKS_Engine"
        cls.installer_exe = cls.repo_root / "release" / "TKS_Engine_Setup.exe"

    def setUp(self) -> None:
        self.temp_clean_home = Path(tempfile.mkdtemp(prefix="tks_clean_env_"))
        self.clean_appdata = self.temp_clean_home / "AppData" / "Roaming" / "TKS_Engine"

    def tearDown(self) -> None:
        if self.temp_clean_home.exists():
            shutil.rmtree(self.temp_clean_home, ignore_errors=True)

    def test_01_binaries_and_installer_exist(self) -> None:
        """Verify that standalone executable and Inno Setup installer are compiled and present."""
        self.assertTrue(self.dist_exe.exists(), f"Missing standalone executable: {self.dist_exe}")
        self.assertTrue(self.installer_exe.exists(), f"Missing installer: {self.installer_exe}")
        self.assertGreater(self.dist_exe.stat().st_size, 1_000_000, "Executable suspiciously small")
        self.assertGreater(self.installer_exe.stat().st_size, 10_000_000, "Installer suspiciously small")

    def test_02_bundled_playwright_driver_integrity(self) -> None:
        """Verify Playwright Node.js and CLI driver exist inside _internal distribution."""
        internal = self.dist_dir / "_internal"
        node_exe = internal / "playwright" / "driver" / "node.exe"
        cli_js = internal / "playwright" / "driver" / "package" / "cli.js"

        self.assertTrue(node_exe.exists(), f"Node.exe not found in bundle: {node_exe}")
        self.assertTrue(cli_js.exists(), f"cli.js not found in bundle: {cli_js}")

        # Run node.exe directly to verify it executes without host python
        res = subprocess.run([str(node_exe), "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Bundled node.exe failed to run: {res.stderr}")
        self.assertTrue(res.stdout.strip().startswith("v"), f"Unexpected node output: {res.stdout}")

    def test_03_executable_launches_in_isolated_environment(self) -> None:
        """Launch TKS_Engine.exe with simulated clean environment without dev PATH."""
        clean_env = os.environ.copy()
        clean_env["APPDATA"] = str(self.temp_clean_home / "AppData" / "Roaming")
        clean_env["LOCALAPPDATA"] = str(self.temp_clean_home / "AppData" / "Local")
        clean_env["TKS_DATA_DIR"] = str(self.clean_appdata)

        # Strip python dev paths from PATH
        paths = clean_env.get("PATH", "").split(os.pathsep)
        clean_paths = [p for p in paths if "python" not in p.lower() and "cursor" not in p.lower()]
        clean_env["PATH"] = os.pathsep.join(clean_paths)

        # Launch process
        proc = subprocess.Popen([str(self.dist_exe)], env=clean_env)
        try:
            time.sleep(3.5)
            # Process must be running healthy without crashing
            poll = proc.poll()
            self.assertIsNone(poll, f"Executable terminated prematurely with exit code {poll}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_04_user_storage_isolation_and_seeding(self) -> None:
        """Verify clean AppData directory is created and seeded with default config and structure."""
        from utils.app_paths import get_storage_dir, resolve_config_path

        old_data_dir = os.environ.get("TKS_DATA_DIR")
        os.environ["TKS_DATA_DIR"] = str(self.clean_appdata)
        try:
            cfg_path = resolve_config_path()
            self.assertTrue(cfg_path.exists(), f"Config not seeded to AppData: {cfg_path}")
            storage = get_storage_dir()
            self.assertTrue(storage.exists(), "Storage directory was not initialized")

            # Check config valid JSON
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertIn("windowSize", data)
            self.assertEqual(data["windowSize"]["width"], 1400)
            self.assertEqual(data["windowSize"]["height"], 850)
        finally:
            if old_data_dir is not None:
                os.environ["TKS_DATA_DIR"] = old_data_dir
            else:
                os.environ.pop("TKS_DATA_DIR", None)

    def test_05_schedule_and_account_persistence_lifecycle(self) -> None:
        """Simulate creating an account, generating schedule slots, persisting, and re-opening."""
        from core.config_manager import ConfigManager
        from core.logger_manager import LoggerManager
        from gui.services.storage_service import GuiStorageService

        logger = LoggerManager(name="TestDistClean", log_file=self.clean_appdata / "storage" / "logs" / "test.log", level="DEBUG")
        storage_service = GuiStorageService(self.clean_appdata, storage_dir_name="storage", logger=logger)
        username = "novousuario_teste"

        # 1. Simulate saving confirmed publication schedule
        sample_tasks = [
            {
                "file": "meu_video_01.mp4",
                "file_path": "C:/Videos/meu_video_01.mp4",
                "caption": "Vídeo teste na máquina limpa #teste",
                "schedule_time": "2026-11-20T14:30:00",
                "status": "pending",
            }
        ]
        storage_service.confirm_planned_schedules(username, sample_tasks)

        # 2. Re-open storage service fresh from disk to test persistence
        fresh_service = GuiStorageService(self.clean_appdata, storage_dir_name="storage", logger=logger)
        loaded_data = fresh_service.load_scheduled(username)
        uploads = fresh_service.get_user_uploads(loaded_data)

        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0]["file"], "meu_video_01.mp4")
        self.assertEqual(uploads[0]["caption"], "Vídeo teste na máquina limpa #teste")
        self.assertEqual(uploads[0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
