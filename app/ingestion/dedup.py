"""Section 5 wire-copy dedup - first-pass version.

Approach: hash the normalized (headline + body) text. When a new article's
hash matches an existing *canonical* article (one with duplicate_of_id IS
NULL) published within a recent time window, the new article is stored but
linked via duplicate_of_id rather than treated as a fresh story. This keeps
every outlet's copy in the DB (useful later for analytics on how widely a
wire story ran) while giving Phase 2 clustering and Phase 3 review a simple
`WHERE duplicate_of_id IS NULL` filter to get one row per story.

Known limitation (documented, not fixed here): this only catches byte-for-
byte-ish identical wire copy (after whitespace/case normalization). It will
miss lightly-edited wire copy (an outlet adding a paragraph, or trimming
one). A fuzzy/near-duplicate pass (e.g. shingling + similarity threshold) is
a reasonable Phase 2 follow-up once clustering embeddings exist anyway.
"""

import hashlib
import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Article

DEDUP_WINDOW = timedelta(hours=72)


def normalize_text(headline: str, body_text: str) -> str:
    combined = f"{headline}\n{body_text}".lower()
    return re.sub(r"\s+", " ", combined).strip()


def compute_content_hash(headline: str, body_text: str) -> str:
    normalized = normalize_text(headline, body_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_canonical_duplicate(db: Session, content_hash: str, published_at: datetime) -> Article | None:
    """Returns the earliest canonical article with a matching content hash
    published within DEDUP_WINDOW of `published_at`, or None.
    """
    window_start = published_at - DEDUP_WINDOW
    window_end = published_at + DEDUP_WINDOW

    stmt = (
        select(Article)
        .where(
            Article.content_hash == content_hash,
            Article.duplicate_of_id.is_(None),
            Article.published_at >= window_start,
            Article.published_at <= window_end,
        )
        .order_by(Article.published_at.asc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
