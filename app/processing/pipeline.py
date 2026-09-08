"""Orchestrates Section 7 stages 3-5 (embed -> cluster -> pre-filter ->
classify) plus the two Section 4.3 safety nets (entity-trigger override,
cluster re-evaluation) for one article at a time. Since Section 13.1-13.2,
also runs entity extraction + subject-sentiment classification
(app/processing/entities.py) as part of the same per-article pass - both
are "system-generated, awaiting admin review" outputs produced at
classification time, same as SystemTag.

Does not touch review/publish at all: every classified article - apolitical
included - is left with published_tag=NULL here, awaiting the Phase 3 admin
review queue. This is a deliberate departure from Section 4.3's original
"apolitical skips straight to publish": live use surfaced apolitical
mis-classifications (a genuinely pro/anti article the classifier missed)
sitting unreviewed and already public, since nothing ever looked at them
again once auto-published. See app/review/assignment.py's module docstring
for the queueing side of this change. Entity/subject-sentiment tags are
reviewed the same way, folded into the same admin decision - see
app/routers/admin_ui.py's submit_review.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import ClassificationProvider, ClassificationResult, EmbeddingProvider, EntitySentimentProvider
from app.llm.factory import get_classification_provider, get_embedding_provider, get_entity_sentiment_provider
from app.models import Article, Entity, StoryCluster, SystemTag
from app.models.enums import ClassificationTag
from app.processing.clustering import find_or_create_cluster
from app.processing.entities import extract_entities_for_article
from app.processing.entity_triggers import has_trigger_entity
from app.processing.geography import guess_geography
from app.processing.jurisdiction import resolve_ruling_party
from app.processing.topics import TopicAssigner

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    processed: int = 0
    new_clusters: int = 0
    joined_existing_clusters: int = 0
    apolitical: int = 0
    pro_establishment: int = 0
    anti_establishment: int = 0
    entity_trigger_overrides: int = 0
    clusters_flagged_needs_review: int = 0
    unresolved_ruling_party: int = 0
    entity_mentions_found: int = 0
    entity_sentiments_classified: int = 0
    remaining_unprocessed: int = 0
    errors: list[str] = field(default_factory=list)


def _unprocessed_articles(db: Session, limit: int | None) -> list[Article]:
    """Articles not yet embedded/clustered/classified. Duplicates
    (duplicate_of_id set) are excluded - Phase 1's dedup already marks them
    as non-canonical, so they never enter clustering/classification, per
    Section 5's "before it reaches clustering/review". Oldest-first so a
    long backlog processes in publish order, and so a `limit` always
    finishes the oldest, longest-waiting articles first rather than an
    arbitrary subset.
    """
    stmt = (
        select(Article)
        .where(Article.embedding.is_(None), Article.duplicate_of_id.is_(None))
        .order_by(Article.published_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def _classify_with_entity_trigger(
    provider: ClassificationProvider, article: Article, result: ProcessResult
) -> tuple[ClassificationResult, bool]:
    classification = provider.classify(article.headline, article.body_text)

    if classification.classification != ClassificationTag.APOLITICAL:
        return classification, False

    text = f"{article.headline}\n{article.body_text}"
    if not has_trigger_entity(text):
        return classification, False

    logger.info("Entity-trigger net fired for article %s - overriding apolitical call", article.id)
    result.entity_trigger_overrides += 1
    forced = provider.classify_forcing_establishment_relevant(article.headline, article.body_text)
    if forced.classification == ClassificationTag.APOLITICAL:
        # Provider ignored the forcing instruction (can happen with an LLM;
        # the local provider's implementation makes this structurally
        # impossible). Keep going rather than crash the whole run - the
        # override flag on the article still records that this needs a
        # second look even though we couldn't force a clean pro/anti split.
        logger.warning("Provider %s would not produce a non-apolitical result for article %s", provider.name, article.id)
    return forced, True


def _process_one(
    db: Session,
    article: Article,
    embedding_provider: EmbeddingProvider,
    classification_provider: ClassificationProvider,
    entity_sentiment_provider: EntitySentimentProvider,
    entities: list[Entity],
    topic_assigner: TopicAssigner,
    result: ProcessResult,
) -> None:
    text = f"{article.headline}\n{article.body_text}"
    (embedding,) = embedding_provider.embed([text])
    article.embedding = embedding
    article.embedding_model = embedding_provider.name

    cluster_id, is_new_cluster = find_or_create_cluster(db, article)
    article.cluster_id = cluster_id
    if is_new_cluster:
        result.new_clusters += 1
        cluster = db.get(StoryCluster, cluster_id)
        cluster.topic = topic_assigner.assign(embedding)
    else:
        result.joined_existing_clusters += 1

    classification, entity_override = _classify_with_entity_trigger(classification_provider, article, result)
    article.entity_trigger_override = entity_override

    ruling_party = None
    if classification.classification != ClassificationTag.APOLITICAL:
        if classification.jurisdiction is not None:
            ruling_party = resolve_ruling_party(db, classification.jurisdiction, article.published_at)
            if ruling_party is None:
                result.unresolved_ruling_party += 1
                logger.warning(
                    "No ruling-party lookup match for jurisdiction=%r as of %s (article %s) - "
                    "check app/data/jurisdiction_seed.py coverage/dates",
                    classification.jurisdiction,
                    article.published_at,
                    article.id,
                )

    # Content-derived geography - computed for every article regardless of
    # classification, independent of the pro/anti-only jurisdiction/
    # ruling_party pair just above. See app/processing/geography.py and
    # SystemTag's own docstring for why these are a separate axis.
    geography = guess_geography(text)

    db.add(
        SystemTag(
            article_id=article.id,
            classification=classification.classification,
            jurisdiction=classification.jurisdiction,
            ruling_party=ruling_party,
            state=geography.state,
            district=geography.district,
            constituency=geography.constituency,
            seat_type=geography.seat_type,
            confidence_score=classification.confidence_score,
            provider=classification_provider.name,
        )
    )

    if classification.classification == ClassificationTag.APOLITICAL:
        result.apolitical += 1
        # published_tag stays NULL - Phase 4 update: apolitical no longer
        # skips straight to publish, it queues for admin review like
        # pro/anti (app/review/assignment.py). See this module's docstring.
    else:
        if classification.classification == ClassificationTag.PRO_ESTABLISHMENT:
            result.pro_establishment += 1
        else:
            result.anti_establishment += 1

        # Section 4.3 cluster re-evaluation: a new establishment-relevant
        # article joining a cluster that already had other articles in it
        # re-flags the WHOLE cluster, not just this article.
        if not is_new_cluster:
            cluster = db.get(StoryCluster, cluster_id)
            if not cluster.needs_review:
                cluster.needs_review = True
                result.clusters_flagged_needs_review += 1

    # Section 13.1-13.2: entity tagging + subject sentiment. Runs regardless
    # of establishment classification (an apolitical article can still name
    # entities worth tracking, e.g. a human-interest piece quoting a local
    # MLA) - flush first so ArticleEntity's FK sees this article's id, and
    # so entity_mentions is queryable below (apply_entity_matches diffs
    # against it to decide what's new vs. already scored).
    db.flush()
    extraction = extract_entities_for_article(db, article, entities, entity_sentiment_provider)
    result.entity_mentions_found += extraction.mentions_found
    result.entity_sentiments_classified += extraction.newly_classified


def process_articles(
    db: Session,
    embedding_provider: EmbeddingProvider | None = None,
    classification_provider: ClassificationProvider | None = None,
    entity_sentiment_provider: EntitySentimentProvider | None = None,
    limit: int | None = None,
) -> ProcessResult:
    """`limit` caps how many unprocessed articles this call handles - each
    one costs two model calls (embedding + local classification) plus a DB
    round-trip, which adds up fast on a CPU-constrained free-tier instance.
    Without a limit, a large backlog can turn one HTTP request into a
    many-minute call - technically fine (Render's request timeout is 100
    minutes), but a bad way to find that out interactively. Call repeatedly
    (`remaining_unprocessed` on the result tells you when to stop) instead
    of processing an unbounded backlog in one shot.

    Since Section 13.1, this also costs one embedding/API call per entity
    FOUND in the article (app/processing/entities.py) - a plain-text
    article with no political entities costs nothing extra, but one
    mentioning several adds up fast. See that module's docstring for the
    "many entities" cost this multiplies by.
    """
    embedding_provider = embedding_provider or get_embedding_provider()
    classification_provider = classification_provider or get_classification_provider()
    entity_sentiment_provider = entity_sentiment_provider or get_entity_sentiment_provider()
    topic_assigner = TopicAssigner(embedding_provider)
    entities = list(db.scalars(select(Entity)))

    result = ProcessResult()
    for article in _unprocessed_articles(db, limit):
        try:
            _process_one(
                db, article, embedding_provider, classification_provider,
                entity_sentiment_provider, entities, topic_assigner, result,
            )
            db.commit()
            result.processed += 1
        except Exception as exc:  # noqa: BLE001 - one bad article shouldn't kill the run
            logger.exception("Failed to process article %s", article.id)
            db.rollback()
            result.errors.append(f"article {article.id}: {exc}")

    result.remaining_unprocessed = len(_unprocessed_articles(db, limit=None))

    return result
