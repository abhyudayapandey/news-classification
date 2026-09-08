"""Paid classification via OpenAI. Not called by default - only used when
LLM_PROVIDER=openai and OPENAI_API_KEY is set. Every call to classify()
here is a billed API request.
"""

import logging

from openai import OpenAI

from app.config import settings
from app.llm.base import ClassificationProvider, ClassificationResult, EntitySentimentProvider, EntitySentimentResult
from app.llm.schema import (
    CLASSIFICATION_INSTRUCTIONS,
    FORCE_RELEVANT_INSTRUCTIONS,
    LLMClassificationOutput,
    LLMEntitySentimentOutput,
    build_entity_sentiment_instructions,
    build_user_prompt,
)
from app.models.enums import ClassificationTag, SubjectSentiment

logger = logging.getLogger(__name__)


class OpenAIClassificationProvider(ClassificationProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or settings.openai_model
        self.name = f"openai:{self.model}"
        resolved_key = api_key or settings.openai_api_key
        if not resolved_key:
            raise ValueError("OPENAI_API_KEY is not set - required to use the openai classification provider.")
        self._client = OpenAI(api_key=resolved_key)

    def _call(self, system_prompt: str, headline: str, body_text: str) -> ClassificationResult:
        completion = self._client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_user_prompt(headline, body_text)},
            ],
            response_format=LLMClassificationOutput,
        )
        parsed: LLMClassificationOutput = completion.choices[0].message.parsed
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
            # The model didn't follow instructions - fall back to whichever
            # of pro/anti it's plausible to guess is closer isn't available
            # here, so just log it; the caller (app/processing/pipeline.py)
            # still records entity_trigger_override=True either way.
            logger.warning("OpenAI ignored FORCE_RELEVANT_INSTRUCTIONS and returned apolitical for %r", headline)
        return result


class OpenAIEntitySentimentProvider(EntitySentimentProvider):
    """Section 13.2. Same client/model/billing posture as
    OpenAIClassificationProvider above - not called unless LLM_PROVIDER=
    openai and OPENAI_API_KEY is set, and every call here is a billed
    request. See app/llm/local_entity_sentiment.py's module docstring for
    the "one call per entity, not per article" cost this multiplies by.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or settings.openai_model
        self.name = f"openai:{self.model}"
        resolved_key = api_key or settings.openai_api_key
        if not resolved_key:
            raise ValueError("OPENAI_API_KEY is not set - required to use the openai entity-sentiment provider.")
        self._client = OpenAI(api_key=resolved_key)

    def classify_subject_sentiment(self, headline: str, body_text: str, entity_name: str) -> EntitySentimentResult:
        completion = self._client.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": build_entity_sentiment_instructions(entity_name)},
                {"role": "user", "content": build_user_prompt(headline, body_text)},
            ],
            response_format=LLMEntitySentimentOutput,
        )
        parsed: LLMEntitySentimentOutput = completion.choices[0].message.parsed
        return EntitySentimentResult(
            sentiment=SubjectSentiment(parsed.sentiment), confidence_score=parsed.confidence_score
        )
