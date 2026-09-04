"""Section 7 stage 6 (queue) + Section 5's "each admin has their own
queue, no overlap": assigns establishment-relevant, classified articles to
an active admin.

Load-balanced rather than a stateless round-robin counter: each article is
assigned to whichever active admin currently has the fewest unreviewed
articles in their queue. This self-corrects across repeated small batches
(e.g. after /process/run?limit=20 runs several times) without needing to
persist "whose turn is next" anywhere - recomputing load from the DB each
call is cheap at POC scale and can't drift out of sync with reality.

Also attempts a full-text scrape (app/review/scraping.py) for each newly-
assigned article, since that's the natural point where "this article is
about to be reviewed by a human" becomes true - apolitical articles never
reach here, so they're never scraped. This makes assignment a network-
bound operation now, same caveat as Phase 2's /process/run: one bad or
slow site shouldn't be able to stall the whole batch, so each scrape is
wrapped and a failure just leaves scraped_body_text NULL (the review UI
falls back to the RSS teaser) rather than blocking assignment.

Since scraping was added after assignment already existed, articles
queued before that point are stuck in a real gap: already assigned (so
_pending_articles no longer sees them) but never scraped
(scrape_attempted_at IS NULL). assign_pending_articles() heals these too
on every call, not just newly-pending ones - see
_articles_needing_scrape_retry - so nothing queued before this feature
shipped is permanently stuck without a scrape attempt.

An article with genuinely no text at all - scrape failed/rejected AND
the RSS teaser (body_text) is also empty - never reaches a regular
admin's queue at all, blinded or not: there'd be nothing for them to
read. assign_pending_articles() checks this before assigning (not just
after), flags such an article's needs_manual_link_review instead, and
leaves assigned_admin_id NULL - see _needs_manual_review. Those surface
in the super-admin-only Manual Review list (app/routers/admin_ui.py),
which shows the raw source URL (blinding doesn't apply there) so a
human can visit the link directly and classify it. See
divert_unreviewable_articles() for the one-time cleanup that catches
articles already stuck in a regular admin's queue from before this
existed.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Admin, Article, SystemTag
from app.models.enums import ClassificationTag
from app.review.scraping import looks_like_author_bio, scrape_article_text

logger = logging.getLogger(__name__)


@dataclass
class AssignmentResult:
    assigned: int = 0  # newly assigned to a queue this call
    rescraped: int = 0  # already-assigned articles given a first scrape attempt this call
    diverted: int = 0  # flagged needs_manual_link_review instead of being assigned/reassigned


@dataclass
class BioHealResult:
    matched: int = 0  # articles whose *currently stored* scrape still looks like an author bio
    rescraped: int = 0  # how many of those this call actually re-attempted (bounded by limit)


@dataclass
class DivertResult:
    diverted: int = 0  # already-assigned articles moved to the Manual Review bucket this call


@dataclass
class RetryFailedScrapesResult:
    matched: int = 0  # unreviewed articles that currently have a scrape_error on record
    rescraped: int = 0  # how many of those this call actually re-attempted (bounded by limit)
    recovered: int = 0  # of those, how many now have usable text and left the Manual Review bucket
    diverted: int = 0  # of those, how many were confirmed to still need manual review and were newly diverted


def _active_admin_queue_depths(db: Session) -> dict[int, int]:
    """Active admins mapped to their current unreviewed queue size (0 for
    an active admin with nothing assigned yet).
    """
    depths = {admin_id: 0 for (admin_id,) in db.query(Admin.id).filter(Admin.is_active.is_(True)).all()}

    counts = (
        db.query(Article.assigned_admin_id, func.count(Article.id))
        .filter(Article.assigned_admin_id.is_not(None), ~Article.reviews.any())
        .group_by(Article.assigned_admin_id)
        .all()
    )
    for admin_id, count in counts:
        if admin_id in depths:  # ignore counts belonging to now-inactive admins
            depths[admin_id] = count

    return depths


def _needs_manual_review(article: Article) -> bool:
    """True when there is genuinely no text for a human to review at all -
    the scrape failed/was rejected AND the RSS teaser is also empty. An
    article like this shouldn't sit in a regular admin's (blinded) queue
    showing nothing; it belongs in the super-admin Manual Review list
    instead, with a raw link a human can actually follow.
    """
    has_scraped = bool(article.scraped_body_text and article.scraped_body_text.strip())
    has_teaser = bool(article.body_text and article.body_text.strip())
    return not has_scraped and not has_teaser


def _pending_articles(db: Session, limit: int | None) -> list[Article]:
    """Establishment-relevant (non-apolitical), classified, not-yet-assigned,
    not-a-duplicate, not-already-diverted articles - oldest published first,
    matching Section 5's queue order.
    """
    stmt = (
        select(Article)
        .join(SystemTag, SystemTag.article_id == Article.id)
        .where(
            Article.assigned_admin_id.is_(None),
            Article.duplicate_of_id.is_(None),
            Article.needs_manual_link_review.is_(False),
            SystemTag.classification != ClassificationTag.APOLITICAL,
        )
        .order_by(Article.published_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def _articles_needing_scrape_retry(db: Session, limit: int | None) -> list[Article]:
    """Already-assigned, unreviewed articles with no scrape attempt on
    record - either queued before scraping existed, or a prior attempt
    never got recorded for some other reason. Oldest-queued first.
    """
    stmt = (
        select(Article)
        .where(
            Article.assigned_admin_id.is_not(None),
            Article.scrape_attempted_at.is_(None),
            ~Article.reviews.any(),
        )
        .order_by(Article.queued_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def _scrape_and_record(article: Article) -> None:
    try:
        result = scrape_article_text(article.url)
        article.scraped_body_text = result.text
        article.scrape_error = result.error
    except Exception as exc:  # noqa: BLE001 - one bad site shouldn't stall the whole batch
        logger.exception("Scraping crashed unexpectedly for article %s", article.id)
        article.scrape_error = f"unexpected error: {exc}"[:255]
    article.scrape_attempted_at = datetime.now(timezone.utc)


def assign_pending_articles(db: Session, limit: int | None = None) -> AssignmentResult:
    """Assigns up to `limit` pending articles to active admins, load-
    balanced, then spends any remaining budget re-scraping already-assigned
    articles that never got a scrape attempt (see module docstring). A
    no-op for the assignment half if there are no active admins - pending
    articles stay unassigned until one exists, they aren't dropped; the
    rescrape half still runs regardless, since it doesn't need an admin.

    Each pending article is scraped (if it hasn't been already - e.g. one
    just redistributed by reassign_admin_queue keeps its existing scrape
    rather than wasting a second network call) before the assign-vs-divert
    decision, not after: an article with no usable text at all never gets
    handed to a regular admin in the first place.
    """
    result = AssignmentResult()
    depths = _active_admin_queue_depths(db)

    if depths:
        for article in _pending_articles(db, limit):
            if article.scrape_attempted_at is None:
                _scrape_and_record(article)

            if _needs_manual_review(article):
                article.needs_manual_link_review = True
                result.diverted += 1
                continue

            target_admin_id = min(depths, key=lambda admin_id: (depths[admin_id], admin_id))
            article.assigned_admin_id = target_admin_id
            article.queued_at = datetime.now(timezone.utc)
            depths[target_admin_id] += 1
            result.assigned += 1
        db.commit()

    remaining_budget = None if limit is None else max(0, limit - result.assigned - result.diverted)
    if remaining_budget != 0:
        for article in _articles_needing_scrape_retry(db, remaining_budget):
            _scrape_and_record(article)
            result.rescraped += 1
            if _needs_manual_review(article):
                article.assigned_admin_id = None
                article.queued_at = None
                article.needs_manual_link_review = True
                result.diverted += 1
        db.commit()

    return result


def reassign_admin_queue(db: Session, admin_id: int) -> int:
    """Un-assigns `admin_id`'s unreviewed queue and immediately redistributes
    it to the remaining active admins. Call this when deactivating an admin
    (do it *after* setting is_active=False, so the deactivated admin is
    correctly excluded from receiving any of their own articles back).
    Returns the number of articles moved.
    """
    stmt = select(Article).where(Article.assigned_admin_id == admin_id, ~Article.reviews.any())
    orphaned = list(db.scalars(stmt))
    for article in orphaned:
        article.assigned_admin_id = None
        article.queued_at = None
        # Deliberately NOT clearing scraped_body_text/scrape_attempted_at/
        # scrape_error: the scraped content is a property of the article's
        # URL, not of who's reviewing it - re-scraping on every reassignment
        # would waste a network call and could turn yesterday's successful
        # scrape into a failure over nothing but transient site flakiness.
    db.commit()

    return assign_pending_articles(db, limit=len(orphaned)).assigned


def heal_bio_scrapes(db: Session, limit: int | None = None) -> BioHealResult:
    """One-time cleanup, not part of the regular assign/rescrape flow:
    app/review/scraping.py's author-bio detection only guards *new*
    scrapes - an article scraped before that check existed (or before it
    was tightened) can still have a wrongly-accepted bio sitting in
    scraped_body_text, confidently wrong rather than honestly empty. This
    finds every article whose *currently stored* text still matches that
    pattern, then immediately re-attempts a scrape for up to `limit` of
    them, oldest first, regardless of review status - the new attempt
    either recovers real article text or is honestly rejected again
    (scrape_error explains why), either of which is strictly better than
    what it's replacing. Not run on a schedule - call it, check
    `matched`, and call again if it's still above 0.
    """
    stmt = (
        select(Article).where(Article.scraped_body_text.is_not(None)).order_by(Article.id.asc())
    )
    misdetected = [a for a in db.scalars(stmt) if looks_like_author_bio(a.scraped_body_text)]

    result = BioHealResult(matched=len(misdetected))
    for article in misdetected if limit is None else misdetected[:limit]:
        _scrape_and_record(article)
        result.rescraped += 1
    db.commit()

    return result


def divert_unreviewable_articles(db: Session) -> DivertResult:
    """One-time cleanup, not part of the regular assign/rescrape flow:
    assign_pending_articles() only started checking _needs_manual_review
    *before* assigning once this feature existed - articles assigned
    earlier (like the one that prompted this: a scrape attempt already on
    record, rejected as an author bio, with an empty RSS teaser too - see
    heal_bio_scrapes and app/review/scraping.py) can still be sitting,
    unreviewed, in a regular admin's queue showing nothing at all. Finds
    every such article and moves it to the Manual Review bucket instead:
    un-assigns it and sets needs_manual_link_review. Pure DB reads/writes,
    no network calls, so unlike the scrape-healing cleanups this doesn't
    need a `limit` - call it once, it's done.
    """
    stmt = (
        select(Article)
        .where(
            Article.assigned_admin_id.is_not(None),
            Article.scrape_attempted_at.is_not(None),
            Article.needs_manual_link_review.is_(False),
            ~Article.reviews.any(),
        )
        .order_by(Article.id.asc())
    )
    candidates = [a for a in db.scalars(stmt) if _needs_manual_review(a)]

    for article in candidates:
        article.assigned_admin_id = None
        article.queued_at = None
        article.needs_manual_link_review = True
    db.commit()

    return DivertResult(diverted=len(candidates))


def retry_failed_scrapes(db: Session, limit: int | None = None) -> RetryFailedScrapesResult:
    """One-time (or occasional) cleanup, not part of the regular pipeline:
    neither assign_pending_articles()'s retry pass nor heal_bio_scrapes()
    touches an article that was already attempted and came back with a
    real scrape_error - the former only looks at scrape_attempted_at IS
    NULL (never attempted), the latter only at scraped_body_text IS NOT
    NULL (wrongly-accepted text, not a rejected/failed one). An article
    like #238 - already attempted, rejected, scraped_body_text NULL - is
    never retried by anything else once app/review/scraping.py itself
    improves (e.g. the JSON-LD articleBody path and bio-container
    stripping added alongside this function). This is the one that gives
    it another shot with whatever scrape_article_text() can do today.

    Finds every unreviewed article with a scrape_error on record,
    regardless of whether it's sitting in a regular admin's queue or the
    Manual Review bucket, and re-attempts up to `limit` of them. If a
    retry recovers usable text for an article that had been diverted to
    Manual Review, it's cleared back out of that bucket (needs_manual_
    link_review=False) so the normal assignment/queue flow picks it up
    again - it does NOT immediately assign it to an admin itself, to keep
    that decision (load balancing) in one place: call assign_pending_
    articles() afterwards to actually queue it.

    The reverse also happens here, not just in divert_unreviewable_
    articles(): an article can have a scrape_error *and* sit in a regular
    admin's queue with needs_manual_link_review still False if it was
    assigned before that check existed (same #238-shaped gap divert_
    unreviewable_articles() cleans up) - confirmed live (#37: a 404, no
    RSS teaser, still sitting in a regular admin's queue with nothing to
    review). Rather than depend on divert_unreviewable_articles() having
    already been called, this checks _needs_manual_review() after every
    retry regardless of the article's starting state, so a still-stuck
    article gets diverted here too, not just a previously-diverted one
    getting recovered.
    """
    stmt = (
        select(Article)
        .where(Article.scrape_error.is_not(None), ~Article.reviews.any())
        .order_by(Article.id.asc())
    )
    candidates = list(db.scalars(stmt))
    result = RetryFailedScrapesResult(matched=len(candidates))

    for article in candidates if limit is None else candidates[:limit]:
        was_diverted = article.needs_manual_link_review
        _scrape_and_record(article)
        result.rescraped += 1
        still_needs_manual = _needs_manual_review(article)
        if was_diverted and not still_needs_manual:
            article.needs_manual_link_review = False
            result.recovered += 1
        elif still_needs_manual and not was_diverted:
            article.assigned_admin_id = None
            article.queued_at = None
            article.needs_manual_link_review = True
            result.diverted += 1
    db.commit()

    return result
