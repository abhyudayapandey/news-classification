from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EntityProminence, EntityType, SubjectSentiment


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: EntityType
    aliases: list[str]
    entity_metadata: dict
    mention_count: int


class ArticleEntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    article_id: int
    entity_id: int
    entity_name: str
    mention_count: int
    in_headline: bool
    first_mention_offset: int
    prominence: EntityProminence
    system_subject_sentiment: SubjectSentiment
    subject_sentiment_confidence: float
    subject_sentiment_provider: str
    published_subject_sentiment: SubjectSentiment | None


class BackfillEntitiesResult(BaseModel):
    scanned: int
    new_mentions_classified: int
    remaining: int
