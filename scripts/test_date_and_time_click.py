import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager

async def test_date_and_time_click():
    mgr = AccountManager()
    acc = next(a for a in mgr.list_accounts() if a.username == 'valueini')
    runtime = BrowserRuntime()
    await runtime.start()
    try:
        context, page = await runtime.get_or_create_account_session(acc.account_id, mgr)
        await page.goto('https://www.tiktok.com/tiktokstudio/upload?from=webapp', wait_until='domcontentloaded')
        await asyncio.sleep(4)
        file_input = await page.wait_for_selector("input[type='file']", state="attached")
        await file_input.set_input_files(r"E:\ORLA1200\2\rmn.ftbl1_012_7689210188892654851.mp4")
        await asyncio.sleep(4)
        
        # 1. Clicar em Programar
        radio = page.locator('input[name="postSchedule"][value="schedule"]')
        await radio.click(force=True)
        await asyncio.sleep(1)
        
        # 2. Descartar modal "Permitir"
        await page.evaluate('''() => {
            for (const b of document.querySelectorAll('button')) {
                if (['permitir', 'allow', 'ativar'].includes(b.textContent.trim().toLowerCase())) {
                    b.click();
                }
            }
        }''')
        await asyncio.sleep(1)
        
        # 3. Clicar no campo de data (contém 'nov' ou ano '2026' ou 'de')
        print("Clicando no seletor de data...", flush=True)
        date_box = page.locator("div[class*='Select']:has-text('nov'), div[class*='select']:has-text('2026'), div:has-text('23 de nov')").last
        await date_box.click(force=True)
        await asyncio.sleep(1)
        await page.screenshot(path="storage/test_step1_date_opened.png")
        
        # Clicar no dia 24
        print("Clicando no dia 24...", flush=True)
        day_24 = await page.evaluate('''() => {
            const cells = Array.from(document.querySelectorAll('span, div')).filter(el => {
                return el.innerText && el.innerText.trim() === '24';
            });
            if (cells.length > 0) {
                cells[cells.length - 1].click();
                return true;
            }
            return false;
        }''')
        print("Dia 24 clicado:", day_24, flush=True)
        await asyncio.sleep(1)
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        
        # 4. Clicar no campo de horário (contém ':')
        print("Clicando no seletor de horário...", flush=True)
        time_box = page.locator("div[class*='Select']:has-text(':'), div[class*='select']:has-text(':')").first
        await time_box.click(force=True)
        await asyncio.sleep(1)
        await page.screenshot(path="storage/test_step2_time_opened.png")
        
        # Selecionar 18:00
        print("Selecionando 18:00...", flush=True)
        time_res = await page.evaluate('''() => {
            const lists = Array.from(document.querySelectorAll('div[class*="timepicker-option-list"], div[class*="option-list"], ul, div[class*="Select__list"]'));
            let hOk = false, mOk = false;
            for (const list of lists) {
                const items = Array.from(list.querySelectorAll('div, li, span'));
                const hItem = items.find(el => el.innerText && el.innerText.trim() === '18');
                if (hItem) { hItem.click(); hOk = true; }
                const mItem = items.find(el => el.innerText && el.innerText.trim() === '00');
                if (mItem) { mItem.click(); mOk = true; }
            }
            return { hOk, mOk };
        }''')
        print("Horário selecionado:", time_res, flush=True)
        await asyncio.sleep(1)
        await page.keyboard.press("Escape")
        await asyncio.sleep(1)
        
        # Tirar screenshot final com data e horário configurados
        await page.screenshot(path="storage/test_step3_schedule_ready.png")
        print("Screenshot final salvo em storage/test_step3_schedule_ready.png", flush=True)
        
        # Verificar estado do botão Agendar
        btn_info = await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(btn => ['agendar', 'programar', 'schedule', 'publicar'].includes(btn.textContent.trim().toLowerCase()));
            return b ? { text: b.textContent.trim(), disabled: b.disabled } : null;
        }''')
        print("Estado do botão Agendar:", btn_info, flush=True)
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(test_date_and_time_click())
