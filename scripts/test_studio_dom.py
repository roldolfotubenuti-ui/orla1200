import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser_runtime import BrowserRuntime
from core.account_manager import AccountManager
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

async def dismiss_all_portals(page):
    for attempt in range(5):
        has_portal = await page.evaluate('''() => {
            const portal = document.querySelector('div[data-floating-ui-portal], div.TUXModal-overlay, div[class*="common-modal"]');
            if (!portal) return false;
            const buttons = Array.from(document.querySelectorAll('button'));
            const actionBtn = buttons.find(b => {
                const t = b.textContent.trim().toLowerCase();
                return t === 'permitir' || t === 'allow' || t === 'ativar' || t === 'entendi' || t === 'cancelar';
            });
            if (actionBtn) {
                actionBtn.click();
                return actionBtn.textContent.trim();
            }
            return false;
        }''')
        print(f"Portal dismissal check {attempt}: {has_portal}", flush=True)
        if not has_portal:
            break
        await asyncio.sleep(1)

async def test():
    mgr = AccountManager()
    accs = mgr.list_accounts()
    acc = next(a for a in accs if a.username == 'valueini')
    print('Testing account:', acc.username)
    
    runtime = BrowserRuntime()
    await runtime.start()
    try:
        context, page = await runtime.get_or_create_account_session(acc.account_id, mgr)
        url = 'https://www.tiktok.com/tiktokstudio/upload?from=webapp'
        print('Navigating to', url, flush=True)
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(4)
        
        file_input = await page.wait_for_selector("input[type='file']", state="attached", timeout=15000)
        video_path = r"E:\ORLA1200\2\rmn.ftbl1_012_7689210188892654851.mp4"
        print('Attaching file:', video_path)
        await file_input.set_input_files(video_path)
        
        for i in range(1, 15):
            await asyncio.sleep(2)
            await page.screenshot(path=f'storage/diag_2_upload_{i*2}s.png')
            
            # Extract detailed elements
            state = await page.evaluate('''() => {
                const textNodes = [...document.querySelectorAll('span, p, div, label, button')]
                    .map(e => e.innerText ? e.innerText.trim() : '')
                    .filter(t => t.length > 0 && t.length < 80);
                
                const inputs = [...document.querySelectorAll('input')].map(i => ({
                    type: i.type,
                    value: i.value,
                    placeholder: i.placeholder,
                    name: i.name,
                    role: i.getAttribute('role'),
                    checked: i.checked,
                    id: i.id,
                    className: i.className
                }));
                
                const buttons = [...document.querySelectorAll('button')].map(b => ({
                    text: b.innerText ? b.innerText.trim() : '',
                    disabled: b.disabled,
                    className: b.className,
                    dataE2e: b.getAttribute('data-e2e')
                }));
                
                return { textNodes: textNodes.slice(0, 40), inputs, buttons };
            }''')
            
            # Look for upload completion indicators
            texts = [t for t in state['textNodes']]
            print(f"[{i*2}s] Buttons: {[b['text'] for b in state['buttons'] if b['text']]}")
            print(f"[{i*2}s] Inputs: {state['inputs']}")
            # Check for scheduling or post button
            post_btns = [b for b in state['buttons'] if any(k in b['text'].lower() for k in ['publicar', 'programar', 'post', 'schedule'])]
            if post_btns:
                print(f"[{i*2}s] FOUND ACTION BUTTONS: {post_btns}")
            
            # Print sample texts
            sample_t = [t for t in texts if any(w in t.lower() for w in ['carreg', 'upload', '100', '%', 'mb', 'conclu', 'program', 'public'])]
            print(f"[{i*2}s] Upload/Status texts: {sample_t}")
            
        # Dismiss any initial modal
        await dismiss_all_portals(page)
        
        print("Attempting to click Schedule radio...", flush=True)
        radio = page.locator('input[name="postSchedule"][value="schedule"]')
        await radio.click(force=True)
        await asyncio.sleep(1)
        
        # Dismiss 'Permitir' modal if it popped up
        await dismiss_all_portals(page)
        await asyncio.sleep(1)
        
        # Test setting date
        print("Testing date input click...", flush=True)
        date_input = page.locator("input[class*='TUXTextInputCore-input']").nth(1)
        cur_date_val = await date_input.input_value()
        print(f"Current date input value: {cur_date_val}", flush=True)
        
        await date_input.click(force=True)
        await asyncio.sleep(1)
        await page.screenshot(path='storage/diag_7_calendar_opened.png')
        
        # Check calendar DOM elements
        cal_info = await page.evaluate('''() => {
            const divs = [...document.querySelectorAll('div, span, table')].filter(el => {
                const c = (el.className || '').toString();
                return c.includes('calendar') || c.includes('date') || c.includes('picker') || c.includes('month');
            }).map(el => ({
                tag: el.tagName,
                className: (el.className || '').toString().slice(0, 80),
                text: el.innerText ? el.innerText.trim().slice(0, 50) : ''
            }));
            const days = [...document.querySelectorAll('span, div')].filter(el => {
                const c = (el.className || '').toString();
                return c.includes('day') && el.innerText && el.innerText.trim() === '24';
            }).map(el => ({ className: el.className, text: el.innerText }));
            return { divs: divs.slice(0, 10), days };
        }''')
        print("Calendar DOM info:", cal_info, flush=True)
        
        # Click day 24
        clicked_day = await page.evaluate('''() => {
            const spans = [...document.querySelectorAll('span, div')].filter(el => {
                const c = (el.className || '').toString().toLowerCase();
                return (c.includes('day') || c.includes('cell') || c.includes('date')) && el.innerText && el.innerText.trim() === '24';
            });
            if (spans.length > 0) {
                spans[0].click();
                return true;
            }
            return false;
        }''')
        print(f"Clicked day 24: {clicked_day}", flush=True)
        await asyncio.sleep(1)
        new_date_val = await date_input.input_value()
        print(f"New date input value: {new_date_val}", flush=True)
    finally:
        await runtime.stop()

if __name__ == '__main__':
    asyncio.run(test())
