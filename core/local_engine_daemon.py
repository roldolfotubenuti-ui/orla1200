"""Local Engine Daemon for TKS Engine 3.0.

Provides a robust, local-only (127.0.0.1:5050) REST and WebSocket API allowing
TKS Virtual Office (running at http://localhost:3005) to function as the full
Operations Command Central without needing the PyQt6 desktop GUI.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from aiohttp import web, WSMsgType

from core.account_manager import AccountManager
from core.browser_runtime import BrowserRuntime
from core.db_manager import DatabaseManager
from core.execution_coordinator import ExecutionCoordinator
from core.local_folder_watcher import LocalFolderWatcher
from core.office_event_bridge import OfficeEventBridge
from core.queue_manager import JobStatus, QueueManager
from core.round_robin_router import RoundRobinRouter
from utils.app_paths import get_storage_dir

logger = logging.getLogger("tks.engine_daemon")


class LocalEngineDaemon:
    """Async engine daemon orchestrating watcher, coordinator, and real-time API."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5050,
        folders_base_dir: Path | str = Path(r"E:\ORLA1200"),
    ) -> None:
        self.host = host
        self.port = port
        self.folders_base_dir = Path(folders_base_dir)

        # Core subsystems
        self.db = DatabaseManager.get_instance()
        self.account_mgr = AccountManager()
        self.queue_mgr = QueueManager(self.db)
        self.router = RoundRobinRouter(self.queue_mgr, self.account_mgr)
        self.bridge = OfficeEventBridge.get_instance()

        self.runtime: BrowserRuntime | None = None
        self.coordinator: ExecutionCoordinator | None = None
        self.watcher: LocalFolderWatcher | None = None

        self.app = web.Application(middlewares=[self._cors_middleware])
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._coordinator_task: asyncio.Task | None = None
        self._coordinator_worker_task: asyncio.Task | None = None

        self._setup_routes()

    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler: Any) -> web.Response:
        """Allow requests strictly from local frontend origins."""
        origin = request.headers.get("Origin", "")
        allowed_origins = {"http://localhost:3005", "http://127.0.0.1:3005"}

        if request.method == "OPTIONS":
            resp = web.Response(status=200)
        else:
            try:
                resp = await handler(request)
            except web.HTTPException as ex:
                resp = ex

        if origin in allowed_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    def _setup_routes(self) -> None:
        self.app.router.add_get("/api/status", self.handle_get_status)
        self.app.router.add_get("/api/overview", self.handle_get_overview)
        self.app.router.add_get("/api/folders", self.handle_get_folders)
        self.app.router.add_post("/api/folders/scan", self.handle_scan_folders)
        self.app.router.add_get("/api/accounts", self.handle_get_accounts)
        self.app.router.add_post("/api/accounts/test", self.handle_test_accounts)
        self.app.router.add_get("/api/queue", self.handle_get_queue)
        self.app.router.add_get("/api/history", self.handle_get_history)
        self.app.router.add_post("/api/control", self.handle_control)
        self.app.router.add_get("/ws/events", self.handle_ws_events)

    async def initialize(self) -> None:
        """Initialize async runtime, coordinator, watcher, and bridge subscribers."""
        logger.info("Initializing LocalEngineDaemon subsystems...")

        # Setup BrowserRuntime (headless)
        self.runtime = BrowserRuntime()
        await self.runtime.start(headless=True)

        # Setup ExecutionCoordinator
        self.coordinator = ExecutionCoordinator(
            browser_runtime=self.runtime,
            queue_manager=self.queue_mgr,
            account_manager=self.account_mgr,
            router=self.router,
            db_manager=self.db,
            max_concurrent_jobs=2,
            max_jobs_per_account=1,
            allow_real_publishing=False,
        )

        # Hook coordinator job completion to trigger atomic archival in LocalFolderWatcher
        def on_coordinator_event(event_type: str, data: dict[str, Any]) -> None:
            if event_type == "job.completed":
                job_id = data.get("job_id")
                status = data.get("status")
                if job_id and status == JobStatus.SCHEDULED and self.watcher:
                    logger.info(f"Job {job_id} confirmed as SCHEDULED. Archiving to _PROCESSADOS...")
                    self.watcher.archive_processed_video(job_id)

        self.coordinator.register_callback(on_coordinator_event)

        # Setup LocalFolderWatcher
        self.watcher = LocalFolderWatcher(
            base_dir=self.folders_base_dir,
            db_manager=self.db,
            queue_manager=self.queue_mgr,
            bridge=self.bridge,
        )
        self.watcher.start()

        # Hook OfficeEventBridge to broadcast on WebSocket
        loop = asyncio.get_running_loop()

        def bridge_subscriber(payload: dict[str, Any]) -> None:
            if self._ws_clients:
                msg = json.dumps(payload, ensure_ascii=False)
                for ws in list(self._ws_clients):
                    if not ws.closed:
                        asyncio.run_coroutine_threadsafe(ws.send_str(msg), loop)

        self.bridge.subscribe(bridge_subscriber)
        logger.info("LocalEngineDaemon subsystems initialized.")

    async def start_server(self) -> None:
        """Start aiohttp HTTP and WebSocket server."""
        await self.initialize()
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"LocalEngineDaemon API running at http://{self.host}:{self.port}")

        # Start continuous coordinator execution worker
        self._coordinator_worker_task = asyncio.create_task(self._coordinator_worker_loop())

        self.bridge.emit(
            event_name="engine.started",
            status="RUNNING",
            extra={"host": self.host, "port": self.port, "mode": "HEADLESS_DAEMON"},
        )

    async def _coordinator_worker_loop(self) -> None:
        """Background loop stepping the execution coordinator periodically."""
        logger.info("LocalEngineDaemon: Coordinator background worker loop started.")
        while True:
            try:
                if self.coordinator and not self.coordinator.is_paused and not self.coordinator.is_stopped:
                    dry_run = not self.coordinator.allow_real_publishing
                    spawned = await self.coordinator.step(dry_run=dry_run)
                    if spawned > 0:
                        logger.info(f"Coordinator stepped: spawned {spawned} job(s) (dry_run={dry_run})")
            except Exception as exc:
                logger.error(f"Error in coordinator worker loop: {exc}")
            await asyncio.sleep(4)

    async def shutdown(self) -> None:
        """Graceful shutdown of all subsystems."""
        logger.info("Shutting down LocalEngineDaemon...")
        if self._coordinator_worker_task and not self._coordinator_worker_task.done():
            self._coordinator_worker_task.cancel()
        if self.watcher:
            self.watcher.stop()
        if self.coordinator:
            await self.coordinator.stop()
        if self.runtime:
            await self.runtime.stop()

        for ws in list(self._ws_clients):
            if not ws.closed:
                await ws.close()

        if self._runner:
            await self._runner.cleanup()

        self.bridge.emit(
            event_name="engine.stopped",
            status="STOPPED",
            extra={"timestamp": datetime.now().isoformat()},
        )
        logger.info("LocalEngineDaemon shut down cleanly.")

    # =========================================================================
    # HTTP REST & WEBSOCKET HANDLERS
    # =========================================================================

    async def handle_get_status(self, request: web.Request) -> web.Response:
        """Returns overall daemon and coordinator status."""
        active_jobs = self.coordinator.active_job_count if self.coordinator else 0
        is_paused = self.coordinator.is_paused if self.coordinator else False
        is_stopped = self.coordinator.is_stopped if self.coordinator else True
        allow_real = self.coordinator.allow_real_publishing if self.coordinator else False

        folder_summary = self.watcher.get_summary() if self.watcher else {}

        return web.json_response({
            "ok": True,
            "engine": {
                "running": True,
                "is_paused": is_paused,
                "is_stopped": is_stopped,
                "allow_real_publishing": allow_real,
                "active_job_count": active_jobs,
                "max_concurrent_jobs": 2,
            },
            "folders": {
                "base_dir": str(self.folders_base_dir),
                "is_watching": self.watcher._is_running if self.watcher else False,
                "total_pending": folder_summary.get("total_pending", 0),
                "total_processed": folder_summary.get("total_processed", 0),
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    async def handle_get_overview(self, request: web.Request) -> web.Response:
        """Comprehensive operational metrics across 6 departments."""
        folder_summary = self.watcher.get_summary() if self.watcher else {}
        accounts = self.account_mgr.list_accounts()

        # Count jobs by status
        job_counts = {
            "total": 0,
            "ready": 0,
            "running": 0,
            "scheduled": 0,
            "failed": 0,
            "archived": 0,
        }

        with self.db.get_connection() as conn:
            c = conn.execute("SELECT status, count(*) as cnt FROM jobs GROUP BY status")
            for r in c.fetchall():
                st = r["status"].upper()
                cnt = r["cnt"]
                job_counts["total"] += cnt
                if "READY" in st or "QUEUED" in st or "DETECTED" in st:
                    job_counts["ready"] += cnt
                elif "UPLOADING" in st or "PROCESSING" in st or "RUNNING" in st:
                    job_counts["running"] += cnt
                elif "SCHEDULED" in st:
                    job_counts["scheduled"] += cnt
                elif "ARCHIVED" in st:
                    job_counts["archived"] += cnt
                elif "FAIL" in st:
                    job_counts["failed"] += cnt

        # Sanitize account profiles for display
        acc_list = []
        for a in accounts:
            status_str = a.auth_status.value if hasattr(a.auth_status, 'value') else str(a.auth_status)
            acc_list.append({
                "account_id": a.account_id,
                "username": a.username,
                "department_id": a.department_id,
                "auth_status": status_str,
                "enabled": a.enabled,
                "cookie_count": a.cookie_count,
                "last_validated_at": a.last_validated_at,
                "display_title": a.display_title,
            })

        return web.json_response({
            "ok": True,
            "engine_state": "RUNNING" if not (self.coordinator and self.coordinator.is_paused) else "PAUSED",
            "allow_real_publishing": self.coordinator.allow_real_publishing if self.coordinator else False,
            "job_counts": job_counts,
            "folders": folder_summary.get("folders", []),
            "total_pending_videos": folder_summary.get("total_pending", 0),
            "total_processed_videos": folder_summary.get("total_processed", 0),
            "accounts": acc_list,
        })

    async def handle_get_folders(self, request: web.Request) -> web.Response:
        """Detailed status of E:\\ORLA1200\\1..6 and _PROCESSADOS."""
        if not self.watcher:
            return web.json_response({"ok": False, "error": "Watcher not initialized"}, status=500)
        summary = self.watcher.get_summary()
        return web.json_response({"ok": True, **summary})

    async def handle_scan_folders(self, request: web.Request) -> web.Response:
        """Trigger immediate folder scan and job detection."""
        if not self.watcher:
            return web.json_response({"ok": False, "error": "Watcher not initialized"}, status=500)
        detected = self.watcher.scan_all_folders()
        return web.json_response({
            "ok": True,
            "message": f"Varredura concluída. {len(detected)} vídeos verificados/registrados.",
            "detected": detected,
        })

    async def handle_get_accounts(self, request: web.Request) -> web.Response:
        """List registered TikTok accounts safely."""
        accounts = self.account_mgr.list_accounts()
        acc_list = [{
            "account_id": a.account_id,
            "username": a.username,
            "department_id": a.department_id,
            "auth_status": a.auth_status.value if hasattr(a.auth_status, 'value') else str(a.auth_status),
            "enabled": a.enabled,
            "cookie_count": a.cookie_count,
            "last_validated_at": a.last_validated_at,
            "display_title": a.display_title,
        } for a in accounts]
        return web.json_response({"ok": True, "count": len(acc_list), "accounts": acc_list})

    async def handle_test_accounts(self, request: web.Request) -> web.Response:
        """Test authentication status of TikTok accounts via CookieValidator."""
        from core.cookie_validator import CookieValidator
        results = []
        for acc in self.account_mgr.list_accounts():
            rep = self.account_mgr.validate_account_cookies(acc.account_id)
            results.append({
                "account_id": acc.account_id,
                "username": acc.username,
                "is_valid": rep.is_valid,
                "status": rep.status.value,
                "issues": rep.issues,
            })
        return web.json_response({"ok": True, "results": results})

    async def handle_get_queue(self, request: web.Request) -> web.Response:
        """List jobs in queue from SQLite."""
        limit = int(request.query.get("limit", "50"))
        dept_filter = request.query.get("department_id")

        with self.db.get_connection() as conn:
            if dept_filter:
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE department_id = ? ORDER BY created_at DESC LIMIT ?",
                    (dept_filter, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            jobs = [dict(r) for r in cursor.fetchall()]

        return web.json_response({"ok": True, "count": len(jobs), "jobs": jobs})

    async def handle_get_history(self, request: web.Request) -> web.Response:
        """List events from execution_events table."""
        limit = int(request.query.get("limit", "100"))
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM execution_events ORDER BY id DESC LIMIT ?", (limit,)
            )
            events = [dict(r) for r in cursor.fetchall()]
        return web.json_response({"ok": True, "count": len(events), "events": events})

    async def handle_control(self, request: web.Request) -> web.Response:
        """Coordinator control actions: start, pause, resume, stop, authorize_real."""
        try:
            data = await request.json()
        except Exception:
            data = {}

        action = data.get("action", "").lower()
        if not self.coordinator:
            return web.json_response({"ok": False, "error": "Coordinator not initialized"}, status=500)

        if action == "start":
            self.coordinator.start()
            if not self._coordinator_worker_task or self._coordinator_worker_task.done():
                self._coordinator_worker_task = asyncio.create_task(self._coordinator_worker_loop())
            return web.json_response({"ok": True, "message": "Operação iniciada com sucesso."})

        elif action == "pause":
            self.coordinator.pause()
            return web.json_response({"ok": True, "message": "Operação pausada."})

        elif action == "resume":
            self.coordinator.resume()
            return web.json_response({"ok": True, "message": "Operação retomada."})

        elif action == "stop":
            self.coordinator.stop()
            return web.json_response({"ok": True, "message": "Operação parada."})

        elif action == "authorize_real":
            confirmed = bool(data.get("confirmed", False))
            if not confirmed:
                return web.json_response({
                    "ok": False,
                    "error": "Autorização requer confirmação explícita (confirmed=True)."
                }, status=400)
            self.coordinator.set_real_publishing(True, confirmed=True)
            self.coordinator.start()
            if not self._coordinator_worker_task or self._coordinator_worker_task.done():
                self._coordinator_worker_task = asyncio.create_task(self._coordinator_worker_loop())
            logger.info("LocalEngineDaemon: MODO REAL AUTORIZADO E ATIVADO!")
            return web.json_response({
                "ok": True,
                "message": "MODO REAL AUTORIZADO com sucesso. Uploads e agendamentos serão executados.",
                "allow_real_publishing": True,
            })

        elif action == "revoke_real":
            self.coordinator.set_real_publishing(False, confirmed=False)
            return web.json_response({
                "ok": True,
                "message": "Modo real desativado.",
                "allow_real_publishing": False,
            })

        return web.json_response({"ok": False, "error": f"Ação desconhecida: {action}"}, status=400)

    async def handle_ws_events(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket endpoint streaming operational events to Virtual Office in real-time."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info(f"Virtual Office WebSocket client connected ({len(self._ws_clients)} total)")

        # Send initial handshake with current state
        init_payload = {
            "event": "engine.connected",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_paused": self.coordinator.is_paused if self.coordinator else False,
            "allow_real_publishing": self.coordinator.allow_real_publishing if self.coordinator else False,
        }
        await ws.send_str(json.dumps(init_payload))

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Echo or handle incoming client ping
                    try:
                        parsed = json.loads(msg.data)
                        if parsed.get("type") == "ping":
                            await ws.send_str(json.dumps({"type": "pong"}))
                    except Exception:
                        pass
                elif msg.type == WSMsgType.ERROR:
                    logger.debug(f"WebSocket client error: {ws.exception()}")
        finally:
            self._ws_clients.discard(ws)
            logger.info(f"Virtual Office WebSocket client disconnected ({len(self._ws_clients)} remaining)")

        return ws


# CLI entry point to run standalone daemon
async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    daemon = LocalEngineDaemon()
    await daemon.start_server()

    try:
        # Keep running until cancelled
        while True:
            await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await daemon.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
