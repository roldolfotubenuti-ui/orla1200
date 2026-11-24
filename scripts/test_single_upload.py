import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager
from core.uploader import Uploader, UploadTask
from core.logger_manager import LoggerManager

async def test_single_upload():
    logger = LoggerManager()
    mgr = AccountManager()
    acc = next(a for a in mgr.list_accounts() if a.username == 'valueini')
    print(f"Testando agendamento com a conta @{acc.username}...")
    
    runtime = BrowserRuntime()
    await runtime.start()
    try:
        context, page = await runtime.get_or_create_account_session(acc.account_id, mgr)
        url = 'https://www.tiktok.com/tiktokstudio/upload?from=webapp'
        print(f"Navegando para {url}...")
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        
        uploader = Uploader.from_page(page=page, logger=logger, homologation_mode=False)
        
        task = UploadTask(
            file_path=Path(r"E:\ORLA1200\2\rmn.ftbl1_012_7689210188892654851.mp4"),
            caption="ABSURDO",
            schedule_time=datetime(2026, 11, 24, 18, 0),
            visibility="public",
        )
        
        print("Executando uploader.upload_video()...")
        res = await uploader.upload_video(task)
        print("Resultado do upload:", res)
        await page.screenshot(path="storage/test_single_upload_result.png")
        print("Screenshot salvo em storage/test_single_upload_result.png")
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(test_single_upload())
