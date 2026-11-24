"""Entry point to launch TKS Engine 3.0 in background headless daemon mode for Virtual Office."""
import asyncio
import logging
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.local_engine_daemon import LocalEngineDaemon

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(root_dir / "storage" / "engine_daemon.log", encoding="utf-8")
        ]
    )
    is_real = "--real" in sys.argv
    print(f"Starting TKS Engine 3.0 Headless Daemon on 127.0.0.1:5050 (real_publishing={is_real})...")
    daemon = LocalEngineDaemon(host="127.0.0.1", port=5050)
    
    try:
        async def run_forever():
            await daemon.start_server()
            if is_real and daemon.coordinator:
                daemon.coordinator.set_real_publishing(True, confirmed=True)
                daemon.coordinator.start()
                if not daemon._coordinator_worker_task or daemon._coordinator_worker_task.done():
                    daemon._coordinator_worker_task = asyncio.create_task(daemon._coordinator_worker_loop())
                print("TKS Engine 3.0: MODO REAL DE PUBLICAÇÃO AUTORIZADO E ATIVADO!")

            while True:
                await asyncio.sleep(3600)

        asyncio.run(run_forever())
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down daemon...")
