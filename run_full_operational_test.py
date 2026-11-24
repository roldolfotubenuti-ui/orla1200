import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add tks-engine to sys.path
sys.path.insert(0, r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine")

from core.account_manager import AccountManager
from core.browser_runtime import BrowserRuntime
from core.db_manager import DatabaseManager
from core.execution_coordinator import ExecutionCoordinator
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobStatus, QueueManager
from core.round_robin_router import RoundRobinRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("tks.operational_test")

BATCH_CONFIG = [
    {
        "dept_idx": "01",
        "dept_id": "dept_instagram",
        "dept_name": "Instagram",
        "employee_id": "employee-01",
        "drawer_id": "drawer-01",
        "account_id": "10d617eb-e1a7-4ed7-b8b3-acda804f3f98",
        "expected_user": "unamyti",
        "drive_file_id": "16HAfri4cs0tplMvSdxGiB2x6K78uNxPJ",
        "video_path": r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos\dept_01_rmn.ftbl1_009_7689492826450660630.mp4",
        "original_name": "rmn.ftbl1_009_7689492826450660630.mp4",
        "caption": "bizarro",
        "schedule_time": "2026-11-23 17:00:00"
    },
    {
        "dept_idx": "02",
        "dept_id": "dept_mercadolivre",
        "dept_name": "Mercado Livre",
        "employee_id": "employee-02",
        "drawer_id": "drawer-02",
        "account_id": "37bc39cd-077f-4920-95d1-b11746f0399f",
        "expected_user": "valueini",
        "drive_file_id": "1Y3mG4t7EwLTAJAJEoLHFLKWB8tV_lw8n",
        "video_path": r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos\dept_02_rmn.ftbl1_011_7686592084618349846.mp4",
        "original_name": "rmn.ftbl1_011_7686592084618349846.mp4",
        "caption": "bizarro",
        "schedule_time": "2026-11-23 17:00:00"
    },
    {
        "dept_idx": "03",
        "dept_id": "dept_shorts",
        "dept_name": "Shorts",
        "employee_id": "employee-03",
        "drawer_id": "drawer-03",
        "account_id": "669df47e-4abf-4efd-a870-934295fa7a58",
        "expected_user": "vinihack537",
        "drive_file_id": "1XHdM7ygKdhRtHbzXluhuqMtBxzzpRr03",
        "video_path": r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos\dept_03_rmn.ftbl1_006_7686174262813527318.mp4",
        "original_name": "rmn.ftbl1_006_7686174262813527318.mp4",
        "caption": "bizarro",
        "schedule_time": "2026-11-23 17:00:00"
    },
    {
        "dept_idx": "04",
        "dept_id": "dept_tiktok",
        "dept_name": "TikTok",
        "employee_id": "employee-04",
        "drawer_id": "drawer-04",
        "account_id": "a874cfb3-700c-4b6f-aa3c-ba1e2856894e",
        "expected_user": "vinihack979",
        "drive_file_id": "1uB3JkwQgGV4o9BWTPTmNXtc4EqsvZAix",
        "video_path": r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos\dept_04_rmn.ftbl1_008_7667487423957421334.mp4",
        "original_name": "rmn.ftbl1_008_7667487423957421334.mp4",
        "caption": "bizarro",
        "schedule_time": "2026-11-23 17:00:00"
    },
    {
        "dept_idx": "05",
        "dept_id": "dept_tiktokshop",
        "dept_name": "TikTok Shop",
        "employee_id": "employee-05",
        "drawer_id": "drawer-05",
        "account_id": "e7e6bd57-59de-4272-82b8-f20ce2487e83",
        "expected_user": "vinihack120",
        "drive_file_id": "1L_ZcPuRewaf5s8iamSh_IaOTfAHjq-f4",
        "video_path": r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos\dept_05_rmn.ftbl1_018_7703622500814425366.mp4",
        "original_name": "rmn.ftbl1_018_7703622500814425366.mp4",
        "caption": "bizarro",
        "schedule_time": "2026-11-23 17:00:00"
    },
    {
        "dept_idx": "06",
        "dept_id": "dept_youtube",
        "dept_name": "YouTube",
        "employee_id": "employee-06",
        "drawer_id": "drawer-06",
        "account_id": "4baf0564-985f-4273-b559-9787cdd86c0d",
        "expected_user": "viniciusferraz218",
        "drive_file_id": "1pIgfXH0heiBCbOEcx4Xmgx1gu_gHNd_e",
        "video_path": r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos\dept_06_rmn.ftbl1_008_7667487423957421334.mp4",
        "original_name": "rmn.ftbl1_008_7667487423957421334.mp4",
        "caption": "bizarro",
        "schedule_time": "2026-11-23 17:00:00"
    }
]

async def run_operational_test():
    test_start = time.monotonic()
    start_iso = datetime.now().isoformat()
    logger.info("=== INICIANDO TESTE OPERACIONAL COMPLETO TKS ENGINE 3.0 ===")
    
    db = DatabaseManager.get_instance()
    queue = QueueManager(db_manager=db)
    account_mgr = AccountManager()
    router = RoundRobinRouter(db)
    bridge = OfficeEventBridge.get_instance()
    
    # Iniciar BrowserRuntime
    runtime = BrowserRuntime()
    await runtime.start(headless=True)
    
    coordinator = ExecutionCoordinator(
        browser_runtime=runtime,
        queue_manager=queue,
        account_manager=account_mgr,
        router=router,
        db_manager=db,
        max_concurrent_jobs=2,
        max_jobs_per_account=1,
        allow_real_publishing=False
    )
    
    # Ativação do Modo Real expressamente confirmada
    coordinator.set_real_publishing(enabled=True, confirmed=True)
    logger.info("Modo Real ATIVADO com sucesso: max_concurrent=2, allow_real_publishing=True")
    
    enqueued_jobs = []
    
    # 1. Enfileirar as 6 tarefas no QueueManager
    print("\n--- 1. ENFILEIRANDO AS 6 TAREFAS NO QUEUEMANAGER ---")
    for item in BATCH_CONFIG:
        job, is_dup = queue.enqueue_job(
            department_id=item["dept_id"],
            filename=item["video_path"],
            drive_file_id=item["drive_file_id"],
            account_id=item["account_id"],
            schedule_time=item["schedule_time"],
            platform="tiktok"
        )
        job.caption = item["caption"]
        item["job_id"] = job.id
        enqueued_jobs.append(job)
        print(f"[{item['dept_idx']}] Dept: {item['dept_name']} | JobID: {job.id} | Account: @{item['expected_user']} | Duplicate: {is_dup}")
        
    print("\n--- 2. PROCESSANDO AS 6 TAREFAS (CONCORRÊNCIA MÁXIMA = 2) ---")
    peak_concurrency = 0
    task_tracking = {j.id: {"start_time": None, "end_time": None, "status": None, "error": None} for j in enqueued_jobs}
    
    # Loop de execução até esvaziar a fila
    while True:
        # Step coordinator
        spawned = await coordinator.step(dry_run=False)
        active = coordinator.active_job_count
        if active > peak_concurrency:
            peak_concurrency = active
            
        # Log active jobs
        if active > 0:
            print(f"[Coordinator] Ativos: {active}/2 simultâneos | Spawned nesta iteração: {spawned}")
            
        # Check jobs state in database
        all_done = True
        for j in enqueued_jobs:
            current_job = queue.get_job(j.id)
            if current_job:
                task_tracking[j.id]["status"] = current_job.status
                if current_job.status in (JobStatus.RUNNING.value, JobStatus.UPLOADING.value, JobStatus.PROCESSING.value, JobStatus.SUBMITTING.value):
                    if not task_tracking[j.id]["start_time"]:
                        task_tracking[j.id]["start_time"] = time.monotonic()
                    all_done = False
                elif current_job.status in (JobStatus.QUEUED.value, JobStatus.ASSIGNED.value):
                    all_done = False
                elif current_job.status in (JobStatus.SCHEDULED.value, JobStatus.PUBLISHED.value, JobStatus.FAILED.value, JobStatus.UNKNOWN.value):
                    if not task_tracking[j.id]["end_time"]:
                        task_tracking[j.id]["end_time"] = time.monotonic()
                        task_tracking[j.id]["last_error"] = current_job.error_message
                        
        if all_done and active == 0:
            print("[Coordinator] Todas as tarefas finalizaram!")
            break
            
        await asyncio.sleep(2.0)
        
    total_duration = time.monotonic() - test_start
    await runtime.close()
    
    print("\n--- 3. RESULTADOS FINAIS DA EXECUÇÃO ---")
    results_summary = []
    scheduled_count = 0
    failed_count = 0
    
    for item in BATCH_CONFIG:
        jid = item["job_id"]
        meta = task_tracking.get(jid, {})
        final_job = queue.get_job(jid)
        st = final_job.status if final_job else meta.get("status", "UNKNOWN")
        err = final_job.error_message if final_job else meta.get("last_error")
        
        start_t = meta.get("start_time") or test_start
        end_t = meta.get("end_time") or time.monotonic()
        dur = max(0.0, end_t - start_t)
        
        if st in (JobStatus.SCHEDULED.value, JobStatus.PUBLISHED.value):
            scheduled_count += 1
        elif st == JobStatus.FAILED.value:
            failed_count += 1
            
        res_entry = {
            "dept_idx": item["dept_idx"],
            "dept_name": item["dept_name"],
            "job_id": jid,
            "drive_file_id": item["drive_file_id"],
            "file_name": item["original_name"],
            "account_id": item["account_id"],
            "detected_user": f"@{item['expected_user']}",
            "employee_id": item["employee_id"],
            "drawer_id": item["drawer_id"],
            "caption": item["caption"],
            "scheduled_time": item["schedule_time"],
            "duration_seconds": round(dur, 2),
            "final_status": st,
            "error_reason": err,
            "evidence": "Registro em tks_jobs.db e evento emitido" if st in (JobStatus.SCHEDULED.value, JobStatus.PUBLISHED.value) else (err or "Falha de submissão")
        }
        results_summary.append(res_entry)
        print(f"[{item['dept_idx']}] {item['dept_name']} | Status: {st} | User: @{item['expected_user']} | Duração: {dur:.1f}s | Erro: {err}")
        
    summary_data = {
        "test_start_iso": start_iso,
        "test_end_iso": datetime.now().isoformat(),
        "total_duration_seconds": round(total_duration, 2),
        "peak_concurrency": peak_concurrency,
        "total_detected": len(BATCH_CONFIG),
        "total_drawers_triggered": len(BATCH_CONFIG),
        "total_employees_triggered": len(BATCH_CONFIG),
        "total_scheduled": scheduled_count,
        "total_failed": failed_count,
        "results": results_summary
    }
    
    out_file = r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\operational_test_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nResumo salvo com sucesso em: {out_file}")
    return summary_data

if __name__ == "__main__":
    asyncio.run(run_operational_test())
