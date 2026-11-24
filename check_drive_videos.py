import urllib.request
import json

url = "http://localhost:3005/api/drive/folders?refresh=1"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())

print("Google Drive API State:")
folders = data.get("folders", {})
for key, f in folders.items():
    print(f"- {f['name']} ({key}): {f['videoCount']} vídeo(s) detectados. URL: {f['folderUrl']}")
    if f.get("videos"):
        for v in f["videos"]:
            print(f"    * {v.get('name')} (id: {v.get('id')})")
