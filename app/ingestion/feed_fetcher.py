"""Fetches and parses a single RSS feed into normalized entries.

Scope note: this stores whatever text the feed itself provides (title +
summary, or content:encoded when present). Most Indian outlet RSS feeds only
carry a summary/teaser, not the full article body - full-text extraction
would need a per-outlet scraper (fragile, and arguably against some outlets'
ToS), which is out of scope for Phase 1. Admin review in Phase 3 will need
to account for body_text sometimes being a teaser rather than the full
article; noting this as a known gap rather than silently pretending
otherwise.
"""

import logging
from calendar import timegm
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class FetchedEntry:
    headline: str
    url: str
    guid: str | None
    published_at: datetime
    body_text: str


def _strip_html(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def _extract_body(entry: feedparser.FeedParserDict) -> str:
    content_list = entry.get("content")
    if content_list:
        return _strip_html(content_list[0].get("value", ""))
    summary = entry.get("summary", "")
    return _strip_html(summary) if summary else ""


def _extract_published_at(entry: feedparser.FeedParserDict) -> datetime | None:
    struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct_time is None:
        return None
    return datetime.fromtimestamp(timegm(struct_time), tz=timezone.utc)


def parse_feed_entries(feed_url: str, timeout_seconds: int = 20) -> list[FetchedEntry]:
    parsed = feedparser.parse(feed_url, request_headers={"User-Agent": "news-classification-poc/0.1"})

    if parsed.bozo and not parsed.entries:
        # bozo=True with entries present is often just a minor XML quirk feedparser
        # recovered from; only treat it as fatal when nothing could be parsed at all.
        raise ValueError(f"Failed to parse feed {feed_url}: {parsed.get('bozo_exception')}")

    entries: list[FetchedEntry] = []
    for entry in parsed.entries:
        headline = entry.get("title")
        url = entry.get("link")
        if not headline or not url:
            logger.warning("Skipping feed entry missing title/link from %s", feed_url)
            continue

        published_at = _extract_published_at(entry)
        if published_at is None:
            # Some feeds omit dates; fall back to "now" rather than dropping the article.
            published_at = datetime.now(tz=timezone.utc)

        entries.append(
            FetchedEntry(
                headline=headline.strip(),
                url=url.strip(),
                guid=entry.get("id") or entry.get("guid"),
                published_at=published_at,
                body_text=_extract_body(entry),
            )
        )

    return entries
