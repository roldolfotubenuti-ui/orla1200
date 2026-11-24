import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager

async def main():
    mgr = AccountManager()
    accs = mgr.list_accounts()
    acc = next(a for a in accs if a.username == 'valueini')
    
    runtime = BrowserRuntime()
    await runtime.start(headless=True)
    try:
        context, page = await runtime.get_or_create_account_session(acc.account_id, mgr)
        url = 'https://www.tiktok.com/tiktokstudio/upload?from=webapp'
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)
        
        file_input = await page.wait_for_selector("input[type='file']", state="attached", timeout=15000)
        video_path = r"E:\ORLA1200\2\rmn.ftbl1_027_7691404197928979734.mp4"
        await file_input.set_input_files(video_path)
        await asyncio.sleep(4)
        
        # Remove joyride
        await page.evaluate('''() => {
            document.querySelectorAll('#react-joyride-portal, .react-joyride__overlay, .react-joyride__tooltip').forEach(el => el.remove());
        }''')
        await asyncio.sleep(0.5)
        
        # Click label
        schedule_label = page.locator("label:has-text('Programar'), label:has-text('Schedule')").first
        await schedule_label.click(force=True)
        await asyncio.sleep(1.5)
        
        # Dismiss Allow modal if present
        await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(b => ['permitir', 'allow', 'ativar', 'entendi'].includes(b.textContent.trim().toLowerCase()));
            if (b) b.click();
        }''')
        await asyncio.sleep(1.5)
        
        # Open date trigger (index 0)
        await page.evaluate('''() => {
            const boxes = document.querySelectorAll('.scheduled-picker [role="combobox"]');
            if (boxes[0]) boxes[0].click();
        }''')
        await asyncio.sleep(1)
        
        # Dump HTML of calendar panel
        cal_panel_html = await page.evaluate('''() => {
            const panel = document.querySelector('.Picker__panel');
            return panel ? panel.outerHTML : "CALENDAR PANEL NOT FOUND";
        }''')
        with open("storage/calendar_panel.html", "w", encoding="utf-8") as f:
            f.write(cal_panel_html)
        print("Wrote storage/calendar_panel.html, length:", len(cal_panel_html))
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(main())
