"""Section 13 social listening. `POST /social/fetch` and `GET /social/
mentions` are unauthenticated ops/debug endpoints, same category and same
established risk posture as `/ingest/run`, `/process/run`, and `/entities`
- an internal-tool tradeoff already accepted project-wide, not a new one
introduced for this feature. `POST /social/fetch` can incur real X spend,
same as `/process/run` already can with a paid LLM_PROVIDER - triggering
a costly pipeline stage without auth is an existing, known tradeoff here,
not new.

Deliberately NOT exposed here: per-client ceiling status or per-entity
spend totals - that's business-confidential cost/contract data, one level
more sensitive than "did a fetch happen," and lives only behind
super-admin auth in app/routers/admin_ui.py's social-costs page, per
direct instruction ("should live only on a super-admin-only screen").
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SocialMention
from app.models.enums import SocialSource
from app.schemas.social import SocialFetchRunResult, SocialMentionOut
from app.social.pipeline import fetch_social_mentions

router = APIRouter(prefix="/social", tags=["social"])


@router.post("/fetch", response_model=SocialFetchRunResult)
def trigger_social_fetch(
    limit: int = Query(default=20, le=200, description="Max entities to scan in this call"),
    db: Session = Depends(get_db),
) -> SocialFetchRunResult:
    """YouTube is attempted for every scanned entity (free tier, no
    gating). X is attempted only for an entity with at least one active
    client's x_access=true right now - everything else is silently (but
    visibly, via `x_entities_skipped`) skipped. Capped per call like
    every other pipeline trigger in this project - X reads cost real
    money, so an unbounded call here is a worse way to find that out than
    the same lesson /process/run already teaches for free.
    """
    result = fetch_social_mentions(db, limit=limit)
    return SocialFetchRunResult(**result.__dict__)


@router.get("/mentions", response_model=list[SocialMentionOut])
def list_social_mentions(
    entity_id: int | None = Query(default=None),
    source: SocialSource | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
) -> list[SocialMentionOut]:
    query = db.query(SocialMention)
    if entity_id is not None:
        query = query.filter(SocialMention.entity_id == entity_id)
    if source is not None:
        query = query.filter(SocialMention.source == source)
    return query.order_by(SocialMention.fetched_at.desc()).limit(limit).all()
