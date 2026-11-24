import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager

async def inspect_selects():
    mgr = AccountManager()
    acc = next(a for a in mgr.list_accounts() if a.username == 'valueini')
    runtime = BrowserRuntime()
    await runtime.start()
    try:
        context, page = await runtime.get_or_create_account_session(acc.account_id, mgr)
        await page.goto('https://www.tiktok.com/tiktokstudio/upload?from=webapp', wait_until='domcontentloaded')
        await asyncio.sleep(3)
        file_input = await page.wait_for_selector("input[type='file']", state="attached")
        await file_input.set_input_files(r"E:\ORLA1200\2\rmn.ftbl1_012_7689210188892654851.mp4")
        await asyncio.sleep(4)
        
        radio = page.locator('input[name="postSchedule"][value="schedule"]')
        await radio.click(force=True)
        await asyncio.sleep(1)
        
        # Permitir
        await page.evaluate('''() => {
            for (const b of document.querySelectorAll('button')) {
                if (b.textContent.trim().toLowerCase() === 'permitir') b.click();
            }
        }''')
        await asyncio.sleep(1)
        
        # Inspecionar containers na área "Quando publicar"
        elements = await page.evaluate('''() => {
            const results = [];
            // Procurar elementos próximos a 'Quando publicar'
            const all = Array.from(document.querySelectorAll('div, button, span'));
            for (const el of all) {
                const txt = el.innerText ? el.innerText.trim() : '';
                if (txt === '18:40' || txt.includes('23 de nov') || txt.includes('Horário local')) {
                    results.push({
                        tag: el.tagName,
                        className: el.className,
                        text: txt,
                        outerHTML: el.outerHTML.slice(0, 300)
                    });
                }
            }
            return results;
        }''')
        for e in elements[:10]:
            print(e)
            print('-'*40)
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(inspect_selects())
