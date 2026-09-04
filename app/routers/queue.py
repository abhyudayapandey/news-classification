"""Section 7 stage 6 (queue). Unauthenticated JSON ops endpoint, same
category as /ingest/run and /process/run - not the Phase 3 admin UI
itself, just a way to trigger the queueing step manually/via cron.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.review.assignment import assign_pending_articles

router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("/assign")
def trigger_assignment(
    limit: int = Query(default=50, le=500, description="Max pending articles to assign in this call"),
    db: Session = Depends(get_db),
) -> dict:
    assigned = assign_pending_articles(db, limit=limit)
    return {"assigned": assigned}
