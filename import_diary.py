"""
Import all diary entries to Hindsight life-mentor bank.
Each diary = one doc, doc_id = original filename (no extension).
"""

import os, re, glob, httpx, time
from pathlib import Path

API_BASE = "http://localhost:8888"
BANK_ID = "life-mentor"
DIARY_ROOT = Path("D:/Diary/diary/Diary")
YEAR = 2017
MONTHS_FILTER = None  # All months
# For 2025, set YEAR=2025 and MONTHS_FILTER=None


def parse_filename(filename: str):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-([A-Za-z]+)\.md$", filename)
    if not m:
        return None
    y, mo, d, dow = m.groups()
    return (f"{y}-{mo}-{d}", dow, f"{y}-{mo}-{d}T09:00:00Z",
            f"{y}-{mo}", filename.replace(".md", ""), mo)


def read_content(path: Path) -> str | None:
    try:
        content = Path(path).read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        return content.strip()
    except Exception as e:
        print(f"  Error reading {path}: {e}")
        return None


def get_files(year: int, months: list[str] | None) -> list[Path]:
    """Get sorted diary files for given year/months."""
    diary_dir = DIARY_ROOT / f"Diary-{year}"
    if not diary_dir.exists():
        print(f"Directory not found: {diary_dir}")
        return []

    all_files = []
    for f in sorted(diary_dir.glob("*.md")):
        parsed = parse_filename(f.name)
        if not parsed:
            continue
        _, _, _, _, _, mo = parsed  # mo is 2-digit month
        if months is None or mo in months:
            all_files.append(f)
    return all_files


def import_month(files: list[Path]) -> dict:
    """Import diary files list, one by one."""
    if not files:
        return {"imported": 0, "errors": [], "doc_ids": []}

    first = parse_filename(files[0].name)
    last = parse_filename(files[-1].name)
    label = f"{first[0]} ~ {last[0]}" if first and last else f"{len(files)} files"

    success = 0
    errors = []
    doc_ids = []
    total_t = 9999  # Will be set properly

    print(f"\n{'='*60}")
    print(f"Importing {len(files)} diaries: {label}")
    print(f"{'='*60}")

    with httpx.Client(timeout=300.0) as client:
        for i, file_path in enumerate(files, 1):
            filename = file_path.name
            parsed = parse_filename(filename)
            if not parsed:
                print(f"  [{i}] SKIP: bad filename: {filename}")
                continue

            date_str, dow, ts, month_label, doc_id, mo = parsed
            content = read_content(file_path)
            if not content:
                print(f"  [{i}] SKIP: empty: {filename}")
                continue

            doc_ids.append(doc_id)
            item = {
                "content": content,
                "context": "personal-diary",
                "document_id": doc_id,
                "timestamp": ts,
                "tags": [f"diary:{month_label}", f"date:{date_str}", f"weekday:{dow}"],
            }

            try:
                resp = client.post(
                    f"{API_BASE}/v1/default/banks/{BANK_ID}/memories",
                    json={"items": [item]},
                )
                resp.raise_for_status()
                r = resp.json()
                success += 1
                usage = r.get("usage", {}) or {}
                tk = usage.get("total_tokens", 0)
                print(f"  [{i}/{len(files)}] OK: {date_str} ({tk} tokens)", flush=True)
            except Exception as e:
                errors.append(f"{filename}: {e}")
                print(f"  [{i}/{len(files)}] ERROR: {filename}: {e}", flush=True)

    print(f"{'='*60}")
    print(f"Subtotal: {success}/{len(files)} imported", flush=True)
    return {"imported": success, "total": len(files), "doc_ids": doc_ids, "errors": errors}


def trigger_consolidation():
    """Trigger bank-level consolidation."""
    print(f"\n{'='*60}")
    print("Triggering bank-level consolidation (observation synthesis)...")
    print(f"{'='*60}")
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{API_BASE}/v1/default/banks/{BANK_ID}/consolidate",
                json={"scope": "bank", "types": ["world", "experience"]},
            )
            resp.raise_for_status()
            result = resp.json()
            print(f"Consolidation queued: operation_id={result.get('operation_id')}")
            return True
    except Exception as e:
        print(f"Consolidation error: {e}")
        return False


def main():
    year = YEAR
    months = MONTHS_FILTER

    files = get_files(year, months)
    if not files:
        print(f"No diary files found for year={year}, months={months}")
        return

    print(f"\n{'#'*60}")
    print(f"# Hindsight Diary Import")
    print(f"# Bank: {BANK_ID}")
    print(f"# Year: {year}, Months: {months or 'ALL'}")
    print(f"# Total files: {len(files)}")
    print(f"{'#'*60}")

    # Group by month for display
    from collections import OrderedDict
    month_groups = OrderedDict()
    for f in files:
        parsed = parse_filename(f.name)
        if parsed:
            month_label = parsed[3]
            if month_label not in month_groups:
                month_groups[month_label] = []
            month_groups[month_label].append(f)

    print(f"\nMonthly breakdown:")
    for ml, flist in month_groups.items():
        print(f"  {ml}: {len(flist)} files")
    print(f"  TOTAL: {len(files)} files\n")

    # Import all files
    start = time.time()
    result = import_month(files)
    elapsed = time.time() - start

    print(f"\n{'#'*60}")
    print(f"Import Summary")
    print(f"{'#'*60}")
    print(f"  Success: {result['imported']}/{result['total']}")
    print(f"  Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    if result["errors"]:
        print(f"  Errors: {len(result['errors'])}")
        for e in result["errors"][:5]:
            print(f"    - {e}")

    # Trigger consolidation
    trigger_consolidation()

    print(f"\nDone! Check http://localhost:9999 for the dashboard.")


if __name__ == "__main__":
    main()
