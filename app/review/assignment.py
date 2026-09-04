"""Section 7 stage 6 (queue) + Section 5's "each admin has their own
queue, no overlap": assigns establishment-relevant, classified articles to
an active admin.

Load-balanced rather than a stateless round-robin counter: each article is
assigned to whichever active admin currently has the fewest unreviewed
articles in their queue. This self-corrects across repeated small batches
(e.g. after /process/run?limit=20 runs several times) without needing to
persist "whose turn is next" anywhere - recomputing load from the DB each
call is cheap at POC scale and can't drift out of sync with reality.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Admin, Article, SystemTag
from app.models.enums import ClassificationTag


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


def _pending_articles(db: Session, limit: int | None) -> list[Article]:
    """Establishment-relevant (non-apolitical), classified, not-yet-assigned,
    not-a-duplicate articles - oldest published first, matching Section 5's
    queue order.
    """
    stmt = (
        select(Article)
        .join(SystemTag, SystemTag.article_id == Article.id)
        .where(
            Article.assigned_admin_id.is_(None),
            Article.duplicate_of_id.is_(None),
            SystemTag.classification != ClassificationTag.APOLITICAL,
        )
        .order_by(Article.published_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def assign_pending_articles(db: Session, limit: int | None = None) -> int:
    """Assigns up to `limit` pending articles to active admins, load-
    balanced. Returns the number assigned. A no-op (returns 0) if there are
    no active admins - articles stay unassigned until one exists, they
    aren't dropped.
    """
    depths = _active_admin_queue_depths(db)
    if not depths:
        return 0

    assigned = 0
    for article in _pending_articles(db, limit):
        target_admin_id = min(depths, key=lambda admin_id: (depths[admin_id], admin_id))
        article.assigned_admin_id = target_admin_id
        article.queued_at = datetime.now(timezone.utc)
        depths[target_admin_id] += 1
        assigned += 1

    db.commit()
    return assigned


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
    db.commit()

    return assign_pending_articles(db, limit=len(orphaned))
