---

name: multi-trip-link-logger
description: Ingest travel links from Telegram (reels, shorts, videos, websites, maps), summarize and classify them into structured fields, and append/update rows in Google Sheets. Use when users send trip-related links and want automatic planning records across multiple trips.
---

# Multi-Trip Link Logger

## Purpose

Build a reliable ingestion pipeline:

`Telegram message -> URL extraction -> source-aware fetch -> LLM summary/classification -> Google Sheet write`

Goal: any shared link becomes a searchable, structured travel row.

Tool registry for execution details:

- Before invoking any tool/handler, read `tools.md`.
- Use `tools.md` as the source of truth for tool CLI usage, output contracts, and failure handling.

## Multi-Tenant (Multi-Trip) Design

Treat each trip as an isolated tenant with its own metadata and storage path.

Before processing any link, the skill must do one of the following:

1. If no active trip is selected, ask user to create or select a trip.
2. If active trip exists, use that trip context for all operations.

Trip files live under:

- `trips/<trip_id>/details.md`

Each trip can map to a different Google Sheet (via `gog`), category preferences, and defaults.

### Trip Creation (Mandatory First Step)

When a user sends links without an active trip, the skill must first ask:

- `Please create a trip first. What should I name this trip?`

Mandatory input to collect:

- `trip_name` (example: `trip1`)

Trip creation actions (must run in this order):

1. Create trip folder and details file path:
  - `trips/<trip_name>/details.md`
2. Create a Google Sheet using OpenClaw `gog`.
3. Add required headers in first row:
  - `Timestamp`, `Link`, `CanonicalLink`, `Source`, `Type`, `Subtype`, `Place`, `ExpenseTier`, `Priority`, `Notes`, `Status`, `Confidence`
4. Get the created Google Sheet link.
5. Share that Google Sheet link with the user.
6. Write all creation outputs into `trips/<trip_name>/details.md`.

Optional input (only if user provides):

- `destination_country`
- `destination_regions` (city/area list)
- `start_date` (YYYY-MM-DD)
- `end_date` (YYYY-MM-DD)
- `budget_profile` (`low|medium|high|mixed`)
- `currency` (e.g. `THB`, `INR`)
- `default_tags`
- `notes`

After collecting input:

1. Create `trips/<trip_name>/details.md`.
2. Write trip metadata in the template format.
3. Set this trip as active context for subsequent ingestion.

## Inputs Supported

- Instagram reel links
- YouTube shorts/videos
- Websites/blogs
- Google Maps place links
- Plain text messages containing URLs

## Output Contract (Sheet Row)

Always write these fields:

- `Timestamp`
- `Link`
- `CanonicalLink`
- `Source` (`instagram|youtube|maps|website|tiktok|other`)
- `Type` (`food|hotel|activity|shopping|transport|tip|other`)
- `Subtype`
- `Place`
- `ExpenseTier` (`low|medium|high|unknown`)
- `Priority` (`must|maybe|later`)
- `Notes`
- `Status` (`queued|processed|failed|needs_review`)
- `Confidence` (`0.00` to `1.00`)

## Workflow

1. Ensure active trip exists; otherwise run trip creation flow first.
2. Receive Telegram message.
3. Extract first valid URL.
4. Canonicalize URL (remove tracking params, normalize host).
5. Compute idempotency key by running `python scripts/idempotency_key.py "<canonical_url>"`.
6. Check if record already exists:
  - If exists, skip duplicate write (or update existing row).
  - If new, write queued row immediately.
7. Fetch content/metadata by source.
8. Run LLM summarization/classification into strict JSON.
9. Validate JSON against schema/enums.
10. Update row with structured fields and set `Status=processed`.
11. If any step fails, write failure reason and `Status=failed`.

## Trip Metadata Template (`trips/<trip_name>/details.md`)

Use this format:

```markdown
# Trip Details

- trip_name: trip1
- trip_path: trips/trip1/details.md
- sheet_provider: gog
- sheet_name: trip1-links
- sheet_id: your-google-sheet-id
- sheet_tab: links
- sheet_url: https://docs.google.com/spreadsheets/d/your-google-sheet-id/edit
- sheet_headers: Timestamp, Link, CanonicalLink, Source, Type, Subtype, Place, ExpenseTier, Priority, Notes, Status, Confidence
- destination_country: Thailand
- destination_regions: Bangkok, Phuket, Chiang Mai
- start_date: 2026-06-01
- end_date: 2026-06-15
- budget_profile: medium
- currency: THB
- default_tags: food, beach, temple
- notes: Focus on food + local markets
```

## Tool Modules (Read `tools.md` First)

Use `tools.md` as the canonical reference for all tool invocation details, output contracts, and failure handling behavior.

### 1) Router Skill

Responsibilities:

- Trigger on Telegram inbound message.
- Create normalized task payload:
  - `message_id`
  - `chat_id`
  - `raw_text`
  - `url`
  - `received_at`

### 2) Link Extractor Tool

Use regex fallback:

```python
import re

def extract_link(message: str) -> str | None:
    pattern = r"https?://\S+"
    m = re.findall(pattern, message or "")
    return m[0] if m else None
```

### 3) Fetch + Parse Tool

Recommended handlers:

- `youtube`: `yt-dlp` for title/channel/duration/description
- `website`: `requests + beautifulsoup4` (or article extraction)
- `maps`: parse place metadata available in URL/title
- `instagram/tiktok`: best-effort metadata; fall back gracefully

Important:

- Do not block pipeline if fetch is partial.
- Continue with fallback and lower confidence.

### 4) Summarize + Classify Skill (LLM)

Prompt the model to return JSON only:

```text
Extract travel planning info from this content.

Return STRICT JSON with keys:
type, subtype, place, expense_tier, priority, notes, confidence

Allowed values:
- type: food|hotel|activity|shopping|transport|tip|other
- expense_tier: low|medium|high|unknown
- priority: must|maybe|later
- confidence: float between 0 and 1
```

If fields are unknown:

- use `"unknown"` for tier
- use `"other"` for type
- keep short notes and set confidence lower

### 5) Google Sheet Writer Tool

Use OpenClaw's existing `gog` integration for Google Sheets to:

- Append initial queued row fast.
- Update same row after enrichment.

Never drop data silently; failed processing should still be traceable in sheet.

## Reliability Rules (Mandatory)

- **Idempotency**: dedupe by canonical URL hash.
- **Two-stage write**:
  1. quick `queued` write
  2. async enrichment update
- **Schema validation** before final write.
- **Retries**: exponential backoff for transient network/API failures.
- **Observability**: store error reason in notes/status for failures.

## Utility Script: Idempotency Key

Use this shared helper so every module computes the same key:

```bash
python scripts/idempotency_key.py "https://example.com/some-canonical-url"
```

Use the returned hash as the idempotency key for dedupe checks and row updates.

## Recommended Python Dependencies

```bash
pip install requests beautifulsoup4 yt-dlp gspread oauth2client
```

Optional:

```bash
pip install newspaper3k instaloader tiktokapipy
```

## Telegram Reply Behavior

On success:

- `Added -> Type | Place | ExpenseTier | Subtype`

On partial success:

- `Saved with limited metadata; marked for review`

On failure:

- `Could not process link now; logged as failed for retry`

## Suggested Processing Order

Start simple and expand:

1. Telegram -> extract -> append queued row.
2. Add YouTube full enrichment path.
3. Add website enrichment.
4. Add maps enrichment.
5. Add Instagram/TikTok best-effort path.

## Data Quality Notes

- Use enums exactly as defined to keep sheet filterable.
- Keep `Notes` short and decision-friendly.
- Normalize place names (e.g., `Bangkok`, `Phuket`, `Chiang Mai`).
- Use `needs_review` when classifier confidence is low.

## Future Enhancements

- Query commands from Telegram:
  - `show best food in bangkok`
  - `list low-cost phuket activities`
- Add status workflow: `pending -> booked -> done`
- Push top picks to calendar/checklist

## Definition of Done

The system is complete when:

- Any travel link sent in Telegram creates exactly one sheet record.
- Record is summarized and categorized with consistent enums.
- Duplicates are prevented.
- Failures are visible and retryable.

