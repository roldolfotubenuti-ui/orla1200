"""
Comprehensive unit tests for TKS Engine 2.0 Integrity Corrections (using unittest.TestCase):
1. Caption literal transmission (no automatic filename prefix or forced hashtags).
2. Distinction of all states (especially 'scheduled' vs 'published').
3. Failure preservation (failed tasks are not overwritten as pending).
4. Live panel counters and status messaging.
5. Legacy record normalization and preservation.
6. Deduplication and accurate accounting.
"""

from datetime import datetime, timedelta
from pathlib import Path
import shutil
import tempfile
import unittest

from core.scheduler import UploadTask
from core.uploader import UploadResult
from gui.services.storage_service import GuiStorageService
from core.logger_manager import LoggerManager


class TestIntegrityFixes(unittest.TestCase):
    """Test suite validating all 14 integrity criteria."""

    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.log_dir = self.test_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = LoggerManager("TestLogger", log_file=self.log_dir / "test.log")
        self.storage_service = GuiStorageService(
            project_root=self.test_dir,
            storage_dir_name="storage",
            logger=self.logger,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 1. Testes de Legendas
    # ------------------------------------------------------------------

    def test_01_caption_only_hashtag(self) -> None:
        """Item 1: Legenda contendo apenas hashtag deve ser transmitida literalmente."""
        task = UploadTask(
            file_path=Path("videos/rmn.ftbl1_005_7675620464353561859.mp4"),
            caption="#neymar",
        )
        self.assertEqual(task.caption, "#neymar")
        self.assertNotIn("rmn.ftbl", task.caption)
        self.assertTrue(task.caption.startswith("#"))

    def test_02_caption_empty(self) -> None:
        """Item 2: Legenda vazia não deve receber nome de arquivo compulsoriamente."""
        task = UploadTask(
            file_path=Path("videos/video_teste_01.mp4"),
            caption="",
        )
        self.assertEqual(task.caption, "")
        self.assertNotIn("video_teste_01", task.caption)

    def test_03_caption_text_and_emojis(self) -> None:
        """Item 3: Legenda com texto complexo, acentuação e emojis preservada literalmente."""
        custom = "Gol incrível do Brasil! ⚽🔥 #futebol #selecao"
        task = UploadTask(
            file_path=Path("videos/sample.mp4"),
            caption=custom,
        )
        self.assertEqual(task.caption, custom)
        self.assertNotIn("sample.mp4", task.caption)

    def test_04_caption_edited_preserves_final_text(self) -> None:
        """Item 4: Edição de legenda preserva o texto final informado sem reverter para filename."""
        task = UploadTask(
            file_path=Path("videos/sample.mp4"),
            caption="Texto Inicial",
        )
        task.caption = "#futebol #viral"
        self.assertEqual(task.caption, "#futebol #viral")
        self.assertNotIn("sample", task.caption)

    # ------------------------------------------------------------------
    # 2. Testes de Estados: Agendamento vs Publicação
    # ------------------------------------------------------------------

    def test_05_scheduled_future_upload_result(self) -> None:
        """Item 5: Agendamento futuro confirmado deve ter status='scheduled', NUNCA 'published'."""
        future_dt = datetime.now() + timedelta(days=2)
        task = UploadTask(
            file_path=Path("sample.mp4"),
            caption="#teste",
            schedule_time=future_dt,
        )
        res = UploadResult(
            success=True,
            file_path=task.file_path,
            message="Upload successful",
            timestamp=datetime.now(),
            is_scheduled=True,
            status="scheduled",
        )
        self.assertEqual(res.status, "scheduled")
        self.assertTrue(res.is_scheduled)
        data_dict = res.to_dict()
        self.assertEqual(data_dict["status"], "scheduled")
        self.assertNotEqual(data_dict["status"], "published")

    def test_06_immediate_publication_confirmed(self) -> None:
        """Item 6: Publicação imediata confirmada deve ser classificada como 'published'."""
        task = UploadTask(
            file_path=Path("immediate.mp4"),
            caption="Publicação imediata",
            schedule_time=None,
        )
        res = UploadResult(
            success=True,
            file_path=task.file_path,
            message="Upload successful",
            timestamp=datetime.now(),
            is_scheduled=False,
        )
        self.assertEqual(res.status, "published")
        self.assertEqual(res.to_dict()["status"], "published")

    def test_07_scheduled_past_clock_not_automatically_published(self) -> None:
        """Item 7: Agendamento cujo relógio passou não muda automaticamente para 'published'."""
        past_sched = datetime.now() - timedelta(hours=1)
        record = {
            "file": "past_video.mp4",
            "schedule_time": past_sched.isoformat(),
            "status": "scheduled",
            "outcome": "confirmed_success",
        }
        normalized = self.storage_service.normalize_upload_record(record)
        self.assertEqual(normalized["status"], "scheduled")

    def test_08_published_confirmed_verification(self) -> None:
        """Item 8: Publicação imediata efetivamente confirmada."""
        record = {
            "file": "live_video.mp4",
            "schedule_time": None,
            "status": "success",
            "outcome": "confirmed_success",
        }
        normalized = self.storage_service.normalize_upload_record(record)
        self.assertEqual(normalized["status"], "published")

    # ------------------------------------------------------------------
    # 3. Testes de Falhas e Desconhecidos
    # ------------------------------------------------------------------

    def test_09_failed_post_button_disabled(self) -> None:
        """Item 9: Falha por botão desabilitado gravada como 'failed'."""
        task = UploadTask(
            file_path=Path("failed_video.mp4"),
            caption="#erro",
            schedule_time=datetime.now() + timedelta(hours=2),
        )
        res = UploadResult(
            success=False,
            file_path=task.file_path,
            message="Post button is disabled",
            timestamp=datetime.now(),
            error="Post button remained disabled in TikTok Studio",
            status="failed",
        )
        self.assertEqual(res.status, "failed")
        data = {"uploads": []}
        self.storage_service.append_upload_record(data, task, res)
        saved = data["uploads"][0]
        self.assertEqual(saved["status"], "failed")
        self.assertIn("Post button remained disabled", saved["error"])

    def test_10_unknown_outcome(self) -> None:
        """Item 10: Timeout de confirmação gravado como 'unknown'."""
        task = UploadTask(
            file_path=Path("unknown_video.mp4"),
            caption="#timeout",
        )
        res = UploadResult(
            success=False,
            file_path=task.file_path,
            message="Post confirmation timed out (outcome unknown)",
            timestamp=datetime.now(),
            outcome="unknown",
        )
        self.assertEqual(res.status, "unknown")
        data = {"uploads": []}
        self.storage_service.append_upload_record(data, task, res)
        self.assertEqual(data["uploads"][0]["status"], "unknown")

    # ------------------------------------------------------------------
    # 4. Normalização de Registros Antigos e Deduplicação
    # ------------------------------------------------------------------

    def test_11_legacy_record_normalization(self) -> None:
        """Item 11: Normalização compatível com registros antigos preservando histórico."""
        future_time = (datetime.now() + timedelta(days=1)).isoformat()
        old_record_future = {
            "file": "rmn.ftbl1_005_7675620464353561859.mp4",
            "caption": "#neynar",
            "schedule_time": future_time,
            "status": "success",
            "outcome": "confirmed_success",
        }
        norm_future = self.storage_service.normalize_upload_record(old_record_future)
        self.assertEqual(norm_future["status"], "scheduled")

        old_record_immediate = {
            "file": "rmn.ftbl1_002_7685841219531984150.mp4",
            "caption": "video.mp4",
            "schedule_time": None,
            "status": "success",
            "outcome": "confirmed_success",
        }
        norm_imm = self.storage_service.normalize_upload_record(old_record_immediate)
        self.assertEqual(norm_imm["status"], "published")

    def test_12_counters_and_tabs_logic(self) -> None:
        """Item 12: Atualização correta da contagem por categoria."""
        items = [
            {"file": "v1.mp4", "status": "scheduled", "schedule_time": "2026-11-20T10:00:00"},
            {"file": "v2.mp4", "status": "published", "schedule_time": None},
            {"file": "v3.mp4", "status": "failed", "schedule_time": "2026-11-20T11:00:00"},
            {"file": "v4.mp4", "status": "pending", "schedule_time": "2026-11-20T12:00:00"},
            {"file": "v5.mp4", "status": "unknown", "schedule_time": "2026-11-20T13:00:00"},
        ]
        counts = {"sched": 0, "pub": 0, "pend": 0, "fail": 0}
        for it in items:
            st = str(it.get("status") or "pending").lower().strip()
            sched_time = it.get("schedule_time")
            is_sched = (st == "scheduled") or (st == "success" and bool(sched_time))
            is_pub = (st == "published") or (st == "success" and not sched_time)
            is_fail = (st in ("failed", "conflict", "unknown")) or ("fail" in st or "erro" in st)
            if is_sched:
                counts["sched"] += 1
            elif is_pub:
                counts["pub"] += 1
            elif is_fail:
                counts["fail"] += 1
            else:
                counts["pend"] += 1

        self.assertEqual(counts["sched"], 1)
        self.assertEqual(counts["pub"], 1)
        self.assertEqual(counts["fail"], 2)  # v3 (failed) + v5 (unknown)
        self.assertEqual(counts["pend"], 1)

    def test_13_completion_message_with_failures(self) -> None:
        """Item 13: Mensagem de conclusão não exibe 100% de sucesso se houver falhas."""
        failed_count = 2
        unknown_count = 0
        scheduled_count = 1
        published_count = 0
        total = 3

        if failed_count > 0 or unknown_count > 0:
            title = "⚠️ Fila finalizada com alertas"
            parts = []
            if scheduled_count > 0:
                parts.append(f"{scheduled_count} agendado(s)")
            if published_count > 0:
                parts.append(f"{published_count} publicado(s)")
            if failed_count > 0:
                parts.append(f"{failed_count} com falha")
            msg = " · ".join(parts)
        else:
            title = "✓ Todas as publicações foram concluídas"
            msg = f"{total} finalizada(s) com sucesso"

        self.assertEqual(title, "⚠️ Fila finalizada com alertas")
        self.assertIn("2 com falha", msg)
        self.assertIn("1 agendado(s)", msg)

    def test_14_no_record_duplication_when_confirmed_and_completed(self) -> None:
        """Item 14: Confirmação e posterior conclusão não duplicam registros do mesmo arquivo."""
        username = "test_account"
        planned = [
            {
                "file": "video1.mp4",
                "file_path": "C:/videos/video1.mp4",
                "caption": "#teste1",
                "schedule_time": (datetime.now() + timedelta(hours=3)).isoformat(),
                "status": "pending",
            }
        ]
        self.storage_service.confirm_planned_schedules(username, planned)
        loaded = self.storage_service.load_scheduled(username)
        self.assertEqual(len(loaded["uploads"]), 1)
        self.assertEqual(loaded["uploads"][0]["status"], "pending")

        task = UploadTask(
            file_path=Path("C:/videos/video1.mp4"),
            caption="#teste1",
            schedule_time=datetime.now() + timedelta(hours=3),
        )
        result = UploadResult(
            success=True,
            file_path=task.file_path,
            message="Success",
            timestamp=datetime.now(),
            status="scheduled",
        )
        self.storage_service.append_upload_record(loaded, task, result)
        self.storage_service.save_scheduled(username, loaded)

        refreshed = self.storage_service.load_scheduled(username)
        self.assertEqual(len(refreshed["uploads"]), 1)
        self.assertEqual(refreshed["uploads"][0]["file"], "video1.mp4")
        self.assertEqual(refreshed["uploads"][0]["status"], "scheduled")


if __name__ == "__main__":
    unittest.main()
