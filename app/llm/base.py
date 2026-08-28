"""Provider-agnostic interfaces for Phase 2 (clustering/classification).

Not used by any Phase 1 code. This exists now so Phase 2 is a matter of
implementing these two interfaces per provider and selecting one via
config (settings.embedding_provider / settings.llm_provider), rather than
a design decision made under time pressure later. Swapping providers to
compare a free local model against a paid API (OpenAI/Gemini) should never
require touching calling code - only which class factory() returns.

Planned Phase 2 implementations:
- EmbeddingProvider: LocalEmbeddingProvider (sentence-transformers, free,
  runs on your machine) / OpenAIEmbeddingProvider / GeminiEmbeddingProvider
- ClassificationProvider: same three-way split, used for the establishment
  pre-filter and pro/anti/apolitical classification (Section 7 stages 4-5)
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Turns article text into a vector for story-cluster similarity search."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one embedding vector per input text, same order."""
        raise NotImplementedError


class ClassificationProvider(ABC):
    """Zero-shot establishment-relevance pre-filter + pro/anti/apolitical tagging."""

    @abstractmethod
    def classify(self, headline: str, body_text: str) -> dict:
        """Returns a dict shaped like SystemTag's fields: classification,
        jurisdiction, ruling_party, confidence_score. jurisdiction/
        ruling_party may be None for an apolitical result.
        """
        raise NotImplementedError


def get_embedding_provider() -> EmbeddingProvider:
    """Factory to be implemented in Phase 2, reading settings.embedding_provider."""
    raise NotImplementedError("Embedding providers land in Phase 2")


def get_classification_provider() -> ClassificationProvider:
    """Factory to be implemented in Phase 2, reading settings.llm_provider."""
    raise NotImplementedError("Classification providers land in Phase 2")
