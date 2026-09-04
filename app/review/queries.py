"""Reusable, efficient queries backing the super-admin review listing
(Section 10) - deliberately structured as plain functions returning ORM
rows/aggregates rather than baked into a route handler, since the actual
analytics dashboard (a later phase) will want the same filters (by admin,
decision, date range) without re-deriving this query logic. Nothing here
builds a chart or aggregate view beyond what's needed for the current
listing page - that's explicitly out of scope for this phase.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Review
from app.models.enums import ReviewDecision


@dataclass
class ReviewFilters:
    admin_id: int | None = None
    decision: ReviewDecision | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def _apply_filters(query, filters: ReviewFilters):
    if filters.admin_id is not None:
        query = query.filter(Review.admin_id == filters.admin_id)
    if filters.decision is not None:
        query = query.filter(Review.decision == filters.decision)
    if filters.date_from is not None:
        query = query.filter(Review.timestamp >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(Review.timestamp <= filters.date_to)
    return query


def query_reviews(
    db: Session, filters: ReviewFilters, limit: int = 50, offset: int = 0
) -> tuple[list[Review], int]:
    """Returns (page of reviews newest-first, total matching count).
    Eager-loads article + admin in the same query (joinedload) - the
    listing page needs both for every row, so this avoids an N+1 query
    pattern that would otherwise fire once per row.
    """
    base_query = _apply_filters(db.query(Review), filters)
    total = base_query.with_entities(func.count(Review.id)).scalar()

    rows = (
        _apply_filters(db.query(Review).options(joinedload(Review.article), joinedload(Review.admin)), filters)
        .order_by(Review.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows, total


def decision_counts_by_admin(db: Session, filters: ReviewFilters) -> list[tuple[int, str, int, int]]:
    """Per-admin (admin_id, admin_name, agreed_count, overrode_count) -
    groundwork for the later analytics dashboard's throughput/disagreement
    view; not rendered as a chart yet, just exposed as a clean aggregate.
    """
    from app.models import Admin

    query = db.query(
        Review.admin_id,
        Admin.name,
        func.count(Review.id).filter(Review.decision == ReviewDecision.AGREED_WITH_SYSTEM).label("agreed"),
        func.count(Review.id).filter(Review.decision == ReviewDecision.OVERRODE).label("overrode"),
    ).join(Admin, Admin.id == Review.admin_id)

    query = _apply_filters(query, filters)
    return query.group_by(Review.admin_id, Admin.name).order_by(Admin.name).all()
