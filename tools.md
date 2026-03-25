# OpenClaw Tools Reference

This file defines tool-level contracts for this repository so OpenClaw can call tools consistently.

## Conventions

- Prefer machine-readable output (JSON on stdout).
- On error, return non-zero exit code and JSON with `ok=false` and `error`.
- Do not hardcode secrets (cookies, tokens, keys) in source files.
- Use canonical URLs before dedupe/hash operations.

## Tool: Instagram Fetcher

- **Path**: `handlers/instagram.py`
- **Use when**:
  - URL host contains `instagram.com`
  - URL is reel/post/profile content to ingest
- **Purpose**:
  - Fetch Instagram HTML using browser-like headers
  - Extract image alt text hints
  - Save raw HTML to a temp file (default)
  - Return agent-friendly JSON

### CLI (Instagram)

```bash
python handlers/instagram.py "<instagram_url>" --cookie "<cookie_header>"
```

Optional flags:

- `--timeout <seconds>` (default `20`)
- `--no-save-source` (skip temp `.html` file write)
- `--raw-html` (print raw HTML instead of JSON)

### Output Contract (Instagram JSON)

Success:

```json
{
  "ok": true,
  "url": "https://www.instagram.com/reel/...",
  "source": "instagram",
  "timeout": 20,
  "html_length": 123456,
  "alt_count": 2,
  "alts": ["..."],
  "source_file": "/tmp/instagram_source_abc123.html"
}
```

Error:

```json
{
  "ok": false,
  "source": "instagram",
  "url": "https://www.instagram.com/reel/...",
  "error": "Failed to fetch Instagram page source: ..."
}
```

### OpenClaw Handling Guidance (Instagram)

- If `ok=true`: use `alts` as quick context for summarization.
- If `source_file` exists: keep path for debug/audit.
- If `ok=false`: mark row `needs_review` or `failed`, keep pipeline running.

## Tool: Idempotency Key Generator

- **Path**: `scripts/idempotency_key.py`
- **Use when**:
  - Canonical URL is available
  - Dedupe key is needed for lookup/upsert
- **Purpose**:
  - Generate deterministic SHA-256 key from canonical URL

### CLI (Idempotency)

```bash
python scripts/idempotency_key.py "https://example.com/canonical-url"
```

### Output Contract (Idempotency)

- Success: prints one SHA-256 hex string to stdout.
- Error: prints usage to stderr and exits non-zero.

### OpenClaw Handling Guidance (Idempotency)

- Use returned hash as idempotency key for:
  - pre-insert duplicate checks
  - stable row updates

## Tool: Google Sheets via `gog`

- **Provider**: OpenClaw built-in Google integration
- **Use when**:
  - Creating a trip sheet
  - Writing queued/enriched rows
  - Reading existing rows for dedupe

### Required Sheet Headers

`Timestamp`, `Link`, `CanonicalLink`, `Source`, `Type`, `Subtype`, `Place`, `ExpenseTier`, `Priority`, `Notes`, `Status`, `Confidence`

### OpenClaw Handling Guidance (gog)

- Trip creation must create one sheet per trip.
- Store sheet metadata in `/memory/multi-trip-link-logger/trips/<tripname>/details.md`:
  - `sheet_id`
  - `sheet_tab`
  - `sheet_url`
  - `sheet_headers`

## Tool Routing Order (Recommended)

1. Detect source from URL.
2. If source is Instagram, call `handlers/instagram.py`.
3. Canonicalize URL.
4. Call `scripts/idempotency_key.py`.
5. Use `gog` to dedupe + append/update rows.
