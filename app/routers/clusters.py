"""Unauthenticated debug/verification endpoint, same caveat as
app/routers/articles.py: this is not the end-user or admin view (Phase 3),
just a way to confirm Phase 2 clustering output over HTTP.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article, StoryCluster, SystemTag
from app.schemas.article import ClusterOut

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("/stats")
def cluster_stats(db: Session = Depends(get_db)) -> dict:
    """Aggregate view of Phase 2 output - answers "did clustering actually
    group anything, or is every article its own singleton cluster?" without
    paging through /clusters by hand. Multi-article clusters are the actual
    signal that same-story grouping is working; if that count is 0 (or
    near it) against a meaningful total, CLUSTERING_SIMILARITY_THRESHOLD is
    likely too strict for real embeddings, or there just wasn't much
    cross-outlet story overlap in this batch - both are worth knowing,
    neither is distinguishable from a single /clusters page.
    """
    total_clusters = db.query(func.count(StoryCluster.id)).scalar()

    cluster_sizes = (
        db.query(Article.cluster_id, func.count(Article.id).label("size"))
        .filter(Article.cluster_id.is_not(None))
        .group_by(Article.cluster_id)
        .subquery()
    )
    multi_article_clusters = db.query(func.count()).select_from(cluster_sizes).filter(cluster_sizes.c.size > 1).scalar()
    largest_cluster_size = db.query(func.max(cluster_sizes.c.size)).scalar() or 0

    total_classified = db.query(func.count(SystemTag.article_id)).scalar()
    classification_counts = dict(
        db.query(SystemTag.classification, func.count()).group_by(SystemTag.classification).all()
    )
    entity_trigger_overrides = db.query(func.count(Article.id)).filter(Article.entity_trigger_override.is_(True)).scalar()
    needs_review_clusters = db.query(func.count(StoryCluster.id)).filter(StoryCluster.needs_review.is_(True)).scalar()
    unresolved_ruling_party = (
        db.query(func.count(SystemTag.article_id))
        .filter(SystemTag.jurisdiction.is_not(None), SystemTag.ruling_party.is_(None))
        .scalar()
    )

    return {
        "total_clusters": total_clusters,
        "multi_article_clusters": multi_article_clusters,
        "largest_cluster_size": largest_cluster_size,
        "clusters_needing_review": needs_review_clusters,
        "total_classified_articles": total_classified,
        "classification_counts": {tag.value: count for tag, count in classification_counts.items()},
        "entity_trigger_overrides": entity_trigger_overrides,
        "unresolved_ruling_party": unresolved_ruling_party,
    }


@router.get("", response_model=list[ClusterOut])
def list_clusters(
    limit: int = Query(default=20, le=200),
    needs_review_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ClusterOut]:
    query = db.query(StoryCluster)
    if needs_review_only:
        query = query.filter(StoryCluster.needs_review.is_(True))
    clusters = query.order_by(StoryCluster.created_at.desc()).limit(limit).all()
    return [
        ClusterOut(
            id=c.id,
            topic=c.topic,
            primary_source_url=c.primary_source_url,
            needs_review=c.needs_review,
            article_count=len(c.articles),
        )
        for c in clusters
    ]
