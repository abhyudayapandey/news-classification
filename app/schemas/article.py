from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    headline: str
    body_text: str
    url: str
    outlet_id: int
    published_at: datetime
    ingested_at: datetime
    duplicate_of_id: int | None
    published_tag: str | None


class IngestOutletResult(BaseModel):
    outlet_name: str
    fetched: int
    inserted_new: int
    inserted_duplicate: int
    skipped_existing: int
    error: str | None
