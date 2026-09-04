"""Section 7 stage 6 (queue). Unauthenticated JSON ops endpoint, same
category as /ingest/run and /process/run - not the Phase 3 admin UI
itself, just a way to trigger the queueing step manually/via cron.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article
from app.review.assignment import (
    assign_pending_articles,
    divert_unreviewable_articles,
    heal_bio_scrapes,
    retry_failed_scrapes,
)

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
    `diverted` counts articles with no usable text at all (scrape failed
    and the RSS teaser was empty too) that were sent to the super-admin
    Manual Review bucket instead of a regular admin's queue.
    """
    result = assign_pending_articles(db, limit=limit)
    return {"assigned": result.assigned, "rescraped": result.rescraped, "diverted": result.diverted}


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


@router.post("/divert-unreviewable")
def trigger_divert_unreviewable(db: Session = Depends(get_db)) -> dict:
    """One-time cleanup, not part of the regular pipeline: moves articles
    already stuck in a regular admin's queue with no usable text at all
    (from before assign_pending_articles started checking this *before*
    assigning) to the super-admin Manual Review bucket instead. Pure DB
    operation, no network calls - safe to call with no limit, and safe to
    call again later (a no-op once nothing matches).
    """
    result = divert_unreviewable_articles(db)
    return {"diverted": result.diverted}


@router.post("/retry-failed-scrapes")
def trigger_retry_failed_scrapes(
    limit: int = Query(
        default=20,
        le=50,
        description="Max unreviewed articles with a scrape_error to re-attempt this call - "
        "see retry_failed_scrapes() for what this does.",
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Re-attempts scraping for every unreviewed article that currently has
    a scrape_error on record (rejected as a bio, fetch failed, no text
    found, etc.), regardless of whether it's assigned to a regular admin
    or sitting in the Manual Review bucket - the one gap neither /assign's
    retry pass (never-attempted only) nor /heal-bio-scrapes (wrongly-
    accepted text only) covers. Use this after a scraping.py improvement
    ships, to give already-failed articles (like #238) another shot with
    the better code - e.g. the JSON-LD articleBody path and bio-container
    stripping. `recovered` counts how many left the Manual Review bucket
    because the retry found real text - call /queue/assign afterwards to
    actually queue those to an admin. `diverted` counts how many were
    confirmed to still have nothing to review (like #37: a dead link with
    no RSS teaser) and were newly moved to the Manual Review bucket, even
    if they hadn't been assigned there before - covers the same #238-
    shaped gap as /queue/divert-unreviewable, for articles that also
    happen to have a scrape_error on record. Call repeatedly until
    `matched` is 0.
    """
    result = retry_failed_scrapes(db, limit=limit)
    return {
        "matched": result.matched,
        "rescraped": result.rescraped,
        "recovered": result.recovered,
        "diverted": result.diverted,
    }


@router.get("/failed-scrapes")
def list_failed_scrapes(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Debug/verification endpoint, same category as GET /articles - not
    the admin UI. Surfaces the actual scrape_error text for every
    unreviewed article that still has one, since retry_failed_scrapes()'s
    `matched`/`recovered` counts alone don't say *why* a given article is
    still failing (robots.txt, a fetch error, honestly-empty extraction,
    still-detected-as-a-bio, etc.), and most of these articles are sitting
    unblinded in a regular admin's queue - not the Manual Review list -
    since they still have an RSS teaser, so there's no other unauthenticated
    way to see the error text without opening that admin's session.
    """
    stmt = (
        select(Article)
        .where(Article.scrape_error.is_not(None), ~Article.reviews.any())
        .order_by(Article.id.asc())
        .limit(limit)
    )
    return [
        {
            "id": article.id,
            "headline": article.headline,
            "url": article.url,
            "scrape_error": article.scrape_error,
            "has_rss_teaser": bool(article.body_text and article.body_text.strip()),
            "assigned_admin_id": article.assigned_admin_id,
            "needs_manual_link_review": article.needs_manual_link_review,
        }
        for article in db.scalars(stmt)
    ]
