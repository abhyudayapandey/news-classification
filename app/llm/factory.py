"""Selects concrete providers from config. This is the only place calling
code should get a provider from - never import a concrete provider class
directly outside this module and app/cli.py's compare-providers utility.
"""

from functools import lru_cache

from app.config import settings
from app.llm.base import ClassificationProvider, EmbeddingProvider, EntitySentimentProvider
from app.llm.local_classification import EmbeddingSimilarityClassifier
from app.llm.local_embedding import LocalEmbeddingProvider
from app.llm.local_entity_sentiment import EmbeddingSimilarityEntitySentimentClassifier


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


def get_classification_provider() -> ClassificationProvider:
    if settings.llm_provider == "local":
        return EmbeddingSimilarityClassifier(embedding_provider=get_embedding_provider())
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIClassificationProvider

        return OpenAIClassificationProvider()
    if settings.llm_provider == "gemini":
        from app.llm.gemini_provider import GeminiClassificationProvider

        return GeminiClassificationProvider()
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}. Expected 'local', 'openai', or 'gemini'.")


def get_entity_sentiment_provider() -> EntitySentimentProvider:
    """Section 13.2: reuses the same LLM_PROVIDER setting as establishment
    classification, rather than a separate knob - "same pattern as the
    existing classifier" (as requested) extends to provider selection too,
    not just the interface shape. Flipping LLM_PROVIDER switches both axes
    together; there's no supported way to run one axis local and the other
    paid today, which is a reasonable POC-scale simplification, not an
    oversight - split it out into its own setting if that's ever needed.
    """
    if settings.llm_provider == "local":
        return EmbeddingSimilarityEntitySentimentClassifier(embedding_provider=get_embedding_provider())
    if settings.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIEntitySentimentProvider

        return OpenAIEntitySentimentProvider()
    if settings.llm_provider == "gemini":
        from app.llm.gemini_provider import GeminiEntitySentimentProvider

        return GeminiEntitySentimentProvider()
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}. Expected 'local', 'openai', or 'gemini'.")
