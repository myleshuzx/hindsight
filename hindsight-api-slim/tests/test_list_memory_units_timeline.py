from datetime import datetime, timezone
from uuid import uuid4

import pytest

from hindsight_api.engine.db_utils import acquire_with_retry
from hindsight_api.engine.memory_engine import fq_table


@pytest.mark.asyncio
async def test_list_memory_units_timeline_sort_uses_event_time_fallbacks(memory, request_context):
    bank_id = f"timeline-list-{uuid4().hex[:8]}"
    rows = [
        (
            "occurred wins over newer mention",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        (
            "mentioned used without occurred",
            None,
            datetime(2021, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
        ),
        (
            "created fallback without event date",
            None,
            None,
            datetime(2022, 1, 1, tzinfo=timezone.utc),
        ),
        (
            "later occurred",
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            None,
            datetime(2026, 1, 3, tzinfo=timezone.utc),
        ),
    ]

    backend = await memory._get_backend()
    async with acquire_with_retry(backend) as conn:
        try:
            for text, occurred_start, mentioned_at, created_at in rows:
                await conn.execute(
                    f"""
                    INSERT INTO {fq_table("memory_units")}
                        (bank_id, text, event_date, fact_type, occurred_start, mentioned_at, created_at)
                    VALUES ($1, $2, $3, 'world', $4, $5, $6)
                    """,
                    bank_id,
                    text,
                    created_at,
                    occurred_start,
                    mentioned_at,
                    created_at,
                )

            timeline = await memory.list_memory_units(
                bank_id=bank_id,
                sort="timeline",
                order="asc",
                limit=10,
                request_context=request_context,
            )
            assert [item["text"] for item in timeline["items"]] == [row[0] for row in rows]
            assert [item["date_source"] for item in timeline["items"]] == [
                "occurred_start",
                "mentioned_at",
                "created_at",
                "occurred_start",
            ]
            assert [item["has_event_date"] for item in timeline["items"]] == [True, True, False, True]
            assert timeline["items"][1]["timeline_at"].startswith("2021-01-01")

            recent = await memory.list_memory_units(bank_id=bank_id, limit=10, request_context=request_context)
            assert [item["text"] for item in recent["items"][:2]] == [
                "occurred wins over newer mention",
                "mentioned used without occurred",
            ]
        finally:
            await conn.execute(f"DELETE FROM {fq_table('memory_units')} WHERE bank_id = $1", bank_id)
