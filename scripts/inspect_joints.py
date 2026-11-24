import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto("http://localhost:3005", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Inspecionar objetos na cena Three.js
        debug_info = await page.evaluate("""() => {
            // Encontrar o canvas Three.js
            const canvas = document.querySelector('canvas');
            const fiberKey = Object.keys(canvas).find(k => k.startsWith('__reactFiber$'));
            if (!fiberKey) return { error: 'No fiber' };
            
            // Buscar na árvore Three.js via inspect dos hooks do window se disponível
            // Ou procurar os grupos dos personagens
            // Vamos checar __r3f se disponível
            return {
                width: canvas.width,
                height: canvas.height,
            };
        }""")
        print("Debug:", debug_info)

        # Tirar screenshots das mesas 1, 2, 3, 4, 5, 6 com zoom ou câmera
        # Vamos ver se podemos manipular a câmera via window
        await page.screenshot(path="storage/inspect_full_view.png")
        await browser.close()

asyncio.run(inspect())
