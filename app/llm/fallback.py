"""Wraps a paid provider with the local one as a fallback, so a billing
issue, rate limit, outage, or any other paid-API failure degrades an
article/mention to the free classifier's result instead of losing its
classification entirely (an unhandled exception would otherwise abort
that article's whole processing run - see app/processing/pipeline.py's
_process_one, which has no try/except around these calls).

Only wraps LLM_PROVIDER=openai/gemini - see app/llm/factory.py, the only
place that constructs these. When LLM_PROVIDER=local there's nothing to
fall back FROM, so the local provider is returned directly, unwrapped.

`self.name` is deliberately mutated on every call to reflect whichever
provider actually produced the last result, not just the intended
primary - every call site (app/processing/pipeline.py, app/social/
pipeline.py, app/social/backfill.py) reads `.name` immediately after
calling classify()/classify_subject_sentiment() on the SAME provider
instance to record provenance (SystemTag.provider /
ArticleEntity.subject_sentiment_provider), synchronously and one
article/mention at a time - never concurrently against the same
instance - so this is safe. Getting this right matters: silently
recording "openai:gpt-5-nano" as the provider for a result the local
classifier actually produced would be a real, misleading provenance bug.
"""

import logging

from app.llm.base import (
    ClassificationProvider,
    ClassificationResult,
    EntitySentimentBatchItem,
    EntitySentimentProvider,
    EntitySentimentResult,
)

logger = logging.getLogger(__name__)


class FallbackClassificationProvider(ClassificationProvider):
    def __init__(self, primary: ClassificationProvider, fallback: ClassificationProvider):
        self._primary = primary
        self._fallback = fallback
        self.name = primary.name

    def classify(self, headline: str, body_text: str) -> ClassificationResult:
        try:
            result = self._primary.classify(headline, body_text)
            self.name = self._primary.name
            return result
        except Exception:
            logger.exception(
                "Primary classification provider %s failed - falling back to %s for %r",
                self._primary.name, self._fallback.name, headline,
            )
            result = self._fallback.classify(headline, body_text)
            self.name = self._fallback.name
            return result

    def classify_forcing_establishment_relevant(self, headline: str, body_text: str) -> ClassificationResult:
        try:
            result = self._primary.classify_forcing_establishment_relevant(headline, body_text)
            self.name = self._primary.name
            return result
        except Exception:
            logger.exception(
                "Primary classification provider %s failed (forced-relevant call) - falling back to %s for %r",
                self._primary.name, self._fallback.name, headline,
            )
            result = self._fallback.classify_forcing_establishment_relevant(headline, body_text)
            self.name = self._fallback.name
            return result


class FallbackEntitySentimentProvider(EntitySentimentProvider):
    def __init__(self, primary: EntitySentimentProvider, fallback: EntitySentimentProvider):
        self._primary = primary
        self._fallback = fallback
        self.name = primary.name

    def classify_subject_sentiment(self, headline: str, body_text: str, entity_name: str) -> EntitySentimentResult:
        try:
            result = self._primary.classify_subject_sentiment(headline, body_text, entity_name)
            self.name = self._primary.name
            return result
        except Exception:
            logger.exception(
                "Primary entity-sentiment provider %s failed - falling back to %s for entity %r",
                self._primary.name, self._fallback.name, entity_name,
            )
            result = self._fallback.classify_subject_sentiment(headline, body_text, entity_name)
            self.name = self._fallback.name
            return result

    def classify_subject_sentiment_batch(
        self, items: list[EntitySentimentBatchItem]
    ) -> dict[int, EntitySentimentResult]:
        try:
            result = self._primary.classify_subject_sentiment_batch(items)
            self.name = self._primary.name
            return result
        except Exception:
            logger.exception(
                "Primary entity-sentiment provider %s failed on a %d-item batch - falling back to %s",
                self._primary.name, len(items), self._fallback.name,
            )
            result = self._fallback.classify_subject_sentiment_batch(items)
            self.name = self._fallback.name
            return result
