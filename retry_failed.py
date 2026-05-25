import re, httpx, json
from pathlib import Path

files = [
    "D:/Diary/diary/Diary/Diary-2022/2022-08-09-Tuesday.md",
    "D:/Diary/diary/Diary/Diary-2022/2022-08-10-Wednesday.md",
    "D:/Diary/diary/Diary/Diary-2022/2022-08-11-Thursday.md",
]

with httpx.Client(timeout=180.0) as client:
    for fp in files:
        f = Path(fp)
        filename = f.name
        doc_id = filename.replace(".md", "")
        date_str = filename[:10]
        ts = f"{date_str}T09:00:00Z"

        content = f.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        item = {
            "content": content,
            "document_id": doc_id,
            "timestamp": ts,
            "context": "personal-diary",
            "tags": [f"diary:2022-08", f"date:{date_str}"],
        }

        resp = client.post("http://localhost:8888/v1/default/banks/life-mentor/memories", json={"items": [item]})
        r = resp.json()
        ok = r.get("success", False)
        tk = r.get("usage", {}).get("total_tokens", 0) if r.get("usage") else 0
        print(f"{'OK' if ok else 'FAIL'} {date_str} ({tk} tokens)")
