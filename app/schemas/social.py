from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import SocialSource


class SocialMentionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_id: int
    source: SocialSource
    content_text: str
    author: str | None
    posted_at: datetime | None
    url: str
    fetched_at: datetime
    cost_usd: Decimal


class SocialFetchRunResult(BaseModel):
    entities_scanned: int
    youtube_posts_read: int
    x_posts_read: int
    x_entities_fetched: int
    x_entities_skipped: int
    x_cost_incurred_usd: Decimal
    errors: list[str]
