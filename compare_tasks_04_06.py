import asyncio
import hashlib
import os
import aiohttp
from pathlib import Path

# URLs diretas de download dos arquivos no Google Drive
# File 04: 1uB3JkwQgGV4o9BWTPTmNXtc4EqsvZAix (TikTok)
# File 06: 1pIgfXH0heiBCbOEcx4Xmgx1gu_gHNd_e (YouTube)

TEMP_DIR = Path(r"C:\Users\Vini\.gemini\antigravity\brain\5eb108eb-e384-4b8d-92be-79be5c417116\checksum_audit")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    {
        "task": "Tarefa 04 (TikTok)",
        "file_id": "1uB3JkwQgGV4o9BWTPTmNXtc4EqsvZAix",
        "name": "rmn.ftbl1_008_7667487423957421334_task04.mp4",
        "save_path": TEMP_DIR / "task04.mp4"
    },
    {
        "task": "Tarefa 06 (YouTube)",
        "file_id": "1pIgfXH0heiBCbOEcx4Xmgx1gu_gHNd_e",
        "name": "rmn.ftbl1_008_7667487423957421334_task06.mp4",
        "save_path": TEMP_DIR / "task06.mp4"
    }
]

async def download_drive_file(session, file_id, dest_path):
    # Google drive direct export/download URL
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
            # Fallback to standard url
            url2 = f"https://drive.google.com/uc?export=download&id={file_id}"
            async with session.get(url2) as resp2:
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = await resp2.content.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                return True

def compute_md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()

async def main():
    async with aiohttp.ClientSession() as session:
        for item in FILES:
            print(f"Downloading {item['task']} (ID: {item['file_id']})...")
            await download_drive_file(session, item['file_id'], item['save_path'])
            size = os.path.getsize(item['save_path'])
            md5 = compute_md5(item['save_path'])
            item['size_bytes'] = size
            item['md5'] = md5
            print(f"{item['task']} -> Size: {size} bytes | MD5: {md5}")

    t4 = FILES[0]
    t6 = FILES[1]
    is_identical = (t4['md5'] == t6['md5'])
    print("\n--- RESULTADO DA COMPARAÇÃO ---")
    print(f"Mesmo tamanho em bytes? {t4['size_bytes'] == t6['size_bytes']} ({t4['size_bytes']} vs {t6['size_bytes']})")
    print(f"Mesmo MD5 Checksum? {is_identical}")
    print(f"Checksum Tarefa 04: {t4['md5']}")
    print(f"Checksum Tarefa 06: {t6['md5']}")
    if is_identical:
        print("ALERTA: Os dois arquivos são CÓPIAS BINÁRIAS EXATAS (mesmo vídeo duplicado em duas pastas diferentes com IDs distintos no Google Drive).")
    else:
        print("CONFIRMADO: Os arquivos são vídeos diferentes.")

if __name__ == "__main__":
    asyncio.run(main())
