import asyncio
from playwright.async_api import async_playwright

async def capture_closeups():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1600, 'height': 900})
        await page.goto('http://localhost:3005')
        await page.wait_for_timeout(2500)
        
        presets = [
            'overview_isometric',
            'mesa1_closeup',
            'mesa2_closeup',
            'mesa3_closeup',
            'mesa4_closeup',
            'mesa5_closeup',
            'mesa6_closeup',
        ]
        
        for preset in presets:
            await page.evaluate(f"window.__tksSetCameraPreset && window.__tksSetCameraPreset('{preset}')")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f'audit_preset_{preset}.png')
            print(f'Captured preset: {preset}')
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(capture_closeups())
