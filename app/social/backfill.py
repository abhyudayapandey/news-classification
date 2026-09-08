"""One-off backfill for SocialMention rows stored before engagement_count/
sentiment/geography existed. Deliberately separate from the normal fetch
path (app/social/pipeline.py's _store_new_mentions): that function only
ever sets these fields for a row it's inserting for the first time, by
design (see SocialMention's and EntitySocialConfig's docstrings on why a
re-fetched-but-already-stored post is never re-scored) - this module is
the explicit, manually-triggered opposite: a pass over EXISTING rows.

sentiment IS NULL is the marker for "needs backfilling" - a row genuinely
scored by the normal path is never NULL, even when the result is NEUTRAL
(see SocialMention's own docstring), so this is an exact, safe way to find
rows that predate the column without guessing from other fields.

Sentiment and geography re-scoring are free (local, text-only re-
classification of content already stored) and always run. Real YouTube
view counts are also free to re-fetch (a cheap videos.list statistics
call - the same one a normal fetch already makes, no additional read
cost) and are backfilled whenever a row's engagement_count is still 0.

X engagement is deliberately NOT re-fetched here: that would mean a
fresh, separately-billed X API read for content already paid for once,
and correctly crediting that against EntitySocialConfig.x_spend_usd for
a backfill pass (as opposed to a normal scan-and-fetch run) is real,
untested surface this module does not take on silently. X mentions still
get sentiment/geography backfilled; their engagement_count is left as-is.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.llm.base import EntitySentimentProvider
from app.models import SocialMention
from app.models.enums import SocialSource
from app.processing.geography import guess_geography
from app.social.youtube import YouTubeFetcher

logger = logging.getLogger(__name__)

_YOUTUBE_VIDEOS_BATCH_SIZE = 50  # videos.list's own per-call id limit


@dataclass
class BackfillResult:
    scanned: int = 0
    sentiment_scored: int = 0
    geography_tagged: int = 0
    youtube_engagement_updated: int = 0
    errors: list[str] = field(default_factory=list)


def _extract_youtube_video_id(url: str) -> str | None:
    if "v=" not in url:
        return None
    return url.split("v=", 1)[1].split("&", 1)[0] or None


def backfill_social_mentions(
    db: Session,
    sentiment_provider: EntitySentimentProvider | None = None,
    youtube_fetcher: YouTubeFetcher | None = None,
    limit: int | None = None,
) -> BackfillResult:
    """Re-scores sentiment + content-derived geography for every
    SocialMention with sentiment IS NULL, and re-fetches real YouTube view
    counts for the YouTube rows among them. `limit` caps how many rows one
    call processes (same reasoning as every other manually-triggered stage
    in this codebase - app/social/pipeline.py's fetch_social_mentions,
    app/processing/pipeline.py's process_articles): call repeatedly until
    a run's `scanned` is 0.
    """
    stmt = (
        select(SocialMention)
        .where(SocialMention.sentiment.is_(None))
        .order_by(SocialMention.id.asc())
        .options(selectinload(SocialMention.entity))
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    mentions = list(db.scalars(stmt))

    result = BackfillResult()
    if not mentions:
        return result

    # Built lazily, only once there's actual work - the local provider
    # loads an embedding model on first use, not worth paying for on a
    # call that turns out to have nothing left to backfill.
    if sentiment_provider is None:
        from app.llm.factory import get_entity_sentiment_provider

        sentiment_provider = get_entity_sentiment_provider()

    youtube_ids = {
        vid: True
        for m in mentions
        if m.source == SocialSource.YOUTUBE
        for vid in [_extract_youtube_video_id(m.url)]
        if vid
    }
    view_counts: dict[str, int] = {}
    if youtube_ids:
        if youtube_fetcher is None:
            try:
                youtube_fetcher = YouTubeFetcher()
            except ValueError as exc:
                result.errors.append(f"YouTube engagement backfill skipped entirely: {exc}")
        if youtube_fetcher is not None:
            ids = list(youtube_ids)
            for i in range(0, len(ids), _YOUTUBE_VIDEOS_BATCH_SIZE):
                batch = ids[i : i + _YOUTUBE_VIDEOS_BATCH_SIZE]
                try:
                    view_counts.update(youtube_fetcher.fetch_view_counts(batch))
                except Exception as exc:  # noqa: BLE001 - one bad batch shouldn't stop sentiment backfill
                    logger.exception("YouTube view-count batch fetch failed")
                    result.errors.append(f"YouTube view-count batch failed: {exc}")

    for mention in mentions:
        result.scanned += 1
        try:
            sentiment_result = sentiment_provider.classify_subject_sentiment(
                headline="", body_text=mention.content_text, entity_name=mention.entity.name,
            )
            mention.sentiment = sentiment_result.sentiment
            mention.sentiment_confidence = sentiment_result.confidence_score
            result.sentiment_scored += 1

            if mention.state is None and mention.district is None and mention.constituency is None:
                geography = guess_geography(mention.content_text)
                mention.state = geography.state
                mention.district = geography.district
                mention.constituency = geography.constituency
                mention.seat_type = geography.seat_type
                if geography.state or geography.district or geography.constituency:
                    result.geography_tagged += 1

            if mention.source == SocialSource.YOUTUBE and mention.engagement_count == 0:
                video_id = _extract_youtube_video_id(mention.url)
                if video_id and video_id in view_counts:
                    mention.engagement_count = view_counts[video_id]
                    result.youtube_engagement_updated += 1
        except Exception as exc:  # noqa: BLE001 - one bad row shouldn't stop the whole backfill
            logger.exception("Backfill failed for social mention %s", mention.id)
            result.errors.append(f"mention {mention.id}: {exc}")

    db.commit()
    return result
