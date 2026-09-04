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
