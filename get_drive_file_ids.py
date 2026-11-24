import asyncio
import re
from playwright.async_api import async_playwright

FOLDERS = [
    ("Instagram", "dept_instagram", "1_EkgBi7YQkLha92WDJk_UJkWalPZtBhi"),
    ("Mercado Livre", "dept_mercadolivre", "1BIT-D_0rTUKuQeEQLooNnl89gzsostjs"),
    ("Shorts", "dept_shorts", "1E8ljEe1tzaTeurNDkGXowMmEEh_21M6w"),
    ("TikTok", "dept_tiktok", "1o0L9RN-yzxzzrVbBTY8H8dU7PcHA4Sgi"),
    ("TikTok Shop", "dept_tiktokshop", "15DSKr0vn2fV3n-3FwI-m_4HR8XZI1hEP"),
    ("YouTube", "dept_youtube", "1gjgMgqK0488Q2xm1ZOipQSC73XLI7rDr")
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        results = []
        for name, dept_id, folder_id in FOLDERS:
            url = f"https://drive.google.com/drive/folders/{folder_id}"
            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)
            content = await page.content()
            
            # Match data-id or drive file IDs in html
            # Usually files have links like /file/d/(fileID)/view or data-id="fileID"
            file_ids = re.findall(r'/file/d/([a-zA-Z0-9_-]{25,})', content)
            if not file_ids:
                file_ids = re.findall(r'data-id="([a-zA-Z0-9_-]{25,})"', content)
                
            # Filter out folder_id
            real_file_ids = [fid for fid in file_ids if fid != folder_id]
            file_id = real_file_ids[0] if real_file_ids else None
            
            # File name from html
            fn_matches = re.findall(r'([^"\'<>\n]+\.mp4)', content)
            fn = fn_matches[0] if fn_matches else "video.mp4"
            
            results.append({
                "dept": name,
                "dept_id": dept_id,
                "folder_id": folder_id,
                "file_name": fn,
                "real_file_id": file_id
            })
            print(f"Found in {name}: {fn} -> FileID: {file_id}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
