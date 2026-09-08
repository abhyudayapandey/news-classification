"""Section 13.1-13.2: promotes entity detection from a binary apolitical-
safety-net trigger (app/processing/entity_triggers.py, unchanged) into a
first-class, queryable per-article record, plus a subject-specific
sentiment score per entity (Section 13.2).

Matching approach, deliberately consistent with entity_triggers.py: plain
word-boundary regex against each Entity's name + aliases
(app/data/entity_seed.py), not an NER model. Same reasoning as that
module - transparent, needs no model download, costs nothing, and is
trivial to extend by editing seed data. The tradeoff is the same kind too:
false negatives (an entity referred to by a form not in its aliases) and,
more consequentially here, false positives from an ambiguous bare surname
(see app/data/entity_seed.py's note on "Modi" et al.) - accepted and
flagged rather than silently absorbed, since a wrong entity tag is a worse
failure mode for a queryable "show me every article about X" feature than
it was for the apolitical trigger's course binary gate.

Prominence heuristic (asked to be explained explicitly): a subject
mentioned once in passing is a different signal than a subject the
article is actually about, so three cheap, explainable signals are
combined into a 0-8 point score:

  - +3 if the entity is named in the headline - the single strongest
    signal that an article is centrally about someone, since headlines
    are written to name the article's actual subject, not a footnote.
  - +1 per mention, capped at 3 - repeated mentions still relate to how
    central a subject is, but a 10th mention isn't 10x more meaningful
    than a 3rd, so this is capped rather than left unbounded.
  - +2 if the first mention falls in the first third of the combined
    (headline + body) text, +1 if in the middle third, +0 in the last
    third - an entity introduced early is more likely the article's
    actual subject than one that shows up as an aside near the end.

Thresholds: score >= 5 -> "primary", score >= 2 -> "secondary", else
"mentioned". These bands, like the classifier confidence temperature in
app/llm/similarity.py, are a reasonable starting point rather than a
tuned constant - there's no labeled data yet to validate them against.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import EntitySentimentProvider
from app.llm.factory import get_entity_sentiment_provider
from app.models import Article, ArticleEntity, Entity
from app.models.enums import EntityProminence
from app.text_utils import boundary_pattern

logger = logging.getLogger(__name__)


@dataclass
class EntityMatch:
    entity: Entity
    mention_count: int
    in_headline: bool
    first_mention_offset: int
    prominence: EntityProminence


def _compute_prominence(mention_count: int, in_headline: bool, first_mention_offset: int, text_length: int) -> EntityProminence:
    score = 0
    if in_headline:
        score += 3
    score += min(mention_count, 3)
    if text_length > 0:
        position_fraction = first_mention_offset / text_length
        if position_fraction <= 1 / 3:
            score += 2
        elif position_fraction <= 2 / 3:
            score += 1

    if score >= 5:
        return EntityProminence.PRIMARY
    if score >= 2:
        return EntityProminence.SECONDARY
    return EntityProminence.MENTIONED


def find_entity_matches(headline: str, body_text: str, entities: list[Entity]) -> list[EntityMatch]:
    """Scans one article's text against every seeded Entity - O(entities)
    regex searches per article, cheap at this scale (pure regex, no model
    call) even with a few hundred entities seeded. `entities` is passed in
    (not queried here) so a caller processing many articles in one run
    loads the Entity table once, not once per article.
    """
    headline_len = len(headline)
    full_text = f"{headline}\n{body_text}"
    text_length = len(full_text)

    matches = []
    for entity in entities:
        names_to_match = [entity.name, *entity.aliases]
        offsets = [m.start() for name in names_to_match for m in boundary_pattern(name).finditer(full_text)]
        if not offsets:
            continue

        mention_count = len(offsets)
        first_offset = min(offsets)
        in_headline = first_offset < headline_len
        prominence = _compute_prominence(mention_count, in_headline, first_offset, text_length)
        matches.append(
            EntityMatch(
                entity=entity,
                mention_count=mention_count,
                in_headline=in_headline,
                first_mention_offset=first_offset,
                prominence=prominence,
            )
        )
    return matches


@dataclass
class ExtractionResult:
    mentions_found: int = 0
    newly_classified: int = 0


def apply_entity_matches(
    db: Session,
    article: Article,
    matches: list[EntityMatch],
    sentiment_provider: EntitySentimentProvider,
) -> ExtractionResult:
    """Upserts one ArticleEntity row per match. Subject-sentiment
    classification (a real model/API call, unlike the free regex matching
    above) is skipped for a pair that already has a
    system_subject_sentiment - re-matching is always cheap and safe to
    redo (app/processing/entities.backfill_entities relies on this), but
    re-scoring sentiment on every re-scan would re-spend money on a paid
    provider for no new information.
    """
    existing_by_entity_id = {ae.entity_id: ae for ae in article.entity_mentions}
    result = ExtractionResult(mentions_found=len(matches))

    for match in matches:
        existing = existing_by_entity_id.get(match.entity.id)
        if existing is not None:
            existing.mention_count = match.mention_count
            existing.in_headline = match.in_headline
            existing.first_mention_offset = match.first_mention_offset
            existing.prominence = match.prominence
            continue

        sentiment = sentiment_provider.classify_subject_sentiment(article.headline, article.body_text, match.entity.name)
        result.newly_classified += 1
        db.add(
            ArticleEntity(
                article_id=article.id,
                entity_id=match.entity.id,
                mention_count=match.mention_count,
                in_headline=match.in_headline,
                first_mention_offset=match.first_mention_offset,
                prominence=match.prominence,
                system_subject_sentiment=sentiment.sentiment,
                subject_sentiment_confidence=sentiment.confidence_score,
                subject_sentiment_provider=sentiment_provider.name,
            )
        )

    article.entities_extracted_at = datetime.now(timezone.utc)
    return result


def extract_entities_for_article(
    db: Session,
    article: Article,
    entities: list[Entity],
    sentiment_provider: EntitySentimentProvider | None = None,
) -> ExtractionResult:
    """Single entry point used by both the live pipeline
    (app/processing/pipeline.py, one article at a time as it's classified)
    and backfill_entities below (many already-ingested articles at once) -
    one code path, two callers, so the two can never drift apart.
    """
    sentiment_provider = sentiment_provider or get_entity_sentiment_provider()
    matches = find_entity_matches(article.headline, article.body_text, entities)
    return apply_entity_matches(db, article, matches, sentiment_provider)


@dataclass
class BackfillResult:
    scanned: int = 0
    new_mentions_classified: int = 0
    remaining: int = 0


def _articles_to_backfill(db: Session, limit: int | None, rescan_all: bool) -> list[Article]:
    stmt = select(Article).where(Article.duplicate_of_id.is_(None), Article.system_tag.has())
    if not rescan_all:
        stmt = stmt.where(Article.entities_extracted_at.is_(None))
    stmt = stmt.order_by(Article.published_at.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def backfill_entities(db: Session, limit: int | None = None, rescan_all: bool = False) -> BackfillResult:
    """Section 13.6's groundwork requirement: re-running entity extraction
    against already-ingested articles must be straightforward, not only
    wired into live ingestion. This is that re-run.

    Two modes:
      - rescan_all=False (default): targets articles never scanned at all
        (entities_extracted_at IS NULL) - covers both articles ingested
        before this feature existed, and the ordinary "keep up with the
        backlog" case if this is ever run on a schedule.
      - rescan_all=True: targets every classified article regardless of
        prior scan state - for "a new entity was just added/seeded, sweep
        the archive for it" (the future client-onboarding backfill in
        Section 13.6 will need exactly this, once ClientSubject exists to
        drive it - this flag is the plain building block, no client
        awareness here yet).

    Either way, matching always re-runs (cheap - see find_entity_matches);
    only genuinely new (article, entity) pairs pay for a sentiment
    classification call (see apply_entity_matches).
    """
    entities = list(db.scalars(select(Entity)))
    if not entities:
        logger.warning("backfill_entities called with no seeded entities - nothing to match against")

    sentiment_provider = get_entity_sentiment_provider()
    result = BackfillResult()
    for article in _articles_to_backfill(db, limit, rescan_all):
        try:
            matches = find_entity_matches(article.headline, article.body_text, entities)
            extraction = apply_entity_matches(db, article, matches, sentiment_provider)
            db.commit()
            result.scanned += 1
            result.new_mentions_classified += extraction.newly_classified
        except Exception:  # noqa: BLE001 - one bad article shouldn't kill the whole backfill
            logger.exception("Failed to backfill entities for article %s", article.id)
            db.rollback()

    result.remaining = len(_articles_to_backfill(db, limit=None, rescan_all=rescan_all))
    return result
