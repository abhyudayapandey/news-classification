"""Shared structured-output schema and prompt for the LLM-backed
classification providers (OpenAI, Gemini). Both SDKs support passing a
Pydantic model as the response schema and getting a parsed instance back
directly - using the same model for both keeps their prompts and output
shape identical, so results are actually comparable across providers.
"""

from typing import Literal

from pydantic import BaseModel, Field

CLASSIFICATION_INSTRUCTIONS = """You are classifying a news article for an Indian news aggregation platform \
along a pro-establishment / anti-establishment / apolitical axis (deliberately not a US-style left/right axis).

Definitions:
- "pro-establishment": the article portrays the currently governing party/administration favorably.
- "anti-establishment": the article is critical of the currently governing party/administration.
- "apolitical": the article has no meaningful connection to government, politics, or public administration \
(e.g. sports, entertainment, weather, routine local news).

If the article is not apolitical, also identify which jurisdiction it concerns:
- "centre" for national/central government matters
- "state:<StateName>" for a specific state government matter, using the state's full English name \
(e.g. "state:Karnataka"), not an abbreviation

Set jurisdiction to null only when classification is "apolitical".

Set confidence_score (0.0-1.0) to your genuine confidence in this specific call - vary it based on how \
ambiguous the article actually is, rather than defaulting to a fixed value."""


class LLMClassificationOutput(BaseModel):
    classification: Literal["pro-establishment", "anti-establishment", "apolitical"]
    jurisdiction: str | None = Field(description="'centre' or 'state:<StateName>', or null if apolitical")
    confidence_score: float = Field(ge=0.0, le=1.0)


FORCE_RELEVANT_INSTRUCTIONS = (
    CLASSIFICATION_INSTRUCTIONS
    + """

IMPORTANT: This article has already been determined to mention a political entity (a politician, \
party, ministry, or government tender/contract) - it is NOT apolitical, even if that connection seems \
minor or incidental to the main subject. You MUST classify it as "pro-establishment" or \
"anti-establishment" and identify a jurisdiction. Do not return "apolitical" or a null jurisdiction."""
)


def build_user_prompt(headline: str, body_text: str) -> str:
    return f"Headline: {headline}\n\nBody:\n{body_text}"


ENTITY_SENTIMENT_INSTRUCTIONS_TEMPLATE = """You are scoring how a piece of Indian political content - a news \
article, a tweet/X post, or a YouTube video's title and description - portrays ONE SPECIFIC entity named below, \
a politician or political party.

This is deliberately NOT the same question as whether the content is pro-establishment or anti-establishment \
overall. It can be critical of the government while quoting an opposition figure approvingly, or supportive of \
the government while criticizing one minister by name. It can also praise a rival by unfavorable comparison \
("X is busy with photo-ops while Y is out working") - that is unfavorable to the entity being compared away from, \
even though no single word of direct criticism is used. You are scoring sentiment toward the named entity \
specifically, independent of the content's overall stance toward the government in power, and independent of \
whether the language is literal, comparative, or sarcastic. Content may be in English, Hindi, or Hindi-English \
code-switched (Hinglish) text - read it in whichever language(s) it's actually written in.

Entity to score: {entity_name}

Definitions:
- "favorable": the content portrays this entity positively - praising their actions, statements, competence, \
or achievements, or portraying them as winning/succeeding relative to a rival.
- "unfavorable": the content portrays this entity negatively - criticizing their actions, statements, or \
attributing failure/wrongdoing/controversy to them, INCLUDING when this is done implicitly by favorably \
comparing a rival to them.
- "neutral": the content mentions this entity factually (e.g. as a quoted source, or named in passing) without \
a clear positive or negative framing of them specifically.

Set confidence_score (0.0-1.0) to your genuine confidence in this specific call - vary it based on how \
ambiguous the sentiment toward this entity actually is, rather than defaulting to a fixed value."""


class LLMEntitySentimentOutput(BaseModel):
    sentiment: Literal["favorable", "unfavorable", "neutral"]
    confidence_score: float = Field(ge=0.0, le=1.0)


def build_entity_sentiment_instructions(entity_name: str) -> str:
    return ENTITY_SENTIMENT_INSTRUCTIONS_TEMPLATE.format(entity_name=entity_name)


ENTITY_SENTIMENT_BATCH_INSTRUCTIONS = """You are scoring how each of several separate, UNRELATED pieces of Indian \
political content (news article excerpts, tweets/X posts, or YouTube video titles/descriptions) portrays ONE \
SPECIFIC named entity per item - a politician or political party. Each item below names its own entity and is \
scored independently of every other item; do not let one item's content influence another's score.

This is deliberately NOT the same question as whether an item is pro-establishment or anti-establishment overall. \
An item can be critical of the government while quoting an opposition figure approvingly, or supportive of the \
government while criticizing one minister by name. It can also praise a rival by unfavorable comparison \
("X is busy with photo-ops while Y is out working") - that is unfavorable to the entity being compared away from, \
even with no direct criticism. You are scoring sentiment toward each item's named entity specifically, \
independent of the item's overall stance toward the government in power, and independent of whether the language \
is literal, comparative, or sarcastic. Items may be in English, Hindi, or Hindi-English code-switched (Hinglish) \
text - read each one in whichever language(s) it's actually written in.

Definitions:
- "favorable": the content portrays the named entity positively - praising their actions, statements, competence, \
or achievements, or portraying them as winning/succeeding relative to a rival.
- "unfavorable": the content portrays the named entity negatively - criticizing their actions, statements, or \
attributing failure/wrongdoing/controversy to them, INCLUDING when this is done implicitly by favorably \
comparing a rival to them.
- "neutral": the content mentions the named entity factually (e.g. as a quoted source, or named in passing) \
without a clear positive or negative framing of them specifically.

Score EVERY item below exactly once. Each item has an explicit index - echo that same index back in your \
corresponding result so scores can be matched to items; do not renumber, skip, merge, or invent items. Set each \
result's confidence_score (0.0-1.0) to your genuine confidence in that specific call, varied per item rather \
than a fixed value."""


class LLMEntitySentimentBatchItemOutput(BaseModel):
    index: int
    sentiment: Literal["favorable", "unfavorable", "neutral"]
    confidence_score: float = Field(ge=0.0, le=1.0)


class LLMEntitySentimentBatchOutput(BaseModel):
    results: list[LLMEntitySentimentBatchItemOutput]


def build_entity_sentiment_batch_user_prompt(items: list) -> str:
    """`items` is a list of app.llm.base.EntitySentimentBatchItem - typed
    as list[] here (not imported) to avoid this schema module depending on
    base.py; the two modules' dataclasses/BaseModels are matched by field
    name/shape, not by a shared import, same as the rest of this module's
    plain-dict-shaped prompt building.
    """
    blocks = [
        f"### Item {item.index}\nEntity to score: {item.entity_name}\nHeadline: {item.headline}\n\nBody:\n{item.body_text}"
        for item in items
    ]
    return "\n\n".join(blocks)
