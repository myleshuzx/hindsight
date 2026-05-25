#!/usr/bin/env python3
"""
Import diary entries one by one for debugging.
"""

import os
import re
import glob
import json
import httpx
from pathlib import Path

API_BASE = "http://localhost:8888"
BANK_ID = "life-mentor"
DIARY_ROOT = Path("D:/Diary/diary/Diary")


def parse_diary_filename(filename: str):
    """Parse diary filename: YYYY-MM-DD-dddd.md"""
    pattern = r"^(\d{4})-(\d{2})-(\d{2})-([A-Za-z]+)\.md$"
    match = re.match(pattern, filename)
    if not match:
        return None
    year, month, day, day_of_week = match.groups()
    return (f"{year}-{month}-{day}", day_of_week, f"{year}-{month}-{day}T09:00:00Z")


def read_diary_content(file_path: Path) -> str:
    """Read diary file content, skip frontmatter."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()
    return content.strip()


def import_single_diary(client, bank_id: str, file_path: Path, session_id: str):
    """Import a single diary entry."""
    filename = os.path.basename(file_path)
    parsed = parse_diary_filename(filename)
    if not parsed:
        return None

    date_str, day_of_week, timestamp = parsed
    content = read_diary_content(file_path)

    item = {
        "content": content,
        "context": "personal-diary",
        "document_id": session_id,
        "timestamp": timestamp,
        "tags": [f"diary:2026-03", f"date:{date_str}"],
    }

    try:
        response = client.post(
            f"{API_BASE}/v1/default/banks/{bank_id}/memories",
            json={"items": [item]},
        )
        return response.json()
    except Exception as e:
        return {"error": str(e), "filename": filename}


def main():
    year, month = "2026", "03"
    diary_dir = DIARY_ROOT / f"Diary-{year}"
    pattern = f"*{year}-{month}-*.md"
    files = sorted(glob.glob(str(diary_dir / pattern)))

    session_id = f"diary-{year}-{month}"
    print(f"Importing {len(files)} diary files as session: {session_id}")

    with httpx.Client(timeout=180.0) as client:
        for i, file_path in enumerate(files[:5], 1):  # Test with first 5
            filename = os.path.basename(file_path)
            print(f"\n[{i}] Testing: {filename}")

            result = import_single_diary(client, BANK_ID, Path(file_path), session_id)

            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                print(f"  SUCCESS: {result.get('items_count', 0)} items imported")
                if result.get("usage"):
                    print(f"  Usage: {result['usage']}")


if __name__ == "__main__":
    main()