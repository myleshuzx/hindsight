"""
Test importing a single 2017 diary entry and checking the results.
"""
import httpx, json, time
from pathlib import Path

API = "http://localhost:8888"
BANK = "life-mentor"
TEST_DOC_ID = "test-2017-01-01-v2"

# Step 1: Read the diary content
f = Path("D:/Diary/diary/Diary/Diary-2017/2017-01-01-Sunday.md")
content = f.read_text(encoding="utf-8")
if content.startswith("---"):
    parts = content.split("---", 2)
    if len(parts) >= 3:
        content = parts[2].strip()

print(f"=== 日记内容 ({len(content)} chars) ===")
print(content[:200])
print("...")
print()

# Step 2: Retain the diary (WITHOUT tags, as user requested)
client = httpx.Client(timeout=300.0)

print("=== Step 1: Retain ===")
resp = client.post(f"{API}/v1/default/banks/{BANK}/memories", json={
    "items": [{
        "content": content,
        "document_id": TEST_DOC_ID,
        "timestamp": "2017-01-01T09:00:00Z",
        "context": "personal-diary",
    }]
})
print(f"Status: {resp.status_code}")
result = resp.json()
print(json.dumps(result, indent=2, ensure_ascii=False)[:500])
print()

# Step 3: Wait a bit for background LLM processing, then check
print("=== Step 2: Wait 15s for background processing ===")
time.sleep(15)

print("=== Step 3: Recall the diary ===")
recall = client.post(f"{API}/v1/default/banks/{BANK}/memories/recall", json={
    "query": "2017 元旦 摄影",
    "types": ["world", "experience"],
    "budget": "high",
    "max_tokens": 4096,
})
r_data = recall.json()
results = r_data.get("results", [])
print(f"Total recall results: {len(results)}")

# Look for our test document
found = [r for r in results if r.get("document_id") == TEST_DOC_ID]
print(f"Results for test doc: {len(found)}")
for r in found:
    print(f"  type={r['type']}")
    print(f"  text={r['text'][:150]}")
    print(f"  tags={r.get('tags', [])}")
    print(f"  source_fact_ids={r.get('source_fact_ids')}")
    print()

if not found:
    print("Test doc NOT found in recall results. Checking all results...")
    for r in results[:5]:
        print(f"  [{r.get('type')}] doc={r.get('document_id')} tags={r.get('tags', [])[:2]}")

# Step 4: Check if consolidation is pending
print("=== Step 4: Check recent operations ===")
ops = client.get(f"{API}/v1/default/banks/{BANK}/operations?limit=3")
ops_data = ops.json()
for op in ops_data.get("operations", [])[:3]:
    print(f"  {op['task_type']}: {op['status']} created={op['created_at'][:19]}")

# Step 5: Clean up - delete the test
print("=== Step 5: Delete test doc ===")
# No delete API available, skip
print("Done")
