"""Orchestrates one ingestion run: sync outlet config -> fetch each active
feed -> dedup -> persist. This is the "Ingest" + "Dedup" stages of Section 7
(stages 3 onward - cluster/classify/queue/review/publish - are later phases).
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ingestion.dedup import compute_content_hash, find_canonical_duplicate
from app.ingestion.feed_fetcher import parse_feed_entries_with_deadline
from app.ingestion.outlets_config import sync_outlets
from app.models import Article, Outlet

logger = logging.getLogger(__name__)


@dataclass
class OutletIngestResult:
    outlet_name: str
    fetched: int = 0
    inserted_new: int = 0
    inserted_duplicate: int = 0
    skipped_existing: int = 0
    error: str | None = None


def _ingest_outlet(db: Session, outlet: Outlet) -> OutletIngestResult:
    result = OutletIngestResult(outlet_name=outlet.name)

    try:
        entries = parse_feed_entries_with_deadline(outlet.rss_feed_url)
    except Exception as exc:  # noqa: BLE001 - one bad feed shouldn't kill the run
        # Includes a TimeoutError from the wall-clock deadline (see
        # feed_fetcher.py's docstring) - a real production incident where a
        # single slow-dripping feed stalled the whole /ingest/run call past
        # its 600s caller-side timeout, with zero outlets after it ever
        # getting a chance to run. Treated the same as any other per-outlet
        # fetch failure: log it, skip this outlet, keep going.
        logger.exception("Failed to fetch/parse feed for outlet %s", outlet.name)
        result.error = str(exc)
        return result

    result.fetched = len(entries)

    for entry in entries:
        existing = db.query(Article).filter(Article.url == entry.url).one_or_none()
        if existing is not None:
            result.skipped_existing += 1
            continue

        content_hash = compute_content_hash(entry.headline, entry.body_text)
        canonical = find_canonical_duplicate(db, content_hash, entry.published_at)

        article = Article(
            headline=entry.headline,
            body_text=entry.body_text,
            url=entry.url,
            guid=entry.guid,
            outlet_id=outlet.id,
            published_at=entry.published_at,
            content_hash=content_hash,
            duplicate_of_id=canonical.id if canonical else None,
        )
        db.add(article)
        db.flush()  # assigns article.id, needed if a later entry duplicates this one

        if canonical:
            result.inserted_duplicate += 1
        else:
            result.inserted_new += 1

    db.commit()
    return result


def run_ingestion(db: Session) -> list[OutletIngestResult]:
    outlets = sync_outlets(db)
    active_outlets = [o for o in outlets if o.is_active]

    results = []
    for outlet in active_outlets:
        results.append(_ingest_outlet(db, outlet))
    return results
