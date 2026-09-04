"""Best-effort full-article-text scraping for internal admin review only
(Section 5) - not for any end-user-facing view, and not run for every
ingested article. app/review/assignment.py calls this only for articles
that actually reach an admin's queue, since apolitical articles are never
reviewed at all and scraping them would be pure waste.

Why this exists: RSS feeds are designed as notifications that content
exists, not a distribution channel - most outlets deliberately put only a
headline and a short teaser (sometimes nothing) in the feed itself. An
admin asked to judge pro/anti framing off a one-line teaser can't do that
job. This is a real product problem, not a bug, and it was raised as one
directly - see the "why does the review screen not show article" /
"admins can't review from just a title" conversation this module answers.

Legal/ethical posture, stated plainly rather than glossed over: most news
outlets' Terms of Service prohibit automated scraping of their content.
This is judged lower-risk than a general-purpose scraper because (a) the
result is used only to let a human reviewer make an accurate call,
privately - never republished, never shown to or stored for an end user,
and (b) it behaves like a good-faith actor: it respects each site's own
robots.txt, and identifies itself honestly via User-Agent rather than
spoofing a browser to bypass blocks. A site that disallows or blocks this
is treated as "can't get this one," not something to work around. This is
still not zero legal risk - if this project ever moves beyond an internal
review tool (particularly toward Phase 4's public site), this needs an
actual legal review before scaling or publicizing use of scraped content,
not an assumption that the Phase 3 posture still applies.
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
import trafilatura

logger = logging.getLogger(__name__)

USER_AGENT = "news-classification-poc/0.1 (+internal admin review tool, not for redistribution)"
REQUEST_TIMEOUT_SECONDS = 15

# Some outlets place a long "About the author" credibility block (name,
# years of experience, beat coverage - an increasingly common SEO/E-E-A-T
# pattern) prominently on the article page. On at least one real article,
# trafilatura picked that block instead of the actual article body,
# producing confident-looking but entirely wrong text - see the "why does
# this article have information about the writer" conversation this
# guards against. This is a best-effort heuristic, not a guarantee: it
# will very occasionally reject a legitimate article that happens to open
# by profiling a journalist as its subject (e.g. "X is a columnist who
# has spent a decade covering..."). That's an acceptable trade - a false
# positive here just means scraped_body_text stays empty and the review
# UI falls back to the RSS teaser with an honest scrape_error, which is
# far better than an admin confidently reviewing the wrong text.
_BIO_OPENING_PATTERN = re.compile(
    r"^[A-Z][a-zA-Z.'-]+(?: [A-Z][a-zA-Z.'-]+){0,3} is (?:a|an) .{0,80}"
    r"(editor|correspondent|reporter|journalist|columnist|contributor|bureau chief)",
    re.IGNORECASE,
)
_BIO_CAREER_PHRASES_PATTERN = re.compile(
    r"(years (in|of|covering)|stationed in|has been (reporting|covering)|"
    r"her reporting|his reporting|her coverage|his coverage)",
    re.IGNORECASE,
)


def _looks_like_author_bio(text: str) -> bool:
    # Check the first couple of non-empty lines/paragraphs, not just the
    # very start of the whole text - trafilatura often prepends the
    # headline as its own line before the body, which would otherwise
    # push a bio's opening sentence past a fixed-offset check.
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    opening_matches = any(_BIO_OPENING_PATTERN.match(line[:200]) for line in lines[:2])
    return opening_matches and bool(_BIO_CAREER_PHRASES_PATTERN.search(text[:800]))

# Cache of parsed robots.txt per origin for this process's lifetime - avoids
# re-fetching robots.txt on every article from the same outlet. None means
# "no robots.txt found / unreachable", treated as allowed.
_robots_cache: dict[str, RobotFileParser | None] = {}


@dataclass
class ScrapeResult:
    text: str | None
    error: str | None


def _get_robots_parser(origin: str) -> RobotFileParser | None:
    if origin in _robots_cache:
        return _robots_cache[origin]

    parser: RobotFileParser | None = RobotFileParser()
    try:
        response = requests.get(
            f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            parser = None  # no robots.txt - nothing to disallow
    except requests.RequestException:
        parser = None  # unreachable - fail open rather than block every scrape on a network blip

    _robots_cache[origin] = parser
    return parser


def _robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    parser = _get_robots_parser(origin)
    return parser.can_fetch(USER_AGENT, url) if parser else True


def scrape_article_text(url: str) -> ScrapeResult:
    if not _robots_allowed(url):
        logger.info("Scraping disallowed by robots.txt: %s", url)
        return ScrapeResult(text=None, error="disallowed by robots.txt")

    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.info("Scrape fetch failed for %s: %s", url, exc)
        return ScrapeResult(text=None, error=f"fetch failed: {exc}"[:255])

    text = trafilatura.extract(
        response.text, url=url, include_comments=False, favor_precision=True, output_format="txt"
    )
    if not text or not text.strip():
        return ScrapeResult(text=None, error="extraction produced no text")

    text = text.strip()
    if _looks_like_author_bio(text):
        logger.info("Extraction for %s looked like an author bio, not an article - discarding", url)
        return ScrapeResult(text=None, error="extraction likely grabbed an author bio, not the article")

    return ScrapeResult(text=text, error=None)
