from __future__ import annotations

import argparse
import json
import tempfile
import requests
from bs4 import BeautifulSoup


def get_instagram_view_source(
    instagram_url: str, timeout: int = 20, cookie_header: str | None = None
) -> str:
    """Fetch and return raw HTML source for an Instagram URL."""
    url = (instagram_url or "").strip()
    if not url:
        raise ValueError("instagram_url cannot be empty")
    if "instagram.com" not in url:
        raise ValueError("Expected an Instagram URL")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-IN,en;q=0.9",
        "Cache-Control": "max-age=0",
        "DPR": "1",
        "Priority": "u=0, i",
        "Sec-CH-Prefers-Color-Scheme": "dark",
        "Sec-CH-UA": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "Sec-CH-UA-Full-Version-List": (
            '"Chromium";v="146.0.7680.153", "Not-A.Brand";v="24.0.0.0", '
            '"Google Chrome";v="146.0.7680.153"'
        ),
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Model": '""',
        "Sec-CH-UA-Platform": '"Linux"',
        "Sec-CH-UA-Platform-Version": '""',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Viewport-Width": "758",
        "Referer": "https://www.instagram.com/",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch Instagram page source: {exc}") from exc


def extract_image_alts(html: str) -> list[str]:
    """Extract all non-empty alt values from img tags."""
    soup = BeautifulSoup(html, "lxml")
    alts: list[str] = []
    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt:
            alts.append(alt)
    return alts


def write_source_to_temp_file(html: str) -> str:
    """Write raw HTML to a temporary file and return path."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".html",
        prefix="instagram_source_",
        delete=False,
    ) as tmp:
        tmp.write(html)
        return tmp.name


def run_instagram_fetch(
    url: str,
    timeout: int = 20,
    cookie_header: str | None = None,
    save_source: bool = True,
) -> dict:
    """Fetch Instagram page and return agent-friendly structured output."""
    html = get_instagram_view_source(url, timeout=timeout, cookie_header=cookie_header)
    alts = extract_image_alts(html)
    source_file = write_source_to_temp_file(html) if save_source else None
    return {
        "ok": True,
        "url": url,
        "source": "instagram",
        "timeout": timeout,
        "html_length": len(html),
        "alt_count": len(alts),
        "alts": alts,
        "source_file": source_file,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch raw HTML source from an Instagram URL."
    )
    parser.add_argument("url", help="Instagram URL (post/reel/profile URL)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds (default: 20)",
    )
    parser.add_argument(
        "--raw-html",
        action="store_true",
        help="Output raw HTML instead of image alt text",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Cookie header value copied from browser/curl (optional)",
    )
    parser.add_argument(
        "--no-save-source",
        action="store_true",
        help="Do not write raw HTML to a temporary file",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        result = run_instagram_fetch(
            args.url,
            timeout=args.timeout,
            cookie_header=args.cookie,
            save_source=not args.no_save_source,
        )

        if args.raw_html:
            html = get_instagram_view_source(
                args.url, timeout=args.timeout, cookie_header=args.cookie
            )
            print(html)
        else:
            print(json.dumps(result, ensure_ascii=True))
        return 0
    except (ValueError, RuntimeError) as exc:
        error = {"ok": False, "source": "instagram", "url": args.url, "error": str(exc)}
        print(json.dumps(error, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
