import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager

async def test_date_time():
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
        
        # Aguardar formulário
        await asyncio.sleep(4)
        
        # Descartar qualquer modal inicial
        await page.evaluate('''() => {
            for (const b of document.querySelectorAll('button')) {
                const t = b.textContent.trim().toLowerCase();
                if (['ativar', 'entendi', 'cancelar', 'got it'].includes(t)) b.click();
            }
        }''')
        
        # Clicar no rádio Agendar
        print("Clicando no rádio Agendar...", flush=True)
        radio = page.locator('input[name="postSchedule"][value="schedule"]')
        await radio.click(force=True)
        await asyncio.sleep(1)
        
        # Clicar em Permitir no modal
        print("Descartando modal Permitir...", flush=True)
        await page.evaluate('''() => {
            for (const b of document.querySelectorAll('button')) {
                const t = b.textContent.trim().toLowerCase();
                if (['permitir', 'allow'].includes(t)) b.click();
            }
        }''')
        await asyncio.sleep(1)
        
        # Listar todos os inputs e seus atributos
        inputs_info = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('input')).map((i, idx) => ({
                idx,
                type: i.type,
                name: i.name,
                placeholder: i.placeholder,
                value: i.value,
                className: i.className,
                ariaLabel: i.getAttribute('aria-label'),
                rect: i.getBoundingClientRect()
            })).filter(i => i.rect.width > 0 && i.rect.height > 0);
        }''')
        print("Inputs visíveis:", inputs_info, flush=True)
        
        # Screenshot
        await page.screenshot(path="storage/test_schedule_inputs.png")
        print("Screenshot salvo em storage/test_schedule_inputs.png", flush=True)
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(test_date_time())
