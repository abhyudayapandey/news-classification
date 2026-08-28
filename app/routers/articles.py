"""Unauthenticated debug/verification endpoint for Phase 1 only.

This is NOT the admin review API (that's Phase 3, and it must blind the
outlet per Section 5). It exists so ingestion results can be checked over
HTTP as well as via the CLI, per the Phase 1 "verify articles land in the
database correctly" requirement.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article
from app.schemas.article import ArticleOut

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=list[ArticleOut])
def list_articles(
    limit: int = Query(default=20, le=200),
    include_duplicates: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[Article]:
    query = db.query(Article)
    if not include_duplicates:
        query = query.filter(Article.duplicate_of_id.is_(None))
    return query.order_by(Article.ingested_at.desc()).limit(limit).all()
