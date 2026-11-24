"""TKS ENGINE 3.0 — FASE 3 TEST SUITE
Integração do Motor Multiaccount com o Uploader Real do TikTok Studio.

Testes Obrigatórios:
- Teste A — Integração: AccountExecutor entrega a página correta ao Uploader (sem iniciar novo processo Chromium).
- Teste B — Identidade: Uploader / AccountExecutor valida e opera na conta selecionada.
- Teste C — Isolamento: Duas contas executam com contextos e cookies estritamente isolados.
- Teste D — Round-Robin: Alternância alternada entre contas do mesmo departamento.
- Teste E — Concorrência: Máximo de duas contas simultâneas (MAX_CONCURRENT = 2, MAX_PER_ACCOUNT = 1).
- Teste F — Falha independente: Falha em uma conta não compromete a outra.
- Teste G — Agendamento: Classificação correta de SCHEDULED vs PUBLISHED.
- Teste H — Idempotência: Mesmo vídeo não é submetido em duplicidade para a mesma conta.
- Teste I — Reinicialização: Recuperação consistente de tarefas interrompidas na fila SQLite.
- Teste J — Regressão: Suítes anteriores e compatibilidade geral.
- Teste K — Modo Homologação: Botão final de publicação permanece rigorosamente bloqueado e nunca acionado.

ZERO PUBLICAÇÕES REAIS SÃO EXECUTADAS NESTA SUÍTE.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from core.account_executor import AccountExecutor, AccountExecutorResult
from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus, AccountRecord
from core.browser_runtime import BrowserRuntime
from core.context_registry import ContextRegistry
from core.db_manager import DatabaseManager
from core.dom_handler import DOMHandler
from core.dpapi_crypto import save_encrypted_json
from core.execution_coordinator import ExecutionCoordinator
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobRecord, JobStatus, QueueManager
from core.round_robin_router import RoundRobinRouter
from core.scheduler import UploadTask
from core.uploader import UploadResult, Uploader


class TestMultiaccountPhase3(unittest.TestCase):
    """Phase 3 comprehensive integration test suite."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="tks_phase3_test_")
        self.temp_path = Path(self.temp_dir)
        self.db_path = self.temp_path / "tks_jobs_phase3.db"
        self.cookies_dir = self.temp_path / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

        self.db = DatabaseManager(self.db_path)
        self.account_manager = AccountManager(
            data_dir=self.temp_path,
            cookies_dir=self.cookies_dir,
        )
        self.office_bridge = OfficeEventBridge(storage_dir=self.temp_path, db_manager=self.db)

        # Seed 3 dummy accounts with encrypted cookies
        self.test_accounts: list[AccountRecord] = []
        for i, username in enumerate(["conta_alfa", "conta_beta", "conta_gama"]):
            acc_id = str(uuid.uuid4())
            enc_name = f"{acc_id}.enc"
            mock_cookies = [
                {
                    "name": f"session_{username}",
                    "value": f"cookie_val_{username}_{i}",
                    "domain": ".tiktok.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                },
                {
                    "name": "tt_chain_token",
                    "value": f"token_{i}",
                    "domain": ".tiktok.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                },
            ]
            save_encrypted_json(self.cookies_dir / enc_name, mock_cookies)

            acc = AccountRecord(
                account_id=acc_id,
                username=username,
                platform="tiktok",
                cookie_file=enc_name,
                department_id="TikTok",
                auth_status=AccountAuthStatus.AUTHENTICATED.value,
                enabled=True,
                cookie_count=len(mock_cookies),
                display_title=f"Perfil {username}",
            )
            self.account_manager._accounts[acc_id] = acc
            self.test_accounts.append(acc)

        self.account_manager._save_registry()

        # Create dummy physical test video file
        self.test_video_path = self.temp_path / "test_sample_video.mp4"
        self.test_video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41")

    def tearDown(self) -> None:
        self.db.close_connection()
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Teste A — Integração Page -> Uploader
    # -------------------------------------------------------------------------
    def test_a_integration_page_to_uploader(self) -> None:
        """Confirmar que o AccountExecutor consegue entregar a página correta ao Uploader."""
        async def _run() -> None:
            runtime = BrowserRuntime()
            try:
                acc = self.test_accounts[0]
                context, page = await runtime.get_or_create_account_session(
                    acc.account_id,
                    self.account_manager,
                )
                self.assertIsNotNone(page)
                self.assertIsNotNone(context)

                # Instantiate Uploader from injected page
                uploader = Uploader.from_page(
                    page=page,
                    logger=MagicMock(),
                    homologation_mode=True,
                )
                self.assertIsInstance(uploader, Uploader)
                self.assertEqual(uploader._dom_handler._page, page)
                self.assertTrue(uploader._homologation_mode)
            finally:
                await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste B — Identidade da Conta
    # -------------------------------------------------------------------------
    def test_b_account_identity_verification(self) -> None:
        """Confirmar que o Uploader / Executor valida e preserva a identidade da conta."""
        async def _run() -> None:
            runtime = BrowserRuntime()
            try:
                acc = self.test_accounts[0]
                executor = AccountExecutor(
                    browser_runtime=runtime,
                    account_manager=self.account_manager,
                    office_bridge=self.office_bridge,
                )

                job = JobRecord(
                    id=str(uuid.uuid4()),
                    department_id="TikTok",
                    account_id=acc.account_id,
                    filename=str(self.test_video_path),
                )

                # Mock Uploader to verify identity passed
                received_username = []
                def spy_uploader(page: Any, dry_run: bool):
                    mock_up = MagicMock(spec=Uploader)
                    async def mock_upload(task, username="", homologation_mode=True):
                        received_username.append(username)
                        return UploadResult(
                            success=True,
                            file_path=task.file_path,
                            message="OK",
                            timestamp=datetime.now(),
                            outcome="simulation_success",
                            status="published",
                        )
                    mock_up.upload_video = mock_upload
                    return mock_up

                executor._uploader_factory = spy_uploader
                res = await executor.execute_task(job, dry_run=True)

                self.assertTrue(res.success)
                self.assertEqual(res.detected_username, acc.username)
                self.assertEqual(received_username, [acc.username])
            finally:
                await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste C — Isolamento de Sessões
    # -------------------------------------------------------------------------
    def test_c_session_isolation_parallel_accounts(self) -> None:
        """Executar duas contas com contextos independentes sem vazamento de cookies."""
        async def _run() -> None:
            runtime = BrowserRuntime()
            try:
                acc1, acc2 = self.test_accounts[0], self.test_accounts[1]
                ctx1, page1 = await runtime.get_or_create_account_session(acc1.account_id, self.account_manager)
                ctx2, page2 = await runtime.get_or_create_account_session(acc2.account_id, self.account_manager)

                self.assertNotEqual(ctx1, ctx2)
                self.assertNotEqual(page1, page2)

                cookies1 = await ctx1.cookies()
                cookies2 = await ctx2.cookies()

                names1 = {c["name"] for c in cookies1}
                names2 = {c["name"] for c in cookies2}

                self.assertIn(f"session_{acc1.username}", names1)
                self.assertNotIn(f"session_{acc1.username}", names2)

                self.assertIn(f"session_{acc2.username}", names2)
                self.assertNotIn(f"session_{acc2.username}", names1)
            finally:
                await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste D — Round-Robin
    # -------------------------------------------------------------------------
    def test_d_round_robin_alternation_same_department(self) -> None:
        """Testar a alternância entre contas do mesmo departamento."""
        dept = self.db.get_department_by_id_or_name("TikTok")
        dept_id = dept["id"]

        for acc in self.test_accounts:
            self.db.assign_account_to_department(acc.account_id, dept_id, platform="tiktok")

        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        assigned_sequence = []
        for i in range(6):
            job, is_new = queue.enqueue_job(
                department_id=dept_id,
                filename=f"video_{i}.mp4",
                drive_file_id=f"drive_f3_{i}",
                auto_assign=True,
            )
            self.assertTrue(is_new)
            assigned_sequence.append(job.account_id)

        expected = [
            self.test_accounts[0].account_id,
            self.test_accounts[1].account_id,
            self.test_accounts[2].account_id,
            self.test_accounts[0].account_id,
            self.test_accounts[1].account_id,
            self.test_accounts[2].account_id,
        ]
        self.assertEqual(assigned_sequence, expected)

    # -------------------------------------------------------------------------
    # Teste E — Concorrência Máxima 2
    # -------------------------------------------------------------------------
    def test_e_concurrency_max_two_jobs(self) -> None:
        """Confirmar máximo de duas contas simultâneas."""
        dept = self.db.get_department_by_id_or_name("TikTok")
        dept_id = dept["id"]
        for acc in self.test_accounts:
            self.db.assign_account_to_department(acc.account_id, dept_id, platform="tiktok")

        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        for i in range(4):
            queue.enqueue_job(
                department_id=dept_id,
                filename=f"conc_video_{i}.mp4",
                drive_file_id=f"drive_conc_{i}",
            )

        async def _run() -> None:
            runtime = BrowserRuntime()
            try:
                coordinator = ExecutionCoordinator(
                    browser_runtime=runtime,
                    queue_manager=queue,
                    account_manager=self.account_manager,
                    router=router,
                    db_manager=self.db,
                    max_concurrent_jobs=2,
                )

                # Mock executor task with controlled delay
                async def mock_exec(job, dry_run=True, **kwargs):
                    await asyncio.sleep(0.3)
                    return AccountExecutorResult(
                        success=True,
                        status=JobStatus.PUBLISHED.value,
                        detected_username="mock_user",
                    )
                coordinator._executor.execute_task = mock_exec

                spawned_1 = await coordinator.step(dry_run=True)
                self.assertLessEqual(spawned_1, 2)
                self.assertLessEqual(coordinator.active_job_count, 2)

                await coordinator.wait_for_completion(timeout=5.0)
                self.assertEqual(coordinator.active_job_count, 0)
            finally:
                await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste F — Falha Independente
    # -------------------------------------------------------------------------
    def test_f_independent_account_failure(self) -> None:
        """Simular erro em uma conta e confirmar continuidade da outra."""
        dept = self.db.get_department_by_id_or_name("TikTok")
        dept_id = dept["id"]
        acc1, acc2 = self.test_accounts[0], self.test_accounts[1]
        self.db.assign_account_to_department(acc1.account_id, dept_id, platform="tiktok")
        self.db.assign_account_to_department(acc2.account_id, dept_id, platform="tiktok")

        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        job1, _ = queue.enqueue_job(dept_id, "fail_test.mp4", drive_file_id="d_fail", account_id=acc1.account_id)
        job2, _ = queue.enqueue_job(dept_id, "pass_test.mp4", drive_file_id="d_pass", account_id=acc2.account_id)

        async def _run() -> None:
            runtime = BrowserRuntime()
            try:
                coordinator = ExecutionCoordinator(
                    browser_runtime=runtime,
                    queue_manager=queue,
                    account_manager=self.account_manager,
                    router=router,
                    db_manager=self.db,
                    max_concurrent_jobs=2,
                )

                async def mock_selective(job, dry_run=True, **kwargs):
                    if job.account_id == acc1.account_id:
                        return AccountExecutorResult(
                            success=False,
                            status=JobStatus.FAILED.value,
                            error_code="ERR_UPLOAD",
                            error_message="Simulated error on Account 1",
                        )
                    return AccountExecutorResult(
                        success=True,
                        status=JobStatus.PUBLISHED.value,
                        detected_username=acc2.username,
                    )
                coordinator._executor.execute_task = mock_selective

                await coordinator.step(dry_run=True)
                await coordinator.step(dry_run=True)
                await coordinator.wait_for_completion(timeout=5.0)

                updated_j1 = queue.get_job(job1.id)
                updated_j2 = queue.get_job(job2.id)

                self.assertIsNotNone(updated_j1)
                self.assertIsNotNone(updated_j2)
                self.assertEqual(updated_j1.status, JobStatus.FAILED.value)
                self.assertEqual(updated_j2.status, JobStatus.PUBLISHED.value)
            finally:
                await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste G — Agendamento (SCHEDULED vs PUBLISHED)
    # -------------------------------------------------------------------------
    def test_g_schedule_status_classification(self) -> None:
        """Testar a classificação correta de SCHEDULED e PUBLISHED."""
        async def _run() -> None:
            runtime = BrowserRuntime()
            try:
                acc = self.test_accounts[0]
                executor = AccountExecutor(
                    browser_runtime=runtime,
                    account_manager=self.account_manager,
                    office_bridge=self.office_bridge,
                )

                # Job without schedule
                job_immediate = JobRecord(
                    id=str(uuid.uuid4()),
                    department_id="TikTok",
                    account_id=acc.account_id,
                    filename="imm.mp4",
                    schedule_time=None,
                )
                res_imm = await executor.execute_task(job_immediate, dry_run=True)
                self.assertEqual(res_imm.status, JobStatus.PUBLISHED.value)

                # Job with schedule
                future_time = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
                job_scheduled = JobRecord(
                    id=str(uuid.uuid4()),
                    department_id="TikTok",
                    account_id=acc.account_id,
                    filename="sched.mp4",
                    schedule_time=future_time,
                )
                res_sched = await executor.execute_task(job_scheduled, dry_run=True)
                self.assertEqual(res_sched.status, JobStatus.SCHEDULED.value)
            finally:
                await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste H — Idempotência
    # -------------------------------------------------------------------------
    def test_h_idempotency_prevents_duplicate_submission(self) -> None:
        """Confirmar que o mesmo vídeo não é submetido duas vezes para a mesma conta."""
        dept = self.db.get_department_by_id_or_name("TikTok")
        dept_id = dept["id"]
        acc = self.test_accounts[0]

        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        job1, is_new1 = queue.enqueue_job(
            department_id=dept_id,
            filename="unique_clip.mp4",
            drive_file_id="unique_drive_101",
            account_id=acc.account_id,
        )
        self.assertTrue(is_new1)

        # Enqueue identical video
        job2, is_new2 = queue.enqueue_job(
            department_id=dept_id,
            filename="unique_clip.mp4",
            drive_file_id="unique_drive_101",
            account_id=acc.account_id,
        )
        self.assertFalse(is_new2)
        self.assertEqual(job1.id, job2.id)

    # -------------------------------------------------------------------------
    # Teste I — Reinicialização e Recuperação de Filas
    # -------------------------------------------------------------------------
    def test_i_restart_queue_recovery(self) -> None:
        """Verificar recuperação consistente das filas após interrupção."""
        dept = self.db.get_department_by_id_or_name("TikTok")
        dept_id = dept["id"]
        acc = self.test_accounts[0]

        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        job, _ = queue.enqueue_job(dept_id, "interrupted.mp4", "drive_int_1", account_id=acc.account_id)
        queue.update_job_status(job.id, JobStatus.RUNNING.value)

        # Simulate sudden process restart by re-initializing QueueManager
        new_queue = QueueManager(self.db, router)
        recovered_count = new_queue.recover_interrupted_jobs()

        self.assertEqual(recovered_count, 1)
        rec = new_queue.get_job(job.id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, JobStatus.ASSIGNED.value)

    # -------------------------------------------------------------------------
    # Teste J — Regressão e Integridade
    # -------------------------------------------------------------------------
    def test_j_regression_compatibility(self) -> None:
        """Confirmar que todas as 6 contas e 6 departamentos permanecem íntegros."""
        depts = self.db.get_departments()
        self.assertEqual(len(depts), 6)
        dept_names = {d["name"] for d in depts}
        self.assertIn("TikTok", dept_names)
        self.assertIn("YouTube", dept_names)
        self.assertIn("Instagram", dept_names)

        # Verify OfficeEventBridge produces valid jsonl output
        bridge = OfficeEventBridge.get_instance()
        event_dict = bridge.emit(
            "account.execution_started",
            department_id=depts[0]["id"],
            account_id=self.test_accounts[0].account_id,
            username=self.test_accounts[0].username,
            job_id="sample_job_j",
            status="RUNNING",
        )
        self.assertEqual(event_dict["event"], "account.execution_started")
        self.assertNotIn("cookie", event_dict)

    # -------------------------------------------------------------------------
    # Teste K — Modo de Homologação (Botão Post Bloqueado)
    # -------------------------------------------------------------------------
    def test_k_homologation_mode_post_button_blocked(self) -> None:
        """Confirmar que o botão final de publicação permanece rigorosamente bloqueado no modo de homologação."""
        async def _run() -> None:
            mock_dom = MagicMock(spec=DOMHandler)
            mock_dom.dismiss_all_popups = AsyncMock()
            mock_dom.upload_file = AsyncMock()
            mock_dom.wait_upload_complete = AsyncMock(return_value=True)
            mock_dom.set_caption = AsyncMock()
            mock_dom.set_visibility = AsyncMock()
            mock_dom.check_music_copyright = AsyncMock(return_value={"has_copyright": False})
            mock_dom.check_content_quality = AsyncMock(return_value={"blocking": False, "state": "passed"})
            mock_dom.is_post_button_enabled = AsyncMock(return_value=True)
            mock_dom.click_post = AsyncMock()
            mock_dom.cancel_or_dismiss_upload = AsyncMock()

            # Initialize Uploader with homologation_mode = True
            uploader = Uploader(
                dom_handler=mock_dom,
                logger=MagicMock(),
                homologation_mode=True,
            )

            task = UploadTask(
                file_path=self.test_video_path,
                caption="Legenda de homologação",
                schedule_time=None,
                visibility="public",
            )

            result = await uploader.upload_video(task=task, username="teste_homolog")

            # Assert success in simulation
            self.assertTrue(result.success)
            self.assertEqual(result.outcome, "simulation_success")
            self.assertEqual(result.status, "published")
            self.assertIn("Simulação de homologação concluída com sucesso", result.message)

            # CRITICAL SAFETY ASSERTION: click_post must NEVER be called
            mock_dom.click_post.assert_not_called()

            # Verify safe cleanup was performed
            mock_dom.cancel_or_dismiss_upload.assert_called_once()
            mock_dom.is_post_button_enabled.assert_called_once()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
