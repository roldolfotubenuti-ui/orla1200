import asyncio
from playwright.async_api import async_playwright

async def capture_closeups():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto("http://localhost:3005", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Vamos usar a câmera ou mover a câmera para focar em cada mesa
        # Vamos verificar se podemos alterar a posição da câmera pelo Three.js
        # Se não, podemos injetar uma câmera temporária ou ajustar a posição
        cameras = [
            ("mesa1_closeup", [-3.85, 1.2, 4.2], [-3.85, 0.9, 2.0]),
            ("mesa2_closeup", [-0.25, 1.2, 4.2], [-0.25, 0.9, 2.0]),
            ("mesa6_closeup", [3.35, 1.2, 4.2], [3.35, 0.9, 2.0]),
            ("mesa5_closeup", [-3.85, 1.2, -0.2], [-3.85, 0.9, -2.5]),
            ("mesa4_closeup", [-0.25, 1.2, -0.2], [-0.25, 0.9, -2.5]),
            ("mesa3_closeup", [3.35, 1.2, -0.2], [3.35, 0.9, -2.5]),
        ]

        for name, eye, target in cameras:
            await page.evaluate(f"""([eye, target]) => {{
                // Encontrar a câmera do Three.js através do store ou canvas
                if (window.__setCameraForAudit) {{
                    window.__setCameraForAudit(eye, target);
                }}
            }}""", [eye, target])
            await asyncio.sleep(0.5)
            await page.screenshot(path=f"storage/{name}.png")

        await browser.close()

asyncio.run(capture_closeups())
