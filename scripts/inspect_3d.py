import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto("http://localhost:3005", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        # Obter dados dos funcionários
        data = await page.evaluate("""() => {
            const employees = window.__tksEmployees || {};
            const res = {};
            for (const [k, v] of Object.entries(employees)) {
                res[k] = {
                    id: v.employeeId,
                    state: v.state,
                    pos: v.pos,
                };
            }
            return {
                employees: res,
                mesa1State: window.__getMesa1EmployeeState ? window.__getMesa1EmployeeState() : null,
                mesa2State: window.__getMesa2EmployeeState ? window.__getMesa2EmployeeState() : null,
                mesa3State: window.__getMesa3EmployeeState ? window.__getMesa3EmployeeState() : null,
            };
        }""")
        print("Dados:", data)
        await page.screenshot(path="storage/inspect_office_3d.png")
        await browser.close()

asyncio.run(inspect())
