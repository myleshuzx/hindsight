"""Prompts for the consolidation engine."""

# Default mission when no bank-specific mission is set
_DEFAULT_MISSION = "Track every detail: names, numbers, dates, places, and relationships. Prefer specifics over abstractions, never generalise."

_LANGUAGE_AND_NAME_RULES = """Language and name preservation (always apply):

Determine the primary natural language of NEW FACTS.

For every creates[].text and updates[].text:
- Use the same primary natural language as the source facts.
- If source facts are Chinese, the observation text MUST be Chinese.
- Preserve personal names, place names, nicknames, organization names, and titles exactly as written in the source facts.
- Never transliterate Chinese names into pinyin.
- Never translate Chinese names, places, or nicknames into English.
- Preserve mixed-language technical terms such as OpenAI, GitHub, Docker, and Python exactly as written.
- Keep JSON field names, UUIDs, observation_id, source_fact_ids, creates, updates, and deletes exactly as specified."""

# Processing rules — always present regardless of mission
_PROCESSING_RULES = """Processing rules (always apply):

1. ONE OBSERVATION PER DISTINCT FACET: each observation tracks exactly one specific facet — a count ("has 3 items"), a named entity ("has a dog named Rex"), a relationship ("works at Google"), etc. Never merge different facets into one observation.

2. MATCH BY ENTITY/FACET, NOT TOPIC: when deciding whether to UPDATE vs CREATE, match on the specific entity or facet. "Sold item X" updates only the X observation. "Now has 5 items" updates only the count observation. Do not update observations about different entities just because they share a general topic.

3. STATE CHANGES — UPDATE CONCISELY: when a fact changes the state of something ("sold X", "X died", "moved to Y"), UPDATE the matching observation to reflect the current state. Include dates when available. Keep it concise — only information about THAT specific facet. Example: "User owned a dog named Rex who died on March 15, 2025". Do NOT pull in information from other observations — each observation stays focused on its own facet.

4. CASCADE TO ALL AFFECTED OBSERVATIONS: a state change may affect multiple observations. For example, if entity C is removed from a group, update BOTH the individual observation for C AND any list/group observation that includes C (remove C from the list while keeping all other members intact).

5. NO COMPUTATION: you do not have the full picture — never calculate, derive, or adjust numeric values. If the user says "I have 2 dogs" and then "I have a dog named Rex", do NOT update the count to 3 — you don't know if Rex is one of the 2 or a new one. If the user says "I sold X", do NOT decrement a count. Only update a count when the user explicitly states a new count. Synthesize and consolidate what was stated, but never do arithmetic or logical deductions.

6. SAME FACET → UPDATE, NOT CREATE: a new count supersedes the old count — UPDATE the existing count observation, don't create a second one. If there's an existing observation for the same specific facet, always UPDATE it rather than creating a duplicate.

7. PRESERVE HISTORY: observations that record significant events (sold, died, moved, changed) are important history — never DELETE them. Only delete an observation when it is restated identically or truly meaningless. Be very conservative with deletes.

8. RESOLVE REFERENCES: when a new fact provides a concrete value for a vague placeholder in an existing observation (e.g., "home country" → "Sweden"), UPDATE to embed the resolved value.

9. NEVER merge observations about different people or unrelated topics."""

# Data section — format placeholders {facts_text} and {observations_text} are substituted at call time
_BATCH_DATA_SECTION = """
NEW FACTS:
{facts_text}

EXISTING OBSERVATIONS (JSON array, pooled from recalls across all facts above):
{observations_text}

Each observation includes:
- id: unique identifier for updating
- text: the observation content
- proof_count: number of supporting memories
- occurred_start/occurred_end: temporal range of source facts
- source_memories: array of supporting facts with their text and dates

Compare the facts against existing observations:
- Same facet as an existing observation → UPDATE it (observation_id + source_fact_ids)
- New facet with durable knowledge → CREATE a new observation (source_fact_ids)
- Cross-reference facts within the batch: a later fact may resolve a vague reference in an earlier one
- Purely ephemeral facts → omit them unless the MISSION above explicitly targets such data (e.g. timestamped events, session state, screen content)"""

# Output format — JSON braces escaped as {{ }} so .format() leaves them literal
_BATCH_OUTPUT_FORMAT = """
Output a JSON object with three arrays.

## EXAMPLE

Input facts:
[a1b2c3d4-e5f6-7890-abcd-ef1234567890] 李明提到他最近经常加班到凌晨 | Involving: 李明 (occurred_start=2024-01-15, mentioned_at=2024-01-15)
[b2c3d4e5-f6a7-8901-bcde-f12345678901] 李明说他因为项目截止日期感到很疲惫 | Involving: 李明 (occurred_start=2024-01-20, mentioned_at=2024-01-20)

Good observation text — clean prose, no metadata, each fact tracked distinctly:
  "李明最近经常加班到凌晨。"
  "李明因为项目截止日期感到疲惫。"

Bad observation text — NEVER do this (verbatim copy of fact text with metadata):
  "李明提到他最近经常加班到凌晨 | Involving: 李明 (occurred_start=2024-01-15, mentioned_at=2024-01-15)"
  "An English or pinyin rendering of 李明's observation."

Observation text rules:
- Write clean prose — NEVER copy raw fact lines or their metadata (temporal fields, "Involving:", "When:" labels, UUIDs).
- Parenthesized metadata like (occurred_start=...) and pipe-separated labels like "| Involving: ..." are fact formatting — strip them entirely from observation text.
- How many observations to create and how much to aggregate is driven by the MISSION above.

{{"creates": [{{"text": "李明最近经常加班到凌晨。", "source_fact_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]}}, {{"text": "李明因为项目截止日期感到疲惫。", "source_fact_ids": ["b2c3d4e5-f6a7-8901-bcde-f12345678901"]}}],
  "updates": [{{"text": "张伟在 Acme Corp 担任高级工程师。", "observation_id": "c3d4e5f6-a7b8-9012-cdef-123456789012", "source_fact_ids": ["d4e5f6a7-b8c9-0123-defa-234567890123"]}}],
  "deletes": [{{"observation_id": "e5f6a7b8-c9d0-1234-efab-345678901234"}}]}}

Rules:
- "source_fact_ids": copy the EXACT UUID strings shown in brackets [uuid] from NEW FACTS — never use integers or positions.
- "observation_id": copy the EXACT "id" UUID string from EXISTING OBSERVATIONS.
- One create/update may reference multiple facts when they jointly support the observation.
- "deletes": only when an observation is directly superseded or contradicted by new facts.
- Do NOT include "tags" — handled automatically.
- Return {{"creates": [], "updates": [], "deletes": []}} if nothing durable is found."""


def build_batch_consolidation_prompt(
    observations_mission: str | None = None,
    observation_capacity_note: str | None = None,
) -> str:
    """
    Build the consolidation prompt for batch mode (multiple facts per LLM call).

    The mission defines *what* to track (customisable per bank).
    Processing rules and output format are always present regardless of mission.
    """
    mission = observations_mission or _DEFAULT_MISSION

    capacity_section = ""
    if observation_capacity_note:
        capacity_section = f"\n\n## CAPACITY CONSTRAINT\n{observation_capacity_note}"

    return (
        "You are a memory consolidation system. Synthesize facts into observations "
        "and merge with existing observations when appropriate.\n\n"
        f"{_LANGUAGE_AND_NAME_RULES}\n\n"
        f"## MISSION\n{mission}{capacity_section}\n\n"
        f"{_PROCESSING_RULES}" + _BATCH_DATA_SECTION + _BATCH_OUTPUT_FORMAT
    )
