"""Unauthenticated debug/verification endpoint, same caveat as
app/routers/articles.py: this is not the end-user or admin view (Phase 3),
just a way to confirm Phase 2 clustering output over HTTP.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import StoryCluster
from app.schemas.article import ClusterOut

router = APIRouter(prefix="/clusters", tags=["clusters"])


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
