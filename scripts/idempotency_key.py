#!/usr/bin/env python3
"""Return a deterministic idempotency key for a canonical URL.

Usage:
    python scripts/idempotency_key.py "https://example.com/canonical-url"
"""

from __future__ import annotations

import hashlib
import sys

# Compute a deterministic idempotency key for a canonical URL.
def build_idempotency_key(canonical_url: str) -> str:
    value = (canonical_url or "").strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python scripts/idempotency_key.py "<canonical_url>"', file=sys.stderr)
        return 1

    print(build_idempotency_key(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
