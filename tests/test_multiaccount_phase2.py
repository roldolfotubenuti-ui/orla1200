"""TKS ENGINE 3.0 — FASE 2 TEST SUITE
BrowserRuntime, SQLite, Round-Robin & Controlled Parallel Execution.

Covers mandatory Tests A through J:
- Teste A: BrowserRuntime — Single Chromium, 2 independent contexts.
- Teste B: Isolamento — 2 accounts, separated cookies and storage.
- Teste C: Round-Robin — 3 accounts in 1 department across 6 videos (A, B, C, A, B, C).
- Teste D: Persistência — Cursor preserved across restarts.
- Teste E: Conta indisponível — Disabled account skipped in rotation.
- Teste F: Concorrência — Maximum 2 concurrent account jobs.
- Teste G: Exclusividade por conta — Exactly 1 active job per account.
- Teste H: Falhas independentes — Failure in one account does not cancel another.
- Teste I: Idempotência — Re-detecting same drive file avoids duplicate jobs.
- Teste J: Reinicialização — Interrupted job recovery state machine.

NO REAL UPLOADS OR POSTS ARE EXECUTED IN THIS TEST SUITE.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any

from core.account_executor import AccountExecutor
from core.account_manager import AccountManager
from core.account_model import AccountAuthStatus, AccountRecord
from core.browser_runtime import BrowserRuntime
from core.context_registry import ContextRegistry
from core.db_manager import DatabaseManager
from core.dpapi_crypto import save_encrypted_json
from core.execution_coordinator import ExecutionCoordinator
from core.queue_manager import JobRecord, JobStatus, QueueManager
from core.round_robin_router import RoundRobinRouter


class TestMultiaccountPhase2(unittest.TestCase):
    """Phase 2 verification suite."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="tks_phase2_test_")
        self.temp_path = Path(self.temp_dir)
        self.db_path = self.temp_path / "tks_jobs_test.db"
        self.cookies_dir = self.temp_path / "cookies"
        self.cookies_dir.mkdir(parents=True, exist_ok=True)

        self.db = DatabaseManager(self.db_path)
        self.account_manager = AccountManager(
            data_dir=self.temp_path,
            cookies_dir=self.cookies_dir,
        )

        # Seed 3 dummy accounts with encrypted cookie payloads
        self.test_accounts: list[AccountRecord] = []
        for i, username in enumerate(["alfa_user", "beta_user", "gama_user"]):
            acc_id = str(uuid.uuid4())
            enc_name = f"{acc_id}.enc"
            mock_cookies = [
                {
                    "name": f"session_{username}",
                    "value": f"val_{username}_{i}",
                    "domain": ".tiktok.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                },
                {
                    "name": "tt_chain_token",
                    "value": f"tok_{i}",
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
                department_id="Instagram",
                auth_status=AccountAuthStatus.AUTHENTICATED.value,
                enabled=True,
                cookie_count=len(mock_cookies),
                display_title=f"Conta {username}",
            )
            self.account_manager._accounts[acc_id] = acc
            self.test_accounts.append(acc)

        self.account_manager._save_registry()

    def tearDown(self) -> None:
        self.db.close_connection()
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Teste A — BrowserRuntime
    # -------------------------------------------------------------------------
    def test_a_browser_runtime_two_contexts(self) -> None:
        """Inicializar um único Chromium e criar dois contextos independentes operando simultaneamente."""
        async def _run() -> None:
            runtime = BrowserRuntime()
            browser = await runtime.start(headless=True)
            self.assertTrue(runtime.is_alive())

            acc_a, acc_b = self.test_accounts[0], self.test_accounts[1]
            ctx_a, page_a = await runtime.get_or_create_account_session(acc_a.account_id, self.account_manager)
            ctx_b, page_b = await runtime.get_or_create_account_session(acc_b.account_id, self.account_manager)

            self.assertNotEqual(ctx_a, ctx_b)
            self.assertNotEqual(page_a, page_b)
            self.assertTrue(runtime.context_registry.is_context_active(acc_a.account_id))
            self.assertTrue(runtime.context_registry.is_context_active(acc_b.account_id))

            # Both pages can execute scripts simultaneously
            res_a = await page_a.evaluate("() => 10 + 20")
            res_b = await page_b.evaluate("() => 50 + 50")
            self.assertEqual(res_a, 30)
            self.assertEqual(res_b, 100)

            await runtime.stop()
            self.assertFalse(runtime.is_alive())

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste B — Isolamento
    # -------------------------------------------------------------------------
    def test_b_context_isolation_separate_accounts(self) -> None:
        """Confirmar que cada contexto identifica exclusivamente sua conta e não compartilha cookies."""
        async def _run() -> None:
            runtime = BrowserRuntime()
            await runtime.start(headless=True)

            acc_a, acc_b = self.test_accounts[0], self.test_accounts[1]
            ctx_a, _ = await runtime.get_or_create_account_session(acc_a.account_id, self.account_manager)
            ctx_b, _ = await runtime.get_or_create_account_session(acc_b.account_id, self.account_manager)

            cookies_a = await ctx_a.cookies()
            cookies_b = await ctx_b.cookies()

            names_a = {c["name"] for c in cookies_a}
            names_b = {c["name"] for c in cookies_b}

            self.assertIn(f"session_{acc_a.username}", names_a)
            self.assertNotIn(f"session_{acc_b.username}", names_a)

            self.assertIn(f"session_{acc_b.username}", names_b)
            self.assertNotIn(f"session_{acc_a.username}", names_b)

            await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste C — Round-Robin
    # -------------------------------------------------------------------------
    def test_c_round_robin_three_accounts_six_videos(self) -> None:
        """3 contas no mesmo departamento: Vídeo 01->A, 02->B, 03->C, 04->A, 05->B, 06->C."""
        dept = "Instagram"
        acc_a, acc_b, acc_c = self.test_accounts[0], self.test_accounts[1], self.test_accounts[2]

        self.db.assign_account_to_department(acc_a.account_id, dept, order=0)
        self.db.assign_account_to_department(acc_b.account_id, dept, order=1)
        self.db.assign_account_to_department(acc_c.account_id, dept, order=2)

        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        expected_sequence = [
            acc_a.account_id,
            acc_b.account_id,
            acc_c.account_id,
            acc_a.account_id,
            acc_b.account_id,
            acc_c.account_id,
        ]

        actual_sequence = []
        for i in range(6):
            job, is_new = queue.enqueue_job(
                department_id=dept,
                filename=f"video_{i+1:02d}.mp4",
                drive_file_id=f"drive_c_{i+1}",
            )
            self.assertTrue(is_new)
            actual_sequence.append(job.account_id)

        self.assertEqual(actual_sequence, expected_sequence)

    # -------------------------------------------------------------------------
    # Teste D — Persistência
    # -------------------------------------------------------------------------
    def test_d_cursor_persistence_after_restart(self) -> None:
        """Confirmar que após reiniciar a conexão SQLite o próximo destino permanece correto."""
        dept = "Instagram"
        acc_a, acc_b, acc_c = self.test_accounts[0], self.test_accounts[1], self.test_accounts[2]

        self.db.assign_account_to_department(acc_a.account_id, dept, order=0)
        self.db.assign_account_to_department(acc_b.account_id, dept, order=1)
        self.db.assign_account_to_department(acc_c.account_id, dept, order=2)

        router1 = RoundRobinRouter(self.db, self.account_manager)
        sel1 = router1.select_next_account(dept)
        sel2 = router1.select_next_account(dept)

        self.assertEqual(sel1, acc_a.account_id)
        self.assertEqual(sel2, acc_b.account_id)

        # Simulate full application restart: close connection and create fresh instances
        self.db.close_connection()
        restarted_db = DatabaseManager(self.db_path)
        restarted_router = RoundRobinRouter(restarted_db, self.account_manager)

        # Next selection must pick C, and then wrap around to A
        sel3 = restarted_router.select_next_account(dept)
        sel4 = restarted_router.select_next_account(dept)

        self.assertEqual(sel3, acc_c.account_id)
        self.assertEqual(sel4, acc_a.account_id)
        restarted_db.close_connection()

    # -------------------------------------------------------------------------
    # Teste E — Conta indisponível
    # -------------------------------------------------------------------------
    def test_e_disabled_account_skipped_in_rotation(self) -> None:
        """Desativar uma conta e confirmar que ela não recebe tarefas e a rotação continua entre as elegíveis."""
        dept = "Instagram"
        acc_a, acc_b, acc_c = self.test_accounts[0], self.test_accounts[1], self.test_accounts[2]

        self.db.assign_account_to_department(acc_a.account_id, dept, order=0)
        self.db.assign_account_to_department(acc_b.account_id, dept, order=1)
        self.db.assign_account_to_department(acc_c.account_id, dept, order=2)

        router = RoundRobinRouter(self.db, self.account_manager)

        # Disable account B
        self.account_manager.update_account(acc_b.account_id, enabled=False)

        # Rotation should only cycle between A and C
        s1 = router.select_next_account(dept)
        s2 = router.select_next_account(dept)
        s3 = router.select_next_account(dept)
        s4 = router.select_next_account(dept)

        self.assertEqual([s1, s2, s3, s4], [acc_a.account_id, acc_c.account_id, acc_a.account_id, acc_c.account_id])
        self.assertNotIn(acc_b.account_id, [s1, s2, s3, s4])

    # -------------------------------------------------------------------------
    # Teste F — Concorrência
    # -------------------------------------------------------------------------
    def test_f_concurrency_max_two_accounts(self) -> None:
        """Criar seis tarefas simuladas e confirmar que no máximo 2 contas trabalham simultaneamente."""
        async def _run() -> None:
            # Assign accounts to distinct departments
            self.db.assign_account_to_department(self.test_accounts[0].account_id, "Instagram")
            self.db.assign_account_to_department(self.test_accounts[1].account_id, "Mercado Livre")
            self.db.assign_account_to_department(self.test_accounts[2].account_id, "Shorts")

            runtime = BrowserRuntime()
            router = RoundRobinRouter(self.db, self.account_manager)
            queue = QueueManager(self.db, router)

            # Enqueue 6 jobs
            depts = ["Instagram", "Mercado Livre", "Shorts"]
            for i in range(6):
                queue.enqueue_job(depts[i % 3], f"video_{i}.mp4", drive_file_id=f"drive_f_{i}")

            coordinator = ExecutionCoordinator(
                browser_runtime=runtime,
                queue_manager=queue,
                account_manager=self.account_manager,
                router=router,
                db_manager=self.db,
                max_concurrent_jobs=2,
            )

            max_active = 0
            while True:
                await coordinator.step(dry_run=True)
                active = coordinator.active_job_count
                if active > max_active:
                    max_active = active
                pending = queue.get_pending_jobs()
                if not pending and active == 0:
                    break
                await asyncio.sleep(0.04)

            stats = queue.get_queue_stats()
            self.assertLessEqual(max_active, 2)
            self.assertEqual(stats["completed"], 6)
            await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste G — Exclusividade por conta
    # -------------------------------------------------------------------------
    def test_g_account_exclusivity_single_job_per_account(self) -> None:
        """Tentar inserir duas tarefas simultâneas na mesma conta: somente uma pode executar por vez."""
        async def _run() -> None:
            acc = self.test_accounts[0]
            self.db.assign_account_to_department(acc.account_id, "Instagram")

            runtime = BrowserRuntime()
            router = RoundRobinRouter(self.db, self.account_manager)
            queue = QueueManager(self.db, router)

            # Enqueue two distinct jobs for the same account
            j1, _ = queue.enqueue_job("Instagram", "job1.mp4", drive_file_id="df_1", account_id=acc.account_id)
            j2, _ = queue.enqueue_job("Instagram", "job2.mp4", drive_file_id="df_2", account_id=acc.account_id)

            coordinator = ExecutionCoordinator(
                browser_runtime=runtime,
                queue_manager=queue,
                account_manager=self.account_manager,
                router=router,
                db_manager=self.db,
                max_concurrent_jobs=2,
                max_jobs_per_account=1,
            )

            # Step 1: Exactly 1 job dispatched
            spawned = await coordinator.step(dry_run=True)
            self.assertEqual(spawned, 1)
            self.assertEqual(coordinator.active_job_count, 1)

            # Step 2: Second job must NOT dispatch while account is locked
            spawned_2 = await coordinator.step(dry_run=True)
            self.assertEqual(spawned_2, 0)
            self.assertEqual(coordinator.active_job_count, 1)

            # Let the first job finish
            while coordinator.active_job_count > 0:
                await asyncio.sleep(0.05)

            # Step 3: Now second job can dispatch
            spawned_3 = await coordinator.step(dry_run=True)
            self.assertEqual(spawned_3, 1)

            while coordinator.active_job_count > 0:
                await asyncio.sleep(0.05)

            stats = queue.get_queue_stats()
            self.assertEqual(stats["completed"], 2)
            await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste H — Falhas independentes
    # -------------------------------------------------------------------------
    def test_h_independent_failures_isolation(self) -> None:
        """Simular falha em uma conta e confirmar que a outra continua normalmente sem ser cancelada."""
        async def _run() -> None:
            acc_fail, acc_ok = self.test_accounts[0], self.test_accounts[1]
            self.db.assign_account_to_department(acc_fail.account_id, "Instagram")
            self.db.assign_account_to_department(acc_ok.account_id, "Mercado Livre")

            runtime = BrowserRuntime()
            router = RoundRobinRouter(self.db, self.account_manager)
            queue = QueueManager(self.db, router)

            # Enqueue one job for failing account, one for healthy account
            j_fail, _ = queue.enqueue_job("Instagram", "fail.mp4", drive_file_id="df_fail", account_id=acc_fail.account_id)
            j_ok, _ = queue.enqueue_job("Mercado Livre", "ok.mp4", drive_file_id="df_ok", account_id=acc_ok.account_id)

            coordinator = ExecutionCoordinator(
                browser_runtime=runtime,
                queue_manager=queue,
                account_manager=self.account_manager,
                router=router,
                db_manager=self.db,
                max_concurrent_jobs=2,
            )

            # Configure executor in coordinator to simulate failure only on acc_fail
            original_exec = coordinator._executor.execute_task

            async def patched_execute(job: JobRecord, dry_run: bool = True):
                if job.account_id == acc_fail.account_id:
                    return await original_exec(job, dry_run=True, simulate_failure_account_id=acc_fail.account_id)
                return await original_exec(job, dry_run=True)

            coordinator._executor.execute_task = patched_execute  # type: ignore[assignment]

            # Run coordinator steps
            while True:
                await coordinator.step(dry_run=True)
                if not queue.get_pending_jobs() and coordinator.active_job_count == 0:
                    break
                await asyncio.sleep(0.04)

            # Verify isolated statuses
            res_fail = queue.get_job(j_fail.id)
            res_ok = queue.get_job(j_ok.id)

            self.assertEqual(res_fail.status, JobStatus.FAILED.value)
            self.assertEqual(res_fail.error_code, "SIMULATED_FAILURE")

            self.assertEqual(res_ok.status, JobStatus.PUBLISHED.value)
            self.assertIsNone(res_ok.error_code)

            await runtime.stop()

        asyncio.run(_run())

    # -------------------------------------------------------------------------
    # Teste I — Idempotência
    # -------------------------------------------------------------------------
    def test_i_idempotency_duplicate_file_prevention(self) -> None:
        """Detectar o mesmo arquivo duas vezes e confirmar que não há tarefas duplicadas."""
        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        acc = self.test_accounts[0]
        self.db.assign_account_to_department(acc.account_id, "Instagram")

        job1, is_new1 = queue.enqueue_job(
            department_id="Instagram",
            filename="marketing_tiktok.mp4",
            drive_file_id="1BIT-D_0rTUKuQeEQLooNnl89gzsostjs",
            account_id=acc.account_id,
        )
        self.assertTrue(is_new1)
        self.assertIsNotNone(job1.idempotency_key)

        # Second arrival of the same drive_file_id
        job2, is_new2 = queue.enqueue_job(
            department_id="Instagram",
            filename="marketing_tiktok.mp4",
            drive_file_id="1BIT-D_0rTUKuQeEQLooNnl89gzsostjs",
            account_id=acc.account_id,
        )
        self.assertFalse(is_new2)
        self.assertEqual(job1.id, job2.id)

        # Count total rows in jobs table
        conn = self.db.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM jobs;").fetchone()[0]
        self.assertEqual(count, 1)

    # -------------------------------------------------------------------------
    # Teste J — Reinicialização
    # -------------------------------------------------------------------------
    def test_j_recovery_after_interruption(self) -> None:
        """Interromper a aplicação com tarefas em andamento e recuperar as filas com integridade."""
        router = RoundRobinRouter(self.db, self.account_manager)
        queue = QueueManager(self.db, router)

        acc = self.test_accounts[0]
        self.db.assign_account_to_department(acc.account_id, "Instagram")

        # 1. Job that crashed while in RUNNING / UPLOADING -> should be safely recovered to ASSIGNED
        job_running, _ = queue.enqueue_job("Instagram", "vid_run.mp4", drive_file_id="df_run", account_id=acc.account_id)
        queue.update_job_status(job_running.id, JobStatus.RUNNING.value)

        # 2. Job that crashed while in SUBMITTING -> should be marked UNKNOWN to avoid duplicate post
        job_submitting, _ = queue.enqueue_job("Instagram", "vid_sub.mp4", drive_file_id="df_sub", account_id=acc.account_id)
        queue.update_job_status(job_submitting.id, JobStatus.SUBMITTING.value)

        # Simulate restart & recovery
        self.db.close_connection()
        restarted_db = DatabaseManager(self.db_path)
        restarted_queue = QueueManager(restarted_db, RoundRobinRouter(restarted_db, self.account_manager))

        recovered = restarted_queue.recover_interrupted_jobs()
        self.assertEqual(recovered, 2)

        rec_run = restarted_queue.get_job(job_running.id)
        rec_sub = restarted_queue.get_job(job_submitting.id)

        self.assertEqual(rec_run.status, JobStatus.ASSIGNED.value)
        self.assertEqual(rec_sub.status, JobStatus.UNKNOWN.value)
        self.assertEqual(rec_sub.error_code, "CRASH_DURING_SUBMISSION")

        restarted_db.close_connection()


if __name__ == "__main__":
    unittest.main()
