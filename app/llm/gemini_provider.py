"""Paid classification via Gemini. Not called by default - only used when
LLM_PROVIDER=gemini and GEMINI_API_KEY is set. Every call to classify()
here is a billed API request.
"""

import logging

from google import genai
from google.genai import types

from app.config import settings
from app.llm.base import (
    ClassificationProvider,
    ClassificationResult,
    EntitySentimentBatchItem,
    EntitySentimentProvider,
    EntitySentimentResult,
)
from app.llm.schema import (
    CLASSIFICATION_INSTRUCTIONS,
    ENTITY_SENTIMENT_BATCH_INSTRUCTIONS,
    FORCE_RELEVANT_INSTRUCTIONS,
    LLMClassificationOutput,
    LLMEntitySentimentBatchOutput,
    LLMEntitySentimentOutput,
    build_entity_sentiment_batch_user_prompt,
    build_entity_sentiment_instructions,
    build_user_prompt,
)
from app.models.enums import ClassificationTag, SubjectSentiment

logger = logging.getLogger(__name__)


class GeminiClassificationProvider(ClassificationProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or settings.gemini_model
        self.name = f"gemini:{self.model}"
        resolved_key = api_key or settings.gemini_api_key
        if not resolved_key:
            raise ValueError("GEMINI_API_KEY is not set - required to use the gemini classification provider.")
        self._client = genai.Client(api_key=resolved_key)

    def _call(self, instructions: str, headline: str, body_text: str) -> ClassificationResult:
        response = self._client.models.generate_content(
            model=self.model,
            contents=f"{instructions}\n\n{build_user_prompt(headline, body_text)}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMClassificationOutput,
            ),
        )
        parsed: LLMClassificationOutput = response.parsed
        return ClassificationResult(
            classification=ClassificationTag(parsed.classification),
            jurisdiction=parsed.jurisdiction,
            confidence_score=parsed.confidence_score,
        )

    def classify(self, headline: str, body_text: str) -> ClassificationResult:
        return self._call(CLASSIFICATION_INSTRUCTIONS, headline, body_text)

    def classify_forcing_establishment_relevant(self, headline: str, body_text: str) -> ClassificationResult:
        result = self._call(FORCE_RELEVANT_INSTRUCTIONS, headline, body_text)
        if result.classification == ClassificationTag.APOLITICAL:
            logger.warning("Gemini ignored FORCE_RELEVANT_INSTRUCTIONS and returned apolitical for %r", headline)
        return result


class GeminiEntitySentimentProvider(EntitySentimentProvider):
    """Section 13.2. Same billing posture as GeminiClassificationProvider
    above. See app/llm/local_entity_sentiment.py's module docstring for
    the "one call per entity, not per article" cost this multiplies by.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or settings.gemini_model
        self.name = f"gemini:{self.model}"
        resolved_key = api_key or settings.gemini_api_key
        if not resolved_key:
            raise ValueError("GEMINI_API_KEY is not set - required to use the gemini entity-sentiment provider.")
        self._client = genai.Client(api_key=resolved_key)

    def classify_subject_sentiment(self, headline: str, body_text: str, entity_name: str) -> EntitySentimentResult:
        response = self._client.models.generate_content(
            model=self.model,
            contents=f"{build_entity_sentiment_instructions(entity_name)}\n\n{build_user_prompt(headline, body_text)}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMEntitySentimentOutput,
            ),
        )
        parsed: LLMEntitySentimentOutput = response.parsed
        return EntitySentimentResult(
            sentiment=SubjectSentiment(parsed.sentiment), confidence_score=parsed.confidence_score
        )

    def classify_subject_sentiment_batch(
        self, items: list[EntitySentimentBatchItem]
    ) -> dict[int, EntitySentimentResult]:
        """One billed call for the whole list, not one per item - see
        EntitySentimentProvider.classify_subject_sentiment_batch's
        docstring for why this exists. Any index the model fails to
        return (a rare structured-output miss, not a design assumption)
        is simply absent from the result dict; callers already treat a
        missing/failed score as "leave this one for next time" via their
        own per-item try/except, so no fallback call is made here.
        """
        if not items:
            return {}
        response = self._client.models.generate_content(
            model=self.model,
            contents=f"{ENTITY_SENTIMENT_BATCH_INSTRUCTIONS}\n\n{build_entity_sentiment_batch_user_prompt(items)}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LLMEntitySentimentBatchOutput,
            ),
        )
        parsed: LLMEntitySentimentBatchOutput = response.parsed
        return {
            r.index: EntitySentimentResult(sentiment=SubjectSentiment(r.sentiment), confidence_score=r.confidence_score)
            for r in parsed.results
        }
