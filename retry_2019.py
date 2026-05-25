import httpx
c = httpx.Client(timeout=180.0)

files = [
    ("2019-09-25-Wednesday.md", "2019-09-25T09:00:00Z", "2019-09"),
    ("2019-10-09-Wednesday.md", "2019-10-09T09:00:00Z", "2019-10"),
]
for f, ts, tag in files:
    doc_id = f.replace(".md","")
    content = open(f"D:/Diary/diary/Diary/Diary-2019/{f}", encoding="utf-8").read()
    if content.startswith("---"):
        p = content.split("---", 2)
        if len(p) >= 3: content = p[2].strip()
    r = c.post("http://localhost:8888/v1/default/banks/life-mentor/memories", json={"items":[{
        "content": content, "document_id": doc_id, "timestamp": ts,
        "context": "personal-diary", "tags": [f"diary:{tag}"]
    }]})
    print(f'{"OK" if r.status_code==200 else "FAIL"} {doc_id}')
