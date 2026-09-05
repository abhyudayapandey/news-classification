"""Display-only formatting helpers for the public site (Phase 4, Sections
8-9). Nothing here touches the database - pure string/datetime formatting,
kept separate from app/public/queries.py so the query layer stays about
data access and this stays about presentation.
"""

from datetime import datetime, timezone


def format_jurisdiction(raw: str | None) -> str | None:
    """SystemTag.jurisdiction is stored as the raw "centre" / "state:<name>"
    values app/data/jurisdiction_seed.py and the classifier use internally
    (see SystemTag's docstring) - never fit for display as-is. Returns None
    for anything unset, which is the normal case for an apolitical article
    (Section 4.2: jurisdiction only applies when pro/anti is applied).
    """
    if not raw:
        return None
    if raw == "centre":
        return "Centre"
    if raw.startswith("state:"):
        name = raw.split(":", 1)[1]
        return name.replace("-", " ").title()
    return raw.title()


def excerpt(text: str, max_chars: int = 200) -> str:
    """Word-boundary-safe truncation for a card's teaser line. Source is
    always Article.body_text (the RSS teaser) - see app/public/queries.py
    for why scraped_body_text must never reach this function.
    """
    text = " ".join(text.split())  # collapse whitespace/newlines from the feed
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated.rstrip(",.;:") + "…"


_BREAKDOWN_LABELS = {
    "pro-establishment": "pro",
    "anti-establishment": "anti",
    "apolitical": "apolitical",
}
_BREAKDOWN_ORDER = ["pro-establishment", "anti-establishment", "apolitical"]


def format_outlet_breakdown(outlet_counts_by_tag: dict[str, int]) -> str | None:
    """Cross-tag outlet-agreement breakdown for one story cluster, e.g.
    "3 pro · 2 anti" - each outlet's coverage of the same story is
    reviewed independently and blind, so a story can genuinely have some
    outlets landing pro and others anti; this makes that split visible on
    the card itself instead of leaving a reader to notice the same
    headline sitting in two columns. "4 pro" (a single tag) means every
    outlet that covered this story agreed. None when only one outlet's
    coverage exists for this story at all - nothing to compare yet, same
    threshold the old outlet-count pill used.
    """
    total = sum(outlet_counts_by_tag.values())
    if total <= 1:
        return None
    parts = [
        f"{outlet_counts_by_tag[tag]} {_BREAKDOWN_LABELS[tag]}"
        for tag in _BREAKDOWN_ORDER
        if outlet_counts_by_tag.get(tag, 0) > 0
    ]
    return " · ".join(parts)


def time_ago(dt: datetime) -> str:
    """Compact relative time for a card's byline row ("3h ago", "2d ago") -
    falls back to an absolute date once it's far enough back that "Nd ago"
    stops being useful at a glance.
    """
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 86400 * 6:
        return f"{int(seconds // 86400)}d ago"
    return dt.strftime("%d %b %Y")
