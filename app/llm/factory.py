"""Selects concrete providers from config. This is the only place calling
code should get a provider from - never import a concrete provider class
directly outside this module and app/cli.py's compare-providers utility.
"""

from app.config import settings
from app.llm.base import ClassificationProvider, EmbeddingProvider
from app.llm.local_classification import EmbeddingSimilarityClassifier
from app.llm.local_embedding import LocalEmbeddingProvider


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
