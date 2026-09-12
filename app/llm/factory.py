"""Selects concrete providers from config. This is the only place calling
code should get a provider from - never import a concrete provider class
directly outside this module and app/cli.py's compare-providers utility.
"""

import logging
from functools import lru_cache

from app.config import settings
from app.llm.base import ClassificationProvider, EmbeddingProvider, EntitySentimentProvider
from app.llm.fallback import FallbackClassificationProvider, FallbackEntitySentimentProvider
from app.llm.local_classification import EmbeddingSimilarityClassifier
from app.llm.local_embedding import LocalEmbeddingProvider
from app.llm.local_entity_sentiment import EmbeddingSimilarityEntitySentimentClassifier

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _local_embedding_provider() -> LocalEmbeddingProvider:
    """Every call site (app/processing/pipeline.py, entities.py) constructs
    a fresh provider per call when none is injected - fine for the paid
    providers (a cheap HTTP client), but not for the local one: its first
    `.embed()` call loads a real ONNX model into memory
    (app/llm/local_embedding.py's docstring on why fastembed over
    sentence-transformers/PyTorch exists at all - Render's free 512MB tier
    is already tight). Reconstructing that provider per request means
    reloading the model every time, and the memory from the previous
    load isn't always returned to the OS promptly (native allocator
    behavior), so repeated calls can accumulate rather than settle at one
    steady footprint - a real contributor to the OOM restarts seen in
    production. Caching this one provider for the process's lifetime means
    the model loads at most once, ever, no matter how many requests call
    for it. Safe to cache: LocalEmbeddingProvider is stateless per-call
    (embed() takes texts as a parameter, stores nothing request-specific
    on self), and every test injects its own fake provider directly rather
    than going through this factory, so nothing depends on getting a fresh
    instance.
    """
    return LocalEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "local":
        return _local_embedding_provider()
    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER={settings.embedding_provider!r}. "
        "Only 'local' is implemented - OpenAI/Gemini embedding providers "
        "are a Phase 2 follow-up, not built yet (only classification has "
        "paid providers so far)."
    )


def _local_classification_fallback() -> EmbeddingSimilarityClassifier:
    return EmbeddingSimilarityClassifier(embedding_provider=get_embedding_provider())


def get_classification_provider() -> ClassificationProvider:
    """A paid provider (openai/gemini) is always wrapped with the local
    classifier as a fallback - see app/llm/fallback.py's own docstring for
    why, and why this is safe with the mutable `.name` it uses for
    provenance. Covers both a construction-time failure (e.g. the API key
    isn't actually set despite LLM_PROVIDER naming a paid provider) and a
    per-call failure (billing, rate limit, outage, malformed response) -
    per direct instruction: a paid-provider problem should degrade
    classification quality, never lose it outright.
    """
    if settings.llm_provider == "local":
        return _local_classification_fallback()
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIClassificationProvider

        try:
            primary = OpenAIClassificationProvider()
        except Exception:
            logger.exception("Could not construct OpenAIClassificationProvider - using the local classifier only")
            return _local_classification_fallback()
        return FallbackClassificationProvider(primary, _local_classification_fallback())
    if settings.llm_provider == "gemini":
        from app.llm.gemini_provider import GeminiClassificationProvider

        try:
            primary = GeminiClassificationProvider()
        except Exception:
            logger.exception("Could not construct GeminiClassificationProvider - using the local classifier only")
            return _local_classification_fallback()
        return FallbackClassificationProvider(primary, _local_classification_fallback())
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}. Expected 'local', 'openai', or 'gemini'.")


def _local_entity_sentiment_fallback() -> EmbeddingSimilarityEntitySentimentClassifier:
    return EmbeddingSimilarityEntitySentimentClassifier(embedding_provider=get_embedding_provider())


def get_entity_sentiment_provider() -> EntitySentimentProvider:
    """Section 13.2: reuses the same LLM_PROVIDER setting as establishment
    classification, rather than a separate knob - "same pattern as the
    existing classifier" (as requested) extends to provider selection too,
    not just the interface shape. Flipping LLM_PROVIDER switches both axes
    together; there's no supported way to run one axis local and the other
    paid today, which is a reasonable POC-scale simplification, not an
    oversight - split it out into its own setting if that's ever needed.
    This also means YouTube/X entity-sentiment (app/social/pipeline.py,
    app/social/backfill.py both call this same factory function) gets the
    same paid-provider-with-local-fallback treatment as article
    classification below, automatically, with no separate wiring.

    A paid provider is always wrapped with the local classifier as a
    fallback - see get_classification_provider()'s own docstring
    (identical reasoning) and app/llm/fallback.py.
    """
    if settings.llm_provider == "local":
        return _local_entity_sentiment_fallback()
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIEntitySentimentProvider

        try:
            primary = OpenAIEntitySentimentProvider()
        except Exception:
            logger.exception("Could not construct OpenAIEntitySentimentProvider - using the local classifier only")
            return _local_entity_sentiment_fallback()
        return FallbackEntitySentimentProvider(primary, _local_entity_sentiment_fallback())
    if settings.llm_provider == "gemini":
        from app.llm.gemini_provider import GeminiEntitySentimentProvider

        try:
            primary = GeminiEntitySentimentProvider()
        except Exception:
            logger.exception("Could not construct GeminiEntitySentimentProvider - using the local classifier only")
            return _local_entity_sentiment_fallback()
        return FallbackEntitySentimentProvider(primary, _local_entity_sentiment_fallback())
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}. Expected 'local', 'openai', or 'gemini'.")
