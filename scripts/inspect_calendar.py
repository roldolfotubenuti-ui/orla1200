import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager

async def inspect_calendar_html():
    mgr = AccountManager()
    accs = mgr.list_accounts()
    acc = next(a for a in accs if a.username == 'valueini')
    
    runtime = BrowserRuntime()
    await runtime.start()
    try:
        context, page = await runtime.get_or_create_account_session(acc.account_id, mgr)
        url = 'https://www.tiktok.com/tiktokstudio/upload?from=webapp'
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(4)
        
        file_input = await page.wait_for_selector("input[type='file']", state="attached", timeout=15000)
        video_path = r"E:\ORLA1200\2\rmn.ftbl1_012_7689210188892654851.mp4"
        await file_input.set_input_files(video_path)
        await asyncio.sleep(5)
        
        # Clicar no rádio Agendar
        radio = page.locator('input[name="postSchedule"][value="schedule"]')
        await radio.click(force=True)
        await asyncio.sleep(1)
        
        # Descartar modal Permitir
        await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(b => b.textContent.trim().toLowerCase() === 'permitir');
            if (b) b.click();
        }''')
        await asyncio.sleep(1)
        
        # Clicar no campo de data
        inputs = page.locator("input[class*='TUXTextInputCore-input']")
        count = await inputs.count()
        print(f"Total TUX inputs: {count}")
        for idx in range(count):
            val = await inputs.nth(idx).input_value()
            print(f"Input {idx}: {val}")
        
        date_input = inputs.nth(1)
        await date_input.click(force=True)
        await asyncio.sleep(1)
        
        # Capturar screenshot e HTML dos modais/portais
        await page.screenshot(path="storage/calendar_debug.png")
        html = await page.evaluate('''() => {
            const portals = [...document.querySelectorAll('div[data-floating-ui-portal], div[class*="calendar"], div[class*="portal"], div[class*="popover"]')];
            return portals.map(p => p.outerHTML).join('\\n--- PORTAL ---\\n');
        }''')
        with open("storage/calendar_portals.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Salvo HTML dos portais e storage/calendar_debug.png")
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(inspect_calendar_html())
