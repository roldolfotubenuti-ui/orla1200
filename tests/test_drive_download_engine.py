"""TKS ENGINE 3.0 — GOOGLE DRIVE DOWNLOAD ENGINE TEST SUITE
Testes Obrigatórios (Seção 12):
- Teste A — Download individual: Baixar um vídeo e verificar integridade.
- Teste B — Download paralelo: Baixar seis vídeos utilizando duas transferências simultâneas (MAX_CONCURRENT = 2).
- Teste C — Cache: Executar novamente e confirmar que vídeos íntegros não são baixados novamente.
- Teste D — Interrupção: Interromper um download e verificar recuperação via HTTP Range 206.
- Teste E — Arquivo incompleto: Simular download incompleto e confirmar que não entra na fila de publicação.
- Teste F — Duplicidade: Detectar o mesmo File ID duas vezes e impedir download duplicado.
- Teste G — Interface: Verificar progresso real, cálculo de velocidade e renderização visual ASCII.
- Teste H — Playwright: Confirmar que o Uploader/AccountExecutor utiliza o arquivo local sem fazer novo download.

ZERO PUBLICAÇÕES OU AGENDAMENTOS REAIS SÃO EXECUTADOS NESTA SUÍTE.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from core.account_executor import AccountExecutor
from core.account_manager import AccountManager
from core.browser_runtime import BrowserRuntime
from core.db_manager import DatabaseManager
from core.drive_cache import DriveCacheManager
from core.drive_downloader import (
    DEFAULT_CHUNK_SIZE,
    MAX_CONCURRENT_DRIVE_DOWNLOADS,
    DownloadErrorCode,
    DownloadProgress,
    DownloadStatus,
    GoogleDriveDownloader,
)
from core.drive_sync_coordinator import DriveSyncCoordinator, DriveVideoItem
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus, QueueManager
from core.uploader import UploadResult


class MockResponseContext:
    def __init__(self, resp: Any) -> None:
        self.resp = resp

    async def __aenter__(self) -> Any:
        return self.resp

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class TestDriveDownloadEngine(unittest.TestCase):
    """Comprehensive test suite for the optimized Google Drive download engine."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="tks_drive_test_")
        self.temp_path = Path(self.temp_dir)
        self.db_path = self.temp_path / "tks_jobs_drive_test.db"
        self.cache_dir = self.temp_path / "downloads"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db = DatabaseManager(self.db_path)
        self.queue = QueueManager(self.db)
        self.cache_mgr = DriveCacheManager(cache_dir=self.cache_dir)
        self.bridge = OfficeEventBridge.get_instance()
        self.downloader = GoogleDriveDownloader(
            cache_manager=self.cache_mgr,
            max_concurrent=MAX_CONCURRENT_DRIVE_DOWNLOADS,
            chunk_size=1024 * 64,  # 64 KB for fast test cycling
            dest_dir=self.cache_dir,
        )
        self.coordinator = DriveSyncCoordinator(
            db_manager=self.db,
            queue_manager=self.queue,
            cache_manager=self.cache_mgr,
            downloader=self.downloader,
            event_bridge=self.bridge,
            max_concurrent_downloads=MAX_CONCURRENT_DRIVE_DOWNLOADS,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _create_synthetic_payload(size_bytes: int = 1024 * 256) -> tuple[bytes, str]:
        """Generate synthetic binary data with known MD5."""
        data = os.urandom(size_bytes)
        md5 = hashlib.md5(data).hexdigest()
        return data, md5

    # --------------------------------------------------------------------------
    # TESTE A — Download individual e verificação de integridade
    # --------------------------------------------------------------------------
    def test_teste_a_individual_download_and_integrity(self) -> None:
        """Teste A: Baixar um vídeo via streaming e verificar integridade e MD5."""
        payload, expected_md5 = self._create_synthetic_payload(size_bytes=1024 * 512)
        file_id = "test_drive_file_01"

        async def run_test():
            # Mock aiohttp stream
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.content_type = "video/mp4"
            mock_resp.headers = {"Content-Length": str(len(payload))}

            # Stream chunks
            chunks = [payload[i : i + 65536] for i in range(0, len(payload), 65536)]
            chunk_iter = iter(chunks)

            async def mock_read(chunk_size):
                try:
                    return next(chunk_iter)
                except StopIteration:
                    return b""

            mock_resp.content.read = mock_read
            mock_ctx = MockResponseContext(mock_resp)

            with patch("aiohttp.ClientSession.get", return_value=mock_ctx):
                progress = await self.downloader.download_file(
                    file_id=file_id,
                    filename="sample_video_01.mp4",
                    dept_id="dept_instagram",
                    expected_size=len(payload),
                    expected_md5=expected_md5,
                )

            self.assertEqual(progress.status, DownloadStatus.COMPLETED)
            self.assertEqual(progress.downloaded_bytes, len(payload))
            self.assertTrue(Path(progress.local_path).exists())

            # Validate disk integrity
            computed_md5 = self.cache_mgr.compute_file_md5(Path(progress.local_path))
            self.assertEqual(computed_md5, expected_md5)
            self.assertFalse((self.cache_dir / f"{file_id}_sample_video_01.mp4.part").exists())

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # TESTE B — Download paralelo com concorrência estrita = 2
    # --------------------------------------------------------------------------
    def test_teste_b_parallel_download_concurrency_limit(self) -> None:
        """Teste B: Baixar 6 vídeos com concorrência máxima de 2 simultâneos."""
        active_peaks: list[int] = []
        current_active = 0
        lock = asyncio.Lock()

        async def run_test():
            nonlocal current_active
            items = []
            payloads = {}

            for idx in range(1, 7):
                fid = f"file_id_{idx:02d}"
                data, md5 = self._create_synthetic_payload(size_bytes=1024 * 128)
                payloads[fid] = (data, md5)
                items.append({
                    "file_id": fid,
                    "filename": f"batch_video_{idx:02d}.mp4",
                    "dept_id": f"dept_{idx:02d}",
                    "expected_size": len(data),
                    "expected_md5": md5,
                })

            def mock_get(url, *args, **kwargs):
                fid = "unknown"
                for k in payloads.keys():
                    if k in url:
                        fid = k
                        break
                data, _ = payloads.get(fid, (b"dummy", "md5"))

                mock_r = AsyncMock()
                mock_r.status = 200
                mock_r.content_type = "video/mp4"
                mock_r.headers = {"Content-Length": str(len(data))}
                chunks = [data[i : i + 65536] for i in range(0, len(data), 65536)]
                chunk_iter = iter(chunks)

                async def mock_read(sz):
                    await asyncio.sleep(0.01)
                    try:
                        return next(chunk_iter)
                    except StopIteration:
                        return b""

                mock_r.content.read = mock_read

                class TrackedContext:
                    async def __aenter__(ctx_self):
                        nonlocal current_active
                        async with lock:
                            current_active += 1
                            active_peaks.append(current_active)
                        return mock_r

                    async def __aexit__(ctx_self, exc_type, exc, tb):
                        nonlocal current_active
                        async with lock:
                            current_active -= 1
                        return None

                return TrackedContext()

            with patch("aiohttp.ClientSession.get", side_effect=mock_get):
                results = await self.downloader.download_batch(items)

            self.assertEqual(len(results), 6)
            for r in results:
                self.assertEqual(r.status, DownloadStatus.COMPLETED)
                self.assertTrue(Path(r.local_path).exists())

            # Verify that peak concurrency NEVER exceeded 2
            max_concurrency_reached = max(active_peaks) if active_peaks else 0
            self.assertLessEqual(max_concurrency_reached, 2, f"Concurrency exceeded 2: peak={max_concurrency_reached}")
            self.assertGreaterEqual(max_concurrency_reached, 2, "Concurrency should reach 2 under load")

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # TESTE C — Cache persistente (Zero download para arquivo íntegro)
    # --------------------------------------------------------------------------
    def test_teste_c_cache_prevents_redownload(self) -> None:
        """Teste C: Confirmar que arquivos em cache são reaproveitados instantaneamente."""
        payload, expected_md5 = self._create_synthetic_payload(size_bytes=1024 * 256)
        file_id = "cached_file_test_01"

        # Register existing file in cache manually
        cached_file = self.cache_dir / f"{file_id}_already_cached.mp4"
        with open(cached_file, "wb") as f:
            f.write(payload)

        self.cache_mgr.register_cached_file(
            file_id=file_id,
            local_path=cached_file,
            filename="already_cached.mp4",
            size_bytes=len(payload),
            md5_checksum=expected_md5,
        )

        async def run_test():
            download_called = False

            async def fail_if_called(*args, **kwargs):
                nonlocal download_called
                download_called = True
                raise RuntimeError("Network should NOT be accessed on cache hit!")

            with patch("aiohttp.ClientSession.get", side_effect=fail_if_called):
                progress = await self.downloader.download_file(
                    file_id=file_id,
                    filename="already_cached.mp4",
                    expected_size=len(payload),
                    expected_md5=expected_md5,
                )

            self.assertFalse(download_called, "Download network was called despite valid cache!")
            self.assertEqual(progress.status, DownloadStatus.CACHED)
            self.assertTrue(progress.is_cached)
            self.assertEqual(progress.local_path, str(cached_file))
            self.assertEqual(progress.percent, 100.0)

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # TESTE D — Interrupção e retomada resumível (HTTP Range 206)
    # --------------------------------------------------------------------------
    def test_teste_d_resumable_interrupted_download(self) -> None:
        """Teste D: Recuperar download interrompido via HTTP Range sem recomeçar do zero."""
        payload, expected_md5 = self._create_synthetic_payload(size_bytes=1024 * 256)
        file_id = "interrupted_file_01"
        clean_fn = "interrupted_video.mp4"

        # Stage half the file in .part
        half_len = len(payload) // 2
        part_file = self.cache_dir / f"{file_id}_{clean_fn}.part"
        with open(part_file, "wb") as f:
            f.write(payload[:half_len])

        async def run_test():
            requested_range = None

            def mock_get(url, headers=None, **kwargs):
                nonlocal requested_range
                headers = headers or {}
                requested_range = headers.get("Range")

                mock_r = AsyncMock()
                mock_r.status = 206
                mock_r.content_type = "video/mp4"
                mock_r.headers = {
                    "Content-Range": f"bytes {half_len}-{len(payload)-1}/{len(payload)}",
                    "Content-Length": str(len(payload) - half_len),
                }

                # Second half only
                remaining_data = payload[half_len:]
                chunks = [remaining_data]
                chunk_iter = iter(chunks)

                async def mock_read(sz):
                    try:
                        return next(chunk_iter)
                    except StopIteration:
                        return b""

                mock_r.content.read = mock_read
                return MockResponseContext(mock_r)

            with patch("aiohttp.ClientSession.get", side_effect=mock_get):
                progress = await self.downloader.download_file(
                    file_id=file_id,
                    filename=clean_fn,
                    expected_size=len(payload),
                    expected_md5=expected_md5,
                )

            self.assertEqual(requested_range, f"bytes={half_len}-")
            self.assertEqual(progress.status, DownloadStatus.COMPLETED)
            final_path = Path(progress.local_path)
            self.assertTrue(final_path.exists())
            self.assertEqual(final_path.stat().st_size, len(payload))
            self.assertEqual(self.cache_mgr.compute_file_md5(final_path), expected_md5)

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # TESTE E — Arquivo incompleto não entra na fila de publicação
    # --------------------------------------------------------------------------
    def test_teste_e_incomplete_file_blocked_from_publishing(self) -> None:
        """Teste E: Simular download incompleto e confirmar que NÃO entra em READY_FOR_UPLOAD."""
        file_id = "failing_incomplete_file"

        async def run_test():
            # Mock returns fewer bytes than expected
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.content_type = "video/mp4"
            mock_resp.headers = {"Content-Length": "500000"}  # Claims 500 KB

            async def truncated_read(sz):
                return b""  # Returns 0 bytes

            mock_resp.content.read = truncated_read
            mock_ctx = MockResponseContext(mock_resp)

            items = [
                DriveVideoItem(
                    dept_id="dept_instagram",
                    file_id=file_id,
                    filename="incomplete.mp4",
                    expected_size=500000,
                )
            ]

            with patch("aiohttp.ClientSession.get", return_value=mock_ctx):
                ready_jobs = await self.coordinator.ingest_drive_videos(items)

            # Incomplete job must NOT be in ready_jobs
            self.assertEqual(len(ready_jobs), 0)

            # Check database status
            conn = self.db.get_connection()
            job_row = conn.execute("SELECT * FROM jobs WHERE drive_file_id = ?;", (file_id,)).fetchone()
            self.assertIsNotNone(job_row)
            self.assertEqual(job_row["status"], JobStatus.DOWNLOAD_FAILED.value)
            self.assertEqual(job_row["error_code"], DownloadErrorCode.INCOMPLETE.value)

            # Ensure get_pending_jobs does NOT return this job
            pending = self.queue.get_pending_jobs(department_id="dept_instagram")
            self.assertFalse(any(j.drive_file_id == file_id for j in pending))

        asyncio.run(run_test())

    # --------------------------------------------------------------------------
    # TESTE F — Duplicidade de File ID prevenida (Idempotência)
    # --------------------------------------------------------------------------
    def test_teste_f_idempotency_prevents_duplicate_download(self) -> None:
        """Teste F: Detectar o mesmo File ID duas vezes e impedir download duplicado."""
        file_id = "duplicate_prevention_file"

        job1, is_new1 = self.queue.enqueue_job(
            department_id="dept_shorts",
            filename="unique_video.mp4",
            drive_file_id=file_id,
            account_id="acc_test_01",
        )
        self.assertTrue(is_new1)

        # Attempt to enqueue again with same drive_file_id
        job2, is_new2 = self.queue.enqueue_job(
            department_id="dept_shorts",
            filename="unique_video.mp4",
            drive_file_id=file_id,
            account_id="acc_test_01",
        )
        self.assertFalse(is_new2)
        self.assertEqual(job1.id, job2.id)

        # Confirm count in SQLite is exactly 1
        conn = self.db.get_connection()
        count = conn.execute("SELECT COUNT(*) as c FROM jobs WHERE drive_file_id = ?;", (file_id,)).fetchone()["c"]
        self.assertEqual(count, 1)

    # --------------------------------------------------------------------------
    # TESTE G — Progresso real e visualização ASCII
    # --------------------------------------------------------------------------
    def test_teste_g_real_progress_and_ascii_rendering(self) -> None:
        """Teste G: Validação de telemetria, cálculo de velocidade e renderização ASCII."""
        progress_items = [
            DownloadProgress(
                file_id="fid_1",
                filename="vid1.mp4",
                dept_id="dept_instagram",
                status=DownloadStatus.COMPLETED,
                total_bytes=10000000,
                downloaded_bytes=10000000,
                percent=100.0,
                speed_mbps=8.5,
            ),
            DownloadProgress(
                file_id="fid_2",
                filename="vid2.mp4",
                dept_id="dept_mercadolivre",
                status=DownloadStatus.DOWNLOADING,
                total_bytes=10000000,
                downloaded_bytes=5500000,
                percent=55.0,
                speed_mbps=5.2,
                eta_seconds=0.8,
            ),
            DownloadProgress(
                file_id="fid_3",
                filename="vid3.mp4",
                dept_id="dept_shorts",
                status=DownloadStatus.QUEUED,
                total_bytes=10000000,
            ),
            DownloadProgress(
                file_id="fid_4",
                filename="vid4.mp4",
                dept_id="dept_tiktok",
                status=DownloadStatus.CACHED,
                total_bytes=10000000,
                downloaded_bytes=10000000,
                percent=100.0,
                is_cached=True,
            ),
        ]

        rendered = GoogleDriveDownloader.render_ascii_progress(progress_items)
        self.assertIn("DOWNLOAD DOS VÍDEOS — GOOGLE DRIVE", rendered)
        self.assertIn("CONCLUÍDO", rendered)
        self.assertIn("BAIXANDO (5.2 MB/s)", rendered)
        self.assertIn("AGUARDANDO", rendered)
        self.assertIn("CACHE", rendered)
        self.assertIn("CONCORRÊNCIA ATIVA: 1/2", rendered)

    # --------------------------------------------------------------------------
    # TESTE H — Playwright Uploader recebe diretamente o arquivo local
    # --------------------------------------------------------------------------
    def test_teste_h_playwright_uploader_receives_local_path(self) -> None:
        """Teste H: Confirmar que o AccountExecutor passa o caminho local diretamente sem re-download."""
        local_video = self.temp_path / "valid_local_video.mp4"
        local_video.write_bytes(b"0" * 1024)

        job = JobRecord(
            id="job_playwright_test",
            department_id="dept_instagram",
            account_id="acc_dummy_id",
            drive_file_id="drive_file_123",
            filename="valid_local_video.mp4",
            file_path=str(local_video),
            status=JobStatus.READY_FOR_UPLOAD.value,
        )

        # Mock Uploader Factory
        mock_uploader = AsyncMock()
        mock_uploader.upload_video = AsyncMock(return_value=UploadResult(
            success=True,
            file_path=local_video,
            message="Upload successful",
            timestamp=None,
        ))

        mock_acc_mgr = MagicMock()
        mock_acc = MagicMock()
        mock_acc.auth_status = "VALID"
        mock_acc.username = "testuser"
        mock_acc_mgr.get_account.return_value = mock_acc

        mock_runtime = AsyncMock()
        mock_context = AsyncMock()
        mock_context.cookies = AsyncMock(return_value=[{"name": "sessionid", "value": "123"}])
        mock_page = MagicMock()
        mock_page.url = "https://www.tiktok.com/tiktokstudio/upload?from=webapp"
        mock_runtime.get_or_create_account_session = AsyncMock(return_value=(mock_context, mock_page))

        executor = AccountExecutor(
            browser_runtime=mock_runtime,
            account_manager=mock_acc_mgr,
            office_bridge=self.bridge,
            uploader_factory=lambda page, dry_run=False: mock_uploader,
        )

        async def run_test():
            result = await executor.execute_task(job, dry_run=False)
            self.assertTrue(result.success)
            # Confirm that the upload task received the exact file path on disk
            mock_uploader.upload_video.assert_called_once()
            call_kwargs = mock_uploader.upload_video.call_args[1]
            call_task = call_kwargs.get("task") or mock_uploader.upload_video.call_args[0][0]
            self.assertEqual(str(call_task.file_path), str(local_video))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
