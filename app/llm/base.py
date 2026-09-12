"""Provider-agnostic interfaces for embeddings and classification.

Swapping providers to compare a free local model against a paid API
(OpenAI/Gemini) should never require touching calling code - only which
class app/llm/factory.py returns. See app/llm/factory.py for how the
concrete provider is selected from config, and README's Phase 2 section
for the resource tradeoffs behind each implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.enums import ClassificationTag, SubjectSentiment


class EmbeddingProvider(ABC):
    """Turns article text into a vector for story-cluster similarity search."""

    #: Value stored in Article.embedding_model / SystemTag.provider for
    #: whatever this provider produces, e.g. "local:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2".
    name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one embedding vector per input text, same order."""
        raise NotImplementedError


@dataclass
class ClassificationResult:
    """Shape matches SystemTag's fields directly (minus ruling_party, which
    is resolved deterministically from jurisdiction + article date via the
    JurisdictionRulingParty lookup table - see app/processing/jurisdiction.py
    - rather than guessed by the classifier).
    """

    classification: ClassificationTag
    # "centre" or "state:<name>", or None when classification is apolitical.
    jurisdiction: str | None
    confidence_score: float


class ClassificationProvider(ABC):
    """Establishment pre-filter + pro/anti/apolitical classification
    (Section 7 stages 4-5) in one call, matching how a single LLM prompt
    naturally does both at once.

    WHY classify() ISN'T BATCHED (unlike EntitySentimentProvider's
    classify_subject_sentiment_batch below) - a deliberate decision, not
    an oversight, worth checking against real numbers before revisiting:

    Entity-sentiment batching earned its complexity because the *same*
    article text was being re-sent once per entity mentioned in it - a
    real, multiplicative duplication (N entities = N full re-sends of the
    same headline+body). Article classification has no equivalent waste:
    each call already sends *different* content (a different article),
    so batching would only amortize the fixed system-prompt overhead
    (~275 tokens for CLASSIFICATION_INSTRUCTIONS, measured directly) across
    N articles - roughly 20-25% of one call's input tokens, nothing on the
    output side. At gpt-5-nano pricing ($0.05/$0.40 per 1M in/out tokens),
    that's the difference between about $0.21/month and maybe $0.15/month
    at 100 articles/day, or $4.20 vs ~$3.30/month even at a generous
    2000/day - real, but nowhere near enough to justify restructuring
    app/processing/pipeline.py's currently-sequential (embed → cluster →
    classify → geography → entities), one-article-at-a-time control flow
    into a two-pass batch-then-continue pipeline, or the reliability risk
    that comes with it: a large batched response is where a model is
    likeliest to drop or miscount an entry (the same reasoning behind
    ENTITY_SENTIMENT_BATCH_SIZE=25 below), and a dropped ARTICLE (unlike a
    dropped entity-sentiment score, which just waits for next time) has no
    obvious safe default - it would need to fall out of "unprocessed" and
    get picked up again, which is new state-machine territory this
    pipeline doesn't have today. OpenAI's automatic prompt caching doesn't
    rescue this either: the ~275-token shared prefix is under the
    documented 1,024-token minimum for a prefix to be cache-eligible at
    all, so there's no free lunch waiting to be claimed there.

    This isn't a one-time guess: app/processing/pipeline.py's
    ProcessResult.classification_calls_by_provider counts real classify()
    calls per provider on every run, logged at the end of
    process_articles(). If that count is consistently running well past
    the volumes above, the math changes and batching is worth
    reconsidering - build it then, against real numbers, not now against
    a guess.
    """

    #: Value stored in SystemTag.provider, e.g. "local", "openai:gpt-4o-mini".
    name: str

    @abstractmethod
    def classify(self, headline: str, body_text: str) -> ClassificationResult:
        raise NotImplementedError

    @abstractmethod
    def classify_forcing_establishment_relevant(self, headline: str, body_text: str) -> ClassificationResult:
        """Used by the Section 4.3 entity-trigger override: classify()'s
        first pass called this article apolitical, but a political entity
        was found in the text anyway (app/processing/entity_triggers.py).
        Must return pro-establishment or anti-establishment - never
        apolitical - with a resolved (non-None) jurisdiction.
        """
        raise NotImplementedError


@dataclass
class EntitySentimentResult:
    sentiment: SubjectSentiment
    confidence_score: float


@dataclass
class EntitySentimentBatchItem:
    """One (text, entity_name) pair to score as part of a batch call - see
    EntitySentimentProvider.classify_subject_sentiment_batch. `index` is
    caller-assigned and echoed back in the result mapping so results can
    be matched to items by identity, not by trusting a paid provider to
    preserve list order/count across a JSON round-trip.
    """

    index: int
    headline: str
    body_text: str
    entity_name: str


def chunked(items: list, size: int) -> list[list]:
    """Splits a list into consecutive chunks of at most `size` - the
    shared helper every ENTITY_SENTIMENT_BATCH_SIZE-respecting call site
    (app/social/pipeline.py, app/processing/entities.py,
    app/social/backfill.py) uses before calling
    classify_subject_sentiment_batch, so chunk size stays one constant to
    tune, not three copy-pasted loops."""
    return [items[i : i + size] for i in range(0, len(items), size)]


# Cap on how many items go into one batched call. Not about token limits
# (a real LLM's context window comfortably fits far more than this) - it's
# about blast radius and output reliability: a failed call means every
# item in it falls back to being scored individually (see each provider's
# classify_subject_sentiment_batch override), and a very large item count
# in one JSON response is where a model is likeliest to drop or miscount
# an entry. Every batch call site chunks its input to this size.
ENTITY_SENTIMENT_BATCH_SIZE = 25


class EntitySentimentProvider(ABC):
    """Section 13.2's subject-specific sentiment axis - same provider-
    swappable pattern as ClassificationProvider above (a new classification
    target, not a new architecture), scored per-entity rather than
    per-article since one article can mention several entities with
    different sentiment toward each. Deliberately a separate interface
    from ClassificationProvider, not an extra method bolted onto it: this
    axis needs the entity's name as extra input, and keeping the two
    interfaces apart is what makes it structurally impossible to confuse
    "pro/anti-establishment" (relative to the government in power) with
    "favorable/unfavorable" (relative to one specific entity) - see
    app/models/article_entity.py's module docstring for why that
    distinction matters.
    """

    #: Value stored in ArticleEntity.subject_sentiment_provider, same
    #: naming convention as ClassificationProvider.name.
    name: str

    @abstractmethod
    def classify_subject_sentiment(self, headline: str, body_text: str, entity_name: str) -> EntitySentimentResult:
        raise NotImplementedError

    def classify_subject_sentiment_batch(
        self, items: list[EntitySentimentBatchItem]
    ) -> dict[int, EntitySentimentResult]:
        """Scores many (text, entity_name) pairs at once, keyed by each
        item's `index` in the returned dict. Exists so a caller with N
        social mentions or N entities-in-one-article pays for ONE call
        (one prompt, one round trip) instead of N - see this module's own
        callers (app/social/pipeline.py, app/processing/entities.py,
        app/social/backfill.py) for why per-item calls don't scale here:
        a single busy fetch cycle across several tracked entities was
        issuing dozens of separate billed LLM calls for what is, to a
        paid provider, one prompt's worth of work.

        Default implementation: no real batching, just one
        classify_subject_sentiment() call per item - correct but pays the
        old per-item cost. Every provider that can actually batch (Gemini,
        OpenAI, and the local embedding provider, each for its own reason)
        overrides this; this default only exists so a future provider
        that hasn't implemented batching yet still works, degraded rather
        than broken. Callers are responsible for chunking to
        ENTITY_SENTIMENT_BATCH_SIZE before calling this - kept a caller
        concern rather than done here, since a caller may need to interleave
        chunk results with other per-item work (e.g. skipping already-scored
        rows) that this method has no visibility into.
        """
        return {
            item.index: self.classify_subject_sentiment(item.headline, item.body_text, item.entity_name)
            for item in items
        }
