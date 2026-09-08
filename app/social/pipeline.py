"""Section 13 social listening orchestration: the fetch-gating decision,
cost accrual, and cost-ceiling status reporting. This is the one module
that actually implements the "shared fetch vs. per-client access" split -
see EntitySocialConfig and ClientSubject's docstrings for the schema
reasoning this code enforces.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.base import EntitySentimentProvider
from app.models import Client, ClientSubject, Entity, EntitySocialConfig, SocialMention
from app.models.enums import SocialSource
from app.social.base import FetchedMention, SocialFetcher

logger = logging.getLogger(__name__)


def _get_or_create_config(db: Session, entity_id: int) -> EntitySocialConfig:
    config = db.get(EntitySocialConfig, entity_id)
    if config is None:
        config = EntitySocialConfig(entity_id=entity_id)
        db.add(config)
        db.flush()
    return config


def _current_period_start() -> date:
    return datetime.now(timezone.utc).date().replace(day=1)


def _roll_spend_period_if_needed(config: EntitySocialConfig) -> None:
    """X ceilings are explicitly monthly (Section 13's own wording), so the
    running total resets at the start of a new calendar month - checked
    lazily whenever this entity's cost is next touched, not on a schedule
    (consistent with this whole project never running anything on its
    own - see README's "nothing runs on its own" framing for ingest/
    process/assign-queue).
    """
    current = _current_period_start()
    if config.x_spend_period_start != current:
        config.x_spend_period_start = current
        config.x_spend_usd = Decimal("0")


def _entity_has_active_x_access(db: Session, entity_id: int) -> bool:
    """The live, authoritative gating check - always re-queried at fetch
    time rather than trusting EntitySocialConfig.x_active's cached value
    (see that model's docstring for why the cache is display-only). Joins
    Client.active so a deactivated client's old access grant can't keep
    costing money after they've left - same "deactivate revokes queue
    assignment" posture Phase 3 already applies to Admin.
    """
    stmt = (
        select(ClientSubject.client_id)
        .join(Client, Client.id == ClientSubject.client_id)
        .where(ClientSubject.entity_id == entity_id, ClientSubject.x_access.is_(True), Client.active.is_(True))
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def _store_new_mentions(
    db: Session,
    entity: Entity,
    source: SocialSource,
    mentions: list[FetchedMention],
    cost_per_item: Decimal,
    sentiment_provider: EntitySentimentProvider,
) -> int:
    """Idempotent on (entity_id, source, url) - a post already stored from
    an earlier fetch is skipped here (storage stays deduplicated) even
    though, for X, it was still billed again by the read that just
    returned it (see SocialMention's docstring on why the per-row cost_usd
    column and the entity-level aggregate don't always reconcile).

    Sentiment is scored only for genuinely NEW rows, same "never re-spend
    on an already-scored item" discipline as app/processing/entities.py's
    backfill - a post already stored keeps whatever sentiment it was first
    scored with, it's never re-classified on a later re-fetch. Reuses
    EntitySentimentProvider (Section 13.2) unchanged: a social post is
    just text mentioning the entity, no different in shape from an
    article's headline+body for this classifier's purposes.

    Returns how many rows were newly inserted.
    """
    if not mentions:
        return 0

    existing_urls = {
        row.url
        for row in db.query(SocialMention.url).filter(
            SocialMention.entity_id == entity.id, SocialMention.source == source,
            SocialMention.url.in_({m.url for m in mentions}),
        )
    }

    new_count = 0
    for mention in mentions:
        if mention.url in existing_urls:
            continue
        sentiment_result = sentiment_provider.classify_subject_sentiment(
            headline="", body_text=mention.content_text, entity_name=entity.name
        )
        db.add(
            SocialMention(
                entity_id=entity.id, source=source, content_text=mention.content_text,
                author=mention.author, posted_at=mention.posted_at, url=mention.url,
                cost_usd=cost_per_item,
                sentiment=sentiment_result.sentiment, sentiment_confidence=sentiment_result.confidence_score,
            )
        )
        existing_urls.add(mention.url)  # guards against a duplicate URL within the same fetch response
        new_count += 1
    return new_count


@dataclass
class EntityFetchResult:
    entity_id: int
    youtube_posts_read: int = 0
    youtube_new_mentions: int = 0
    x_posts_read: int = 0
    x_new_mentions: int = 0
    x_cost_incurred_usd: Decimal = Decimal("0")
    x_skipped_reason: str | None = None
    errors: list[str] = field(default_factory=list)


def fetch_social_for_entity(
    db: Session,
    entity: Entity,
    youtube_fetcher: SocialFetcher | None,
    x_fetcher: SocialFetcher | None,
    sentiment_provider: EntitySentimentProvider | None = None,
) -> EntityFetchResult:
    if sentiment_provider is None:
        from app.llm.factory import get_entity_sentiment_provider

        sentiment_provider = get_entity_sentiment_provider()

    result = EntityFetchResult(entity_id=entity.id)
    config = _get_or_create_config(db, entity.id)
    max_results = settings.social_fetch_max_results_per_entity

    # YouTube: always attempted, free tier, no access gating at all - the
    # only reason it's skipped is a missing API key (caught as a normal
    # fetch error below, same as any other failure).
    if youtube_fetcher is not None:
        try:
            mentions = youtube_fetcher.fetch(entity, max_results)
            result.youtube_posts_read = len(mentions)
            result.youtube_new_mentions = _store_new_mentions(
                db, entity, SocialSource.YOUTUBE, mentions, Decimal("0"), sentiment_provider
            )
            config.youtube_last_fetched_at = datetime.now(timezone.utc)
        except Exception as exc:  # noqa: BLE001 - one bad entity/source shouldn't stall the whole batch
            logger.exception("YouTube fetch failed for entity %s", entity.id)
            result.errors.append(f"youtube: {exc}")
    else:
        result.errors.append("youtube: YOUTUBE_API_KEY not configured")

    # X: gated per-entity on live client access - the one piece of logic
    # that actually enforces the "shared fetch, per-client access" design.
    has_access = _entity_has_active_x_access(db, entity.id)
    config.x_active = has_access  # display-cache sync, not the gating decision itself
    if not has_access:
        result.x_skipped_reason = "no active client currently has x_access=true for this entity"
    elif x_fetcher is None:
        result.x_skipped_reason = "X_API_BEARER_TOKEN not configured"
    else:
        try:
            mentions = x_fetcher.fetch(entity, max_results)
            cost_per_item = Decimal(str(settings.x_cost_per_post_usd))
            # Billed for every post X actually returned, whether or not it
            # turns out to already be stored - see this module's and
            # SocialMention's docstrings for why that's correct, not a bug.
            incurred = cost_per_item * len(mentions)
            _roll_spend_period_if_needed(config)
            config.x_spend_usd = config.x_spend_usd + incurred
            config.x_last_fetched_at = datetime.now(timezone.utc)
            result.x_posts_read = len(mentions)
            result.x_new_mentions = _store_new_mentions(
                db, entity, SocialSource.X, mentions, cost_per_item, sentiment_provider
            )
            result.x_cost_incurred_usd = incurred
        except Exception as exc:  # noqa: BLE001
            logger.exception("X fetch failed for entity %s", entity.id)
            result.errors.append(f"x: {exc}")

    return result


@dataclass
class SocialFetchResult:
    entities_scanned: int = 0
    youtube_posts_read: int = 0
    x_posts_read: int = 0
    x_entities_fetched: int = 0
    x_entities_skipped: int = 0
    x_cost_incurred_usd: Decimal = Decimal("0")
    errors: list[str] = field(default_factory=list)


def fetch_social_mentions(
    db: Session,
    limit: int | None = None,
    youtube_fetcher: SocialFetcher | None = None,
    x_fetcher: SocialFetcher | None = None,
    sentiment_provider: EntitySentimentProvider | None = None,
) -> SocialFetchResult:
    """Manually-triggered stage, same pattern as /ingest/run, /process/run,
    /queue/assign - nothing in this codebase runs on its own. `limit` caps
    how many entities this call scans, same reasoning as /process/run's
    limit (each entity costs real API calls and, for X, real money).

    youtube_fetcher/x_fetcher default to real fetchers built from the
    configured API keys; either is left None (and every entity's fetch for
    that source is skipped with a clear reason) if its key isn't set -
    fails open by omission, never crashes the whole run over one missing
    key. sentiment_provider is built once here (not per-entity) via the
    same cached factory app/processing/pipeline.py uses, so a batch run
    over many entities doesn't reload the local model repeatedly.
    """
    if youtube_fetcher is None:
        try:
            from app.social.youtube import YouTubeFetcher

            youtube_fetcher = YouTubeFetcher()
        except ValueError:
            youtube_fetcher = None
    if x_fetcher is None:
        try:
            from app.social.x_api import XFetcher

            x_fetcher = XFetcher()
        except ValueError:
            x_fetcher = None
    if sentiment_provider is None:
        from app.llm.factory import get_entity_sentiment_provider

        sentiment_provider = get_entity_sentiment_provider()

    stmt = select(Entity).order_by(Entity.id.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    entities = list(db.scalars(stmt))

    result = SocialFetchResult()
    for entity in entities:
        try:
            entity_result = fetch_social_for_entity(db, entity, youtube_fetcher, x_fetcher, sentiment_provider)
            db.commit()
            result.entities_scanned += 1
            result.youtube_posts_read += entity_result.youtube_posts_read
            result.x_posts_read += entity_result.x_posts_read
            result.x_cost_incurred_usd += entity_result.x_cost_incurred_usd
            if entity_result.x_skipped_reason is None and x_fetcher is not None:
                result.x_entities_fetched += 1
            elif entity_result.x_skipped_reason is not None:
                result.x_entities_skipped += 1
            result.errors.extend(f"entity {entity.id}: {e}" for e in entity_result.errors)
        except Exception as exc:  # noqa: BLE001 - one bad entity shouldn't kill the whole run
            logger.exception("Failed to fetch social mentions for entity %s", entity.id)
            db.rollback()
            result.errors.append(f"entity {entity.id}: {exc}")

    return result
