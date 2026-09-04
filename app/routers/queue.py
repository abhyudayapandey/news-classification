"""Section 7 stage 6 (queue). Unauthenticated JSON ops endpoint, same
category as /ingest/run and /process/run - not the Phase 3 admin UI
itself, just a way to trigger the queueing step manually/via cron.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.review.assignment import assign_pending_articles, heal_bio_scrapes

router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("/assign")
def trigger_assignment(
    limit: int = Query(
        default=10,
        le=200,
        description="Max pending articles to assign (and scrape) in this call - "
        "kept small by default since each one now costs a real network fetch",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Default lowered from Phase 2's ingestion-style batches (which had no
    per-item network cost) - assignment now also attempts a full-text
    scrape per article (app/review/scraping.py), so a large batch here can
    genuinely take a while. Call repeatedly for a big backlog, same pattern
    as /process/run. Also retries scraping for already-assigned articles
    that never got a scrape attempt (e.g. ones queued before this feature
    existed) - `rescraped` counts those separately from `assigned`.
    """
    result = assign_pending_articles(db, limit=limit)
    return {"assigned": result.assigned, "rescraped": result.rescraped}


@router.post("/heal-bio-scrapes")
def trigger_bio_scrape_healing(
    limit: int = Query(
        default=20,
        le=50,
        description="Max already-scraped articles to re-attempt this call, out of however many "
        "currently look like a mis-scraped author bio - see heal_bio_scrapes() for what this does.",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """One-time cleanup, not part of the regular pipeline: heals articles
    scraped before app/review/scraping.py's author-bio detection existed
    (or before it was fixed to catch a headline-prefixed bio). Call
    repeatedly until `matched` is 0 - `matched` reflects how many are
    *still* wrong as of this call, so it naturally drops as you heal them.
    """
    result = heal_bio_scrapes(db, limit=limit)
    return {"matched": result.matched, "rescraped": result.rescraped}
