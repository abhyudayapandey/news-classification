"""Selects concrete providers from config. This is the only place calling
code should get a provider from - never import a concrete provider class
directly outside this module and app/cli.py's compare-providers utility.
"""

from app.config import settings
from app.llm.base import ClassificationProvider, EmbeddingProvider, EntitySentimentProvider
from app.llm.local_classification import EmbeddingSimilarityClassifier
from app.llm.local_embedding import LocalEmbeddingProvider
from app.llm.local_entity_sentiment import EmbeddingSimilarityEntitySentimentClassifier


def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "local":
        return LocalEmbeddingProvider()
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
