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
import socket
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@contextmanager
def _bounded_socket_timeout(seconds: float):
    """feedparser has no timeout argument of its own - the documented
    workaround is scoping the process-wide socket default around the call.

    IMPORTANT LIMITATION, confirmed as a real production incident (not just
    theoretical): this bounds each individual blocking socket call (connect,
    and each recv()) to `seconds`, not the TOTAL wall-clock time for the
    whole fetch. A feed that trickles data slowly enough to keep every single
    recv() under this timeout - a few bytes every 15s, say - can still take
    several minutes in aggregate without ever tripping this limit, and since
    outlets are ingested sequentially in one /ingest/run request, that one
    slow feed can stall the whole call well past the caller's own timeout
    budget. parse_feed_entries_with_deadline() below adds the real, total
    wall-clock cap this only approximates. Not thread-safe against concurrent
    fetches, which is fine for the POC's single-worker, one-request-at-a-time
    ingestion path.
    """
    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(previous)


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
    with _bounded_socket_timeout(timeout_seconds):
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


def parse_feed_entries_with_deadline(
    feed_url: str, timeout_seconds: int = 20, wall_clock_deadline_seconds: float = 30
) -> list[FetchedEntry]:
    """Same as parse_feed_entries(), but enforces a real total wall-clock cap
    on top of it - see _bounded_socket_timeout()'s docstring for exactly why
    that alone isn't enough (a slow-but-steady feed can dodge every
    individual per-call timeout while still taking minutes overall). Runs
    the fetch in a throwaway single-use thread so a feed that blows the
    deadline can be abandoned outright: raises TimeoutError immediately
    rather than making the caller (run_ingestion(), processing outlets
    sequentially in one /ingest/run request) wait on it. The abandoned
    thread is not forcibly killed - Python can't do that - it just keeps
    running in the background until it finishes or errors on its own and is
    then discarded; parse_feed_entries() touches no DB session or other
    shared mutable state, so an orphaned one is harmless, not a leak of
    anything but a little memory/CPU until it naturally ends.
    """
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(parse_feed_entries, feed_url, timeout_seconds)
        try:
            return future.result(timeout=wall_clock_deadline_seconds)
        except FutureTimeoutError as exc:
            raise TimeoutError(
                f"Fetching {feed_url} exceeded the {wall_clock_deadline_seconds}s wall-clock deadline "
                "(the feed was still trickling data slowly enough to dodge the per-call socket timeout)"
            ) from exc
    finally:
        executor.shutdown(wait=False)
