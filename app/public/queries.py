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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Article
from app.models.enums import ClassificationTag
from app.public.formatting import excerpt as make_excerpt
from app.public.formatting import format_jurisdiction
from app.public.formatting import time_ago as make_time_ago


@dataclass
class ClusterCard:
    cluster_id: int
    headline: str
    excerpt: str
    article_url: str
    outlet_name: str
    published_at: datetime
    published_at_display: str  # pre-formatted relative time - see app/public/formatting.time_ago
    outlet_count: int  # outlets whose reviewed coverage agrees on this tag, within this cluster
    jurisdiction: str | None
    ruling_party: str | None
    primary_source_url: str | None


@dataclass
class HomeColumns:
    pro_establishment: list[ClusterCard]
    anti_establishment: list[ClusterCard]
    apolitical: list[ClusterCard]


def _published_articles_for_tag(db: Session, tag: ClassificationTag) -> list[Article]:
    """Newest-published first, so the first article seen per cluster while
    grouping below is always that cluster's most recent one for this tag -
    avoids a second sort pass after grouping.
    """
    stmt = (
        select(Article)
        .options(joinedload(Article.outlet), joinedload(Article.system_tag))
        .where(
            Article.published_tag == tag.value,
            Article.cluster_id.is_not(None),
            Article.duplicate_of_id.is_(None),
        )
        .order_by(Article.published_at.desc())
    )
    return list(db.scalars(stmt).unique())


def _cluster_cards_for_tag(db: Session, tag: ClassificationTag, limit: int) -> list[ClusterCard]:
    articles = _published_articles_for_tag(db, tag)

    representative_by_cluster: dict[int, Article] = {}
    outlets_by_cluster: dict[int, set[int]] = {}
    for article in articles:
        representative_by_cluster.setdefault(article.cluster_id, article)
        outlets_by_cluster.setdefault(article.cluster_id, set()).add(article.outlet_id)

    cards = [
        ClusterCard(
            cluster_id=cluster_id,
            headline=article.headline,
            # Section 5/scraping.py: scraped_body_text is for internal admin
            # review only and must never reach an end user - the public
            # excerpt can only ever be the RSS teaser (body_text), even
            # when a fuller scrape happens to exist for this article.
            excerpt=make_excerpt(article.body_text),
            article_url=article.url,
            outlet_name=article.outlet.name,
            published_at=article.published_at,
            published_at_display=make_time_ago(article.published_at),
            outlet_count=len(outlets_by_cluster[cluster_id]),
            jurisdiction=format_jurisdiction(article.system_tag.jurisdiction) if article.system_tag else None,
            ruling_party=article.system_tag.ruling_party if article.system_tag else None,
            primary_source_url=article.cluster.primary_source_url if article.cluster else None,
        )
        for cluster_id, article in representative_by_cluster.items()
    ]
    cards.sort(key=lambda c: c.published_at, reverse=True)
    return cards[:limit]


def get_home_columns(db: Session, limit_per_column: int = 15) -> HomeColumns:
    return HomeColumns(
        pro_establishment=_cluster_cards_for_tag(db, ClassificationTag.PRO_ESTABLISHMENT, limit_per_column),
        anti_establishment=_cluster_cards_for_tag(db, ClassificationTag.ANTI_ESTABLISHMENT, limit_per_column),
        apolitical=_cluster_cards_for_tag(db, ClassificationTag.APOLITICAL, limit_per_column),
    )
