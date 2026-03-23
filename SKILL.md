---
name: thailand-trip-link-logger
description: Ingest travel links from Telegram (reels, shorts, videos, websites, maps), summarize and classify them into structured fields, and append/update rows in Google Sheets. Use when user sends travel links and wants automatic trip planning records.
---

# Thailand Trip Link Logger

## Purpose

Build a reliable ingestion pipeline:

`Telegram message -> URL extraction -> source-aware fetch -> LLM summary/classification -> Google Sheet write`

Goal: any shared link becomes a searchable, structured travel row.

## Inputs Supported

- Instagram reel links
- YouTube shorts/videos
- TikTok links
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

1. Receive Telegram message.
2. Extract first valid URL.
3. Canonicalize URL (remove tracking params, normalize host).
4. Compute idempotency key (`sha256(canonical_url)`).
5. Check if record already exists:
   - If exists, skip duplicate write (or update existing row).
   - If new, write queued row immediately.
6. Fetch content/metadata by source.
7. Run LLM summarization/classification into strict JSON.
8. Validate JSON against schema/enums.
9. Update row with structured fields and set `Status=processed`.
10. If any step fails, write failure reason and `Status=failed`.

## Skill/Tool Modules

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

Use Google Sheets API (`gspread`) to:
- Append initial queued row fast.
- Update same row after enrichment.

Never drop data silently; failed processing should still be traceable in sheet.

## Reliability Rules (Mandatory)

- **Idempotency**: dedupe by canonical URL hash.
- **Two-stage write**:
  1) quick `queued` write
  2) async enrichment update
- **Schema validation** before final write.
- **Retries**: exponential backoff for transient network/API failures.
- **Observability**: store error reason in notes/status for failures.

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
