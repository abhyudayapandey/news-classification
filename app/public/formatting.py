"""Display-only formatting helpers for the public site (Phase 4, Sections
8-9). Nothing here touches the database - pure string/datetime formatting,
kept separate from app/public/queries.py so the query layer stays about
data access and this stays about presentation.
"""

from datetime import date, datetime, timedelta, timezone


def format_date_long(day: date) -> str:
    """"4 September 2026" - for the date-picker's headline context on the
    public homepage (app/routers/public.py's day param).
    """
    return day.strftime("%-d %B %Y")


def recent_date_options(today: date, days: int = 14) -> list[tuple[str, str]]:
    """(iso_value, label) pairs, today first, for the home page's date
    <select> - a bounded list rather than an open-ended native date-input
    calendar. Two reasons: a native <input type="date">'s calendar UI
    renders as a full-screen sheet on iOS Safari (reported as "really
    bad, so big"), where a <select> is a compact native wheel picker on
    every platform; and a future date is structurally never one of these
    options at all, rather than merely discouraged by a `max` attribute
    that iOS wasn't fully enforcing anyway.
    """
    options = []
    for offset in range(days):
        day = today - timedelta(days=offset)
        if offset == 0:
            label = "Today"
        elif offset == 1:
            label = "Yesterday"
        else:
            label = day.strftime("%a, %-d %b")
        options.append((day.isoformat(), label))
    return options


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


def entity_subtitle(entity) -> str:
    """Type/party/state line shown under an entity's name on the client
    portal (dashboard cards and a subject's detail header) - built from
    Entity.entity_metadata's free-form fields (Section 13.1), since what's
    worth showing differs by entity type and there's no fixed schema for
    it (see Entity's own docstring). Deliberately tolerant of whichever
    keys are actually present - app/data/entity_seed.py doesn't populate
    every field for every entity.
    """
    from app.models.enums import EntityType

    meta = entity.entity_metadata or {}
    if entity.type == EntityType.PERSON:
        parts = [p for p in (meta.get("role"), meta.get("party")) if p]
        constituency = meta.get("constituency")
        if constituency:
            seat_type = meta.get("seat_type")
            parts.append(f"{constituency} ({seat_type.upper()})" if seat_type else constituency)
        return " · ".join(parts) if parts else "Person"
    if meta.get("scope") == "state" and meta.get("state"):
        return f"State party · {meta['state']}"
    if meta.get("scope") == "national":
        return "National party"
    return "Party"


def entity_initials(name: str) -> str:
    """Up to 2 letters for a dashboard card's avatar circle - first letter
    of the first two words ("Rohan Deshmukh" -> "RD", "Shiv Sena" -> "SS"),
    or just the first letter for a single-word name.
    """
    words = name.split()
    letters = "".join(w[0] for w in words[:2])
    return letters.upper() or "?"


def youtube_thumbnail_url(mention_url: str) -> str | None:
    """hqdefault.jpg thumbnail for a stored YouTube mention, keyed off the
    same v=<id> query param the stored video URL itself carries - a fixed,
    free URL pattern, no API call needed. None if the URL is malformed
    (defensive only; every stored YouTube mention's url comes from
    app/social/youtube.py's own fetch, which always includes v=).
    """
    if "v=" not in mention_url:
        return None
    video_id = mention_url.split("v=", 1)[1].split("&", 1)[0]
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None


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
