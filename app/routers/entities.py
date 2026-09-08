"""Section 13.1-13.2: unauthenticated debug/verification endpoints, same
caveat as app/routers/articles.py and app/routers/clusters.py - not the
admin review API (that's the entities card folded into
app/routers/admin_ui.py's review screen), just a way to confirm entity
extraction and backfill output over HTTP, including on Render's free tier
where there's no shell to run the CLI equivalents.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ArticleEntity, Entity
from app.processing.entities import backfill_entities
from app.schemas.entity import ArticleEntityOut, BackfillEntitiesResult, EntityOut

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityOut])
def list_entities(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> list[EntityOut]:
    entities = db.query(Entity).order_by(Entity.type, Entity.name).limit(limit).all()
    return [
        EntityOut(
            id=e.id, name=e.name, type=e.type, aliases=e.aliases,
            entity_metadata=e.entity_metadata, mention_count=len(e.mentions),
        )
        for e in entities
    ]


@router.get("/{entity_id}/mentions", response_model=list[ArticleEntityOut])
def list_entity_mentions(
    entity_id: int,
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
) -> list[ArticleEntityOut]:
    """Every article that mentions this entity, most-recently-classified
    first - the concrete answer to Section 13.1's core B2B query ("show me
    every article about Subject X"), well ahead of any client-facing
    surface for it.
    """
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    mentions = (
        db.query(ArticleEntity)
        .filter(ArticleEntity.entity_id == entity_id)
        .order_by(ArticleEntity.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ArticleEntityOut(
            article_id=m.article_id, entity_id=m.entity_id, entity_name=entity.name,
            mention_count=m.mention_count, in_headline=m.in_headline,
            first_mention_offset=m.first_mention_offset, prominence=m.prominence,
            system_subject_sentiment=m.system_subject_sentiment,
            subject_sentiment_confidence=m.subject_sentiment_confidence,
            subject_sentiment_provider=m.subject_sentiment_provider,
            published_subject_sentiment=m.published_subject_sentiment,
        )
        for m in mentions
    ]


@router.post("/backfill", response_model=BackfillEntitiesResult)
def trigger_backfill(
    limit: int = Query(default=50, le=500, description="Max articles to scan in this call"),
    rescan_all: bool = Query(
        default=False,
        description="Re-scan every classified article, not just ones never scanned - use after adding a new entity",
    ),
    db: Session = Depends(get_db),
) -> BackfillEntitiesResult:
    """Section 13.6's groundwork requirement made runnable: re-scan
    already-ingested articles against the current Entity table. Capped per
    call for the same reason /process/run is - each newly-matched entity
    costs a real classification call. Check `remaining` and call again if
    it's still above 0.
    """
    result = backfill_entities(db, limit=limit, rescan_all=rescan_all)
    return BackfillEntitiesResult(**result.__dict__)
