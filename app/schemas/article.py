from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ClassificationTag


class SystemTagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    classification: ClassificationTag
    jurisdiction: str | None
    ruling_party: str | None
    confidence_score: float
    provider: str


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
    cluster_id: int | None
    embedding_model: str | None
    entity_trigger_override: bool
    system_tag: SystemTagOut | None


class IngestOutletResult(BaseModel):
    outlet_name: str
    fetched: int
    inserted_new: int
    inserted_duplicate: int
    skipped_existing: int
    error: str | None


class ClusterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic: str | None
    primary_source_url: str | None
    needs_review: bool
    article_count: int


class ProcessRunResult(BaseModel):
    processed: int
    new_clusters: int
    joined_existing_clusters: int
    apolitical: int
    pro_establishment: int
    anti_establishment: int
    entity_trigger_overrides: int
    clusters_flagged_needs_review: int
    unresolved_ruling_party: int
    remaining_unprocessed: int
    errors: list[str]
