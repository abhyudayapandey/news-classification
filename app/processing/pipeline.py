"""Orchestrates Section 7 stages 3-5 (embed -> cluster -> pre-filter ->
classify) plus the two Section 4.3 safety nets (entity-trigger override,
cluster re-evaluation) for one article at a time.

Does not touch review/publish beyond what Section 4.3 explicitly assigns to
this stage: apolitical articles get published_tag set directly here ("skips
straight to publish"); everything else is left with published_tag=NULL,
awaiting the Phase 3 admin review queue.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import ClassificationProvider, ClassificationResult, EmbeddingProvider
from app.llm.factory import get_classification_provider, get_embedding_provider
from app.models import Article, StoryCluster, SystemTag
from app.models.enums import ClassificationTag
from app.processing.clustering import find_or_create_cluster
from app.processing.entity_triggers import has_trigger_entity
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

    db.add(
        SystemTag(
            article_id=article.id,
            classification=classification.classification,
            jurisdiction=classification.jurisdiction,
            ruling_party=ruling_party,
            confidence_score=classification.confidence_score,
            provider=classification_provider.name,
        )
    )

    if classification.classification == ClassificationTag.APOLITICAL:
        result.apolitical += 1
        article.published_tag = ClassificationTag.APOLITICAL.value  # Section 4.3: skip straight to publish
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


def process_articles(
    db: Session,
    embedding_provider: EmbeddingProvider | None = None,
    classification_provider: ClassificationProvider | None = None,
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
    """
    embedding_provider = embedding_provider or get_embedding_provider()
    classification_provider = classification_provider or get_classification_provider()
    topic_assigner = TopicAssigner(embedding_provider)

    result = ProcessResult()
    for article in _unprocessed_articles(db, limit):
        try:
            _process_one(db, article, embedding_provider, classification_provider, topic_assigner, result)
            db.commit()
            result.processed += 1
        except Exception as exc:  # noqa: BLE001 - one bad article shouldn't kill the run
            logger.exception("Failed to process article %s", article.id)
            db.rollback()
            result.errors.append(f"article {article.id}: {exc}")

    result.remaining_unprocessed = len(_unprocessed_articles(db, limit=None))

    return result
