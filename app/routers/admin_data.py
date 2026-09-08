"""Manual data-seeding endpoints. HTTP counterpart to CLI commands that
need to run somewhere without shell access - notably Render's free tier,
which has no interactive shell. Same unauthenticated-debug-endpoint caveat
as the other routers here: not the Phase 3 admin API.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.data.entity_seed import seed_entities
from app.data.jurisdiction_seed import seed_jurisdictions
from app.db import get_db
from app.models import Admin, Entity
from app.models.enums import AdminRole
from app.social.backfill import backfill_social_mentions
from app.social.pipeline import fetch_youtube_historical

router = APIRouter(prefix="/admin-data", tags=["admin-data"])


@router.post("/seed-jurisdictions")
def trigger_seed_jurisdictions(db: Session = Depends(get_db)) -> dict:
    inserted, updated = seed_jurisdictions(db)
    return {
        "inserted": inserted,
        "updated": updated,
        "note": "See app/data/jurisdiction_seed.py's module docstring for what's confirmed vs. still needs verification.",
    }


@router.post("/seed-entities")
def trigger_seed_entities(db: Session = Depends(get_db)) -> dict:
    inserted, updated = seed_entities(db)
    return {
        "inserted": inserted,
        "updated": updated,
        "note": "See app/data/entity_seed.py's module docstring for what's confidently seeded vs. flagged gaps.",
    }


@router.post("/backfill-social-mentions")
def trigger_backfill_social_mentions(
    limit: int | None = Query(default=None, description="Max rows to process this call"),
    db: Session = Depends(get_db),
) -> dict:
    """HTTP counterpart to `python -m app.cli backfill-social-mentions` -
    same Render-has-no-shell reasoning as this module's other endpoints.
    Re-scores sentiment/geography (free) and re-fetches real YouTube view
    counts (free) for SocialMention rows stored before those columns
    existed; X engagement is deliberately not touched here (see
    app/social/backfill.py's module docstring for why). Call repeatedly
    with a limit until `scanned` comes back 0.
    """
    result = backfill_social_mentions(db, limit=limit)
    return {
        "scanned": result.scanned,
        "sentiment_scored": result.sentiment_scored,
        "geography_tagged": result.geography_tagged,
        "youtube_engagement_updated": result.youtube_engagement_updated,
        "errors": result.errors,
        "note": "X engagement is not backfilled here - it would mean a fresh, separately-billed X API read.",
    }


@router.post("/fetch-youtube-historical")
def trigger_fetch_youtube_historical(
    entity_id: int = Query(...),
    before: str = Query(..., description="ISO date/datetime - only videos published before this"),
    after: str | None = Query(default=None, description="ISO date/datetime - only videos published after this"),
    max_results: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """HTTP counterpart to `python -m app.cli fetch-youtube-historical` -
    same Render-has-no-shell reasoning as this module's other endpoints.
    Unlike X's recent-search (hard-capped to the last 7 days by the
    endpoint itself), YouTube's search.list accepts an arbitrary
    publishedBefore/publishedAfter window, so this genuinely reaches
    further back than the regular fetch-social scan can - see
    app/social/pipeline.py's fetch_youtube_historical for why this is a
    separate, single-entity entry point rather than a parameter on the
    regular multi-entity scan.
    """
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"No entity with id={entity_id}")
    try:
        published_before = datetime.fromisoformat(before).replace(tzinfo=timezone.utc)
        published_after = datetime.fromisoformat(after).replace(tzinfo=timezone.utc) if after else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {exc}") from exc

    new_count = fetch_youtube_historical(
        db, entity, published_before, published_after=published_after, max_results=max_results,
    )
    return {"entity": entity.name, "new_mentions_stored": new_count}


class BootstrapSuperAdminRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


@router.post("/bootstrap-super-admin")
def bootstrap_super_admin(body: BootstrapSuperAdminRequest, db: Session = Depends(get_db)) -> dict:
    """Creates the first super-admin account. Only works when the `admins`
    table is empty - a chicken-and-egg fix for Render's free tier (no
    shell to run `python -m app.cli create-admin`), NOT a general-purpose
    account-creation endpoint. Once any admin exists, this always 403s;
    use the authenticated super-admin UI (/admin/admins) for every account
    after the first.
    """
    if db.query(Admin).count() > 0:
        raise HTTPException(
            status_code=403,
            detail="An admin account already exists - use the authenticated /admin/admins UI to create more.",
        )
    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    admin = Admin(username=body.username, name=body.name, password_hash=password_hash, role=AdminRole.SUPER_ADMIN)
    db.add(admin)
    db.commit()
    return {"created": body.username, "role": "super_admin"}
