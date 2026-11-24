import asyncio
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = r"C:\Users\Vini\.gemini\antigravity\brain\5eb108eb-e384-4b8d-92be-79be5c417116\prevalidation_office"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        await page.goto("http://localhost:3005", wait_until="networkidle")
        await asyncio.sleep(4)
        
        # 1. Full view
        p1 = os.path.join(OUTPUT_DIR, "01_office_drawers_status.png")
        await page.screenshot(path=p1)
        print("Captured full view:", p1)
        
        # 2. Focus on cabinet if menu exists
        menu_btn = await page.query_selector("button:has-text('Menu')")
        if menu_btn:
            await menu_btn.click()
            await asyncio.sleep(1)
            cab_btn = await page.query_selector("button:has-text('Armário'), button:has-text('Gavetas')")
            if cab_btn:
                await cab_btn.click()
                await asyncio.sleep(2)
                p2 = os.path.join(OUTPUT_DIR, "02_cabinet_focus.png")
                await page.screenshot(path=p2)
                print("Captured cabinet focus:", p2)
                
        # Emit employee fetch events via bridge if needed
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
