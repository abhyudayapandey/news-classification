"""Standalone feed health check - does NOT touch the database.

Run this after cloning, from a machine with normal internet access, to
confirm the feed URLs in config/outlets.yaml are actually alive before
relying on them. This build environment's outbound network is restricted
to a small allowlist that doesn't include news domains, so these URLs were
never fetched live during development - run this yourself first.

Usage:
    python -m app.ingestion.verify_feeds
"""

import sys

from app.ingestion.feed_fetcher import parse_feed_entries
from app.ingestion.outlets_config import load_outlets_config


def main() -> int:
    entries = load_outlets_config()
    if not entries:
        print("No outlets configured in config/outlets.yaml")
        return 1

    all_ok = True
    for outlet in entries:
        status = "SKIP (inactive)" if not outlet.is_active else None
        if status:
            print(f"[{status}] {outlet.name}: {outlet.rss_feed_url}")
            continue

        try:
            items = parse_feed_entries(outlet.rss_feed_url)
        except Exception as exc:  # noqa: BLE001
            all_ok = False
            print(f"[FAIL] {outlet.name}: {outlet.rss_feed_url}\n       {exc}")
            continue

        if not items:
            all_ok = False
            print(f"[EMPTY] {outlet.name}: {outlet.rss_feed_url} - parsed but returned 0 entries")
            continue

        print(f"[OK]   {outlet.name}: {len(items)} entries. Newest: \"{items[0].headline}\"")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
