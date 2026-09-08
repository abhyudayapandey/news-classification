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
    #: whatever this provider produces, e.g. "local:sentence-transformers/all-MiniLM-L6-v2".
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
