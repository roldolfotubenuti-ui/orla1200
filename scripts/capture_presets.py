import asyncio
from playwright.async_api import async_playwright

async def capture_presets():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto("http://localhost:3005", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        presets = [
            "mesa1_closeup",
            "mesa2_closeup",
            "mesa3_closeup",
            "mesa4_closeup",
            "mesa5_closeup",
            "mesa6_closeup",
        ]

        for preset in presets:
            await page.evaluate(f"window.__tksSetCameraPreset('{preset}')")
            await asyncio.sleep(1.0)
            await page.screenshot(path=f"storage/preset_{preset}.png")
            print(f"Captured {preset}")

        await browser.close()

asyncio.run(capture_presets())
