"""Section 8-9: read model for the public site. Deliberately separate from
app/review/queries.py (Phase 3's admin-facing queries) - the public site
has a fundamentally different visibility rule than admin review does, and
keeping them apart makes that rule impossible to accidentally blur.

The one rule everything here enforces: nothing is visible publicly until
Article.published_tag is set. That field is already the codebase's own
definition of "safe to show" - app/processing/pipeline.py sets it directly
for apolitical articles ("skip straight to publish", Section 4.3) and
app/routers/admin_ui.py's _record_review sets it once a human has
confirmed or overridden a pro/anti verdict (Section 5). SystemTag (the raw,
unreviewed model output) is never read here at all - only published_tag,
per the platform's own explicit instruction that end users see human-
reviewed classifications, never the raw system tag.
"""

from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Article
from app.models.enums import ClassificationTag
from app.public.formatting import excerpt as make_excerpt
from app.public.formatting import format_jurisdiction
from app.public.formatting import format_outlet_breakdown
from app.public.formatting import time_ago as make_time_ago

# The platform's outlets and readership are India-focused, so "today"
# means the Indian calendar day, not the UTC one this data is stored in -
# using UTC day boundaries would clip or duplicate the last/first ~5.5
# hours of every IST day. Article.published_at is UTC-aware; this is the
# one place that gets converted to IST, purely for day-bucketing.
IST = ZoneInfo("Asia/Kolkata")


def today_ist() -> date_cls:
    return datetime.now(IST).date()


def _day_bounds_utc(day: date_cls) -> tuple[datetime, datetime]:
    """[start, end) in UTC for one IST calendar day."""
    start_ist = datetime.combine(day, time.min, tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)
    return start_ist.astimezone(timezone.utc), end_ist.astimezone(timezone.utc)


@dataclass
class ClusterCard:
    cluster_id: int
    headline: str
    excerpt: str
    article_url: str
    outlet_name: str
    published_at: datetime
    published_at_display: str  # pre-formatted relative time - see app/public/formatting.time_ago
    outlet_breakdown_display: str | None  # e.g. "3 pro · 2 anti" - see format_outlet_breakdown
    has_comparison: bool  # True when 2+ tags exist for this cluster - see /compare/{cluster_id}
    jurisdiction: str | None
    ruling_party: str | None
    primary_source_url: str | None


@dataclass
class HomeColumns:
    pro_establishment: list[ClusterCard]
    anti_establishment: list[ClusterCard]
    apolitical: list[ClusterCard]


@dataclass
class ComparisonArticle:
    headline: str
    excerpt: str
    article_url: str
    outlet_name: str
    published_at_display: str
    jurisdiction: str | None
    ruling_party: str | None


@dataclass
class ClusterComparison:
    cluster_id: int
    primary_source_url: str | None
    pro_establishment: list[ComparisonArticle]
    anti_establishment: list[ComparisonArticle]
    apolitical: list[ComparisonArticle]


def _published_articles_for_tag(
    db: Session, tag: ClassificationTag, day_bounds: tuple[datetime, datetime] | None
) -> list[Article]:
    """Newest-published first, so the first article seen per cluster while
    grouping below is always that cluster's most recent one for this tag -
    avoids a second sort pass after grouping. day_bounds (from
    _day_bounds_utc), when given, restricts to articles whose own
    published_at (the outlet's original publish time, not our review
    time) falls in that IST calendar day.
    """
    conditions = [
        Article.published_tag == tag.value,
        Article.cluster_id.is_not(None),
        Article.duplicate_of_id.is_(None),
    ]
    if day_bounds is not None:
        start, end = day_bounds
        conditions += [Article.published_at >= start, Article.published_at < end]

    stmt = (
        select(Article)
        .options(joinedload(Article.outlet), joinedload(Article.system_tag))
        .where(*conditions)
        .order_by(Article.published_at.desc())
    )
    return list(db.scalars(stmt).unique())


def _outlet_breakdown_by_cluster(
    db: Session, day_bounds: tuple[datetime, datetime] | None
) -> dict[int, dict[str, int]]:
    """One pass across every published article (all three tags, not just
    one) building {cluster_id: {tag: distinct_outlet_count}} - the cross-
    tag view a single tag's query can't see on its own, since two outlets
    covering the same story are reviewed independently and can land on
    different tags. Feeds format_outlet_breakdown() for each card below.
    Scoped to the same day_bounds as the cards it's computed for, so a
    date-filtered view's breakdown reflects that day's coverage only.
    """
    conditions = [
        Article.published_tag.is_not(None),
        Article.cluster_id.is_not(None),
        Article.duplicate_of_id.is_(None),
    ]
    if day_bounds is not None:
        start, end = day_bounds
        conditions += [Article.published_at >= start, Article.published_at < end]

    stmt = select(Article.cluster_id, Article.published_tag, Article.outlet_id).where(*conditions)
    outlets_by_cluster_and_tag: dict[int, dict[str, set[int]]] = {}
    for cluster_id, tag, outlet_id in db.execute(stmt):
        outlets_by_cluster_and_tag.setdefault(cluster_id, {}).setdefault(tag, set()).add(outlet_id)

    return {
        cluster_id: {tag: len(outlet_ids) for tag, outlet_ids in tags.items()}
        for cluster_id, tags in outlets_by_cluster_and_tag.items()
    }


def _cluster_cards_for_tag(
    db: Session,
    tag: ClassificationTag,
    limit: int,
    breakdown_by_cluster: dict[int, dict[str, int]],
    day_bounds: tuple[datetime, datetime] | None,
) -> list[ClusterCard]:
    articles = _published_articles_for_tag(db, tag, day_bounds)

    representative_by_cluster: dict[int, Article] = {}
    for article in articles:
        representative_by_cluster.setdefault(article.cluster_id, article)

    cards = []
    for cluster_id, article in representative_by_cluster.items():
        cluster_breakdown = breakdown_by_cluster.get(cluster_id, {})
        cards.append(
            ClusterCard(
                cluster_id=cluster_id,
                headline=article.headline,
                # Section 5/scraping.py: scraped_body_text is for internal
                # admin review only and must never reach an end user - the
                # public excerpt can only ever be the RSS teaser
                # (body_text), even when a fuller scrape happens to exist
                # for this article.
                excerpt=make_excerpt(article.body_text),
                article_url=article.url,
                outlet_name=article.outlet.name,
                published_at=article.published_at,
                published_at_display=make_time_ago(article.published_at),
                outlet_breakdown_display=format_outlet_breakdown(cluster_breakdown),
                # More than one tag present for this cluster means outlets'
                # independent, blinded reviews genuinely diverged - that's
                # exactly the case worth a "compare the coverage" link to
                # /compare/{cluster_id}. A single-tag cluster (everyone
                # agreed, or only one outlet has covered it so far) has
                # nothing to compare, so no link.
                has_comparison=sum(1 for count in cluster_breakdown.values() if count > 0) > 1,
                jurisdiction=format_jurisdiction(article.system_tag.jurisdiction) if article.system_tag else None,
                ruling_party=article.system_tag.ruling_party if article.system_tag else None,
                primary_source_url=article.cluster.primary_source_url if article.cluster else None,
            )
        )
    cards.sort(key=lambda c: c.published_at, reverse=True)
    return cards[:limit]


def get_cluster_comparison(db: Session, cluster_id: int) -> ClusterComparison | None:
    """Every published article in one story cluster, grouped by tag - the
    full "how did each side cover this" view a home-page card can only
    hint at (one representative headline plus a breakdown count). Same
    published_tag-only visibility rule as everywhere else in this module.
    Returns None when the cluster doesn't exist or has nothing published
    yet, so the route can redirect home instead of rendering an empty page.
    """
    stmt = (
        select(Article)
        .options(joinedload(Article.outlet), joinedload(Article.system_tag), joinedload(Article.cluster))
        .where(
            Article.cluster_id == cluster_id,
            Article.published_tag.is_not(None),
            Article.duplicate_of_id.is_(None),
        )
        .order_by(Article.published_at.desc())
    )
    articles = list(db.scalars(stmt).unique())
    if not articles:
        return None

    by_tag: dict[str, list[ComparisonArticle]] = {tag.value: [] for tag in ClassificationTag}
    primary_source_url = None
    for article in articles:
        if article.cluster and article.cluster.primary_source_url:
            primary_source_url = article.cluster.primary_source_url
        by_tag[article.published_tag].append(
            ComparisonArticle(
                headline=article.headline,
                excerpt=make_excerpt(article.body_text),
                article_url=article.url,
                outlet_name=article.outlet.name,
                published_at_display=make_time_ago(article.published_at),
                jurisdiction=format_jurisdiction(article.system_tag.jurisdiction) if article.system_tag else None,
                ruling_party=article.system_tag.ruling_party if article.system_tag else None,
            )
        )

    return ClusterComparison(
        cluster_id=cluster_id,
        primary_source_url=primary_source_url,
        pro_establishment=by_tag[ClassificationTag.PRO_ESTABLISHMENT.value],
        anti_establishment=by_tag[ClassificationTag.ANTI_ESTABLISHMENT.value],
        apolitical=by_tag[ClassificationTag.APOLITICAL.value],
    )


def get_home_columns(db: Session, limit_per_column: int = 15, day: date_cls | None = None) -> HomeColumns:
    """day (an IST calendar date), when given, restricts every column to
    articles originally published that day - see _day_bounds_utc. None
    (the default) is unfiltered, latest-first regardless of date.
    """
    day_bounds = _day_bounds_utc(day) if day is not None else None
    breakdown_by_cluster = _outlet_breakdown_by_cluster(db, day_bounds)
    return HomeColumns(
        pro_establishment=_cluster_cards_for_tag(
            db, ClassificationTag.PRO_ESTABLISHMENT, limit_per_column, breakdown_by_cluster, day_bounds
        ),
        anti_establishment=_cluster_cards_for_tag(
            db, ClassificationTag.ANTI_ESTABLISHMENT, limit_per_column, breakdown_by_cluster, day_bounds
        ),
        apolitical=_cluster_cards_for_tag(
            db, ClassificationTag.APOLITICAL, limit_per_column, breakdown_by_cluster, day_bounds
        ),
    )
