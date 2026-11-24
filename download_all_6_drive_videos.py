import asyncio
import os
import aiohttp
from pathlib import Path

VIDEOS_DIR = Path(r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\test_batch_videos")
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

DRIVE_FILES = [
    {
        "dept_id": "dept_instagram",
        "file_id": "16HAfri4cs0tplMvSdxGiB2x6K78uNxPJ",
        "filename": "rmn.ftbl1_009_7689492826450660630.mp4"
    },
    {
        "dept_id": "dept_mercadolivre",
        "file_id": "1Y3mG4t7EwLTAJAJEoLHFLKWB8tV_lw8n",
        "filename": "rmn.ftbl1_011_7686592084618349846.mp4"
    },
    {
        "dept_id": "dept_shorts",
        "file_id": "1XHdM7ygKdhRtHbzXluhuqMtBxzzpRr03",
        "filename": "rmn.ftbl1_006_7686174262813527318.mp4"
    },
    {
        "dept_id": "dept_tiktok",
        "file_id": "1uB3JkwQgGV4o9BWTPTmNXtc4EqsvZAix",
        "filename": "rmn.ftbl1_008_7667487423957421334.mp4"
    },
    {
        "dept_id": "dept_tiktokshop",
        "file_id": "1L_ZcPuRewaf5s8iamSh_IaOTfAHjq-f4",
        "filename": "rmn.ftbl1_018_7703622500814425366.mp4"
    },
    {
        "dept_id": "dept_youtube",
        "file_id": "1pIgfXH0heiBCbOEcx4Xmgx1gu_gHNd_e",
        "filename": "rmn.ftbl1_008_7667487423957421334.mp4"
    }
]

async def download_file(session, file_id, dest_path):
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&authuser=0&confirm=t"
    async with session.get(url) as resp:
        if resp.status == 200:
            with open(dest_path, "wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return True
        else:
            url2 = f"https://drive.google.com/uc?export=download&id={file_id}"
            async with session.get(url2) as resp2:
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = await resp2.content.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                return True

async def main():
    async with aiohttp.ClientSession() as session:
        for idx, item in enumerate(DRIVE_FILES, 1):
            dest = VIDEOS_DIR / f"dept_{idx:02d}_{item['filename']}"
            item['local_path'] = str(dest)
            if dest.exists() and dest.stat().st_size > 1000000:
                print(f"[{idx}/6] Already exists: {dest.name} ({dest.stat().st_size} bytes)")
                continue
            print(f"[{idx}/6] Downloading {item['dept_id']} -> {dest.name}...")
            await download_file(session, item['file_id'], dest)
            size = dest.stat().st_size
            print(f"[{idx}/6] Downloaded {dest.name}: {size} bytes")

    print("\nAll 6 videos ready locally in:", VIDEOS_DIR)

if __name__ == "__main__":
    asyncio.run(main())
