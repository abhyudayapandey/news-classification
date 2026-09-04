from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import EMBEDDING_DIM
from app.db import Base


class Article(Base):
    """Section 6: Article, extended in Phase 2 with embedding/clustering
    fields not present in the original spec.

    duplicate_of_id implements the Section 5 wire-copy dedup: a non-null
    value means "this row is a verbatim duplicate of another outlet's copy
    of the same wire story". Clustering/classification (Phase 2) and review
    (Phase 3) should filter WHERE duplicate_of_id IS NULL to work on one
    canonical article per story - the pipeline in app/processing never
    processes a duplicate row directly.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Original article URL - used for idempotent re-ingestion (skip if seen).
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    # RSS entry guid, when the feed provides one. Not unique across feeds.
    guid: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), nullable=False)
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("story_clusters.id"), nullable=True)

    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # SHA-256 of normalized (headline + body) text - Section 5 dedup.
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)

    # Copy of the winning review's final_tag once published (Section 6:
    # "POC = copy of the single review; future = e.g. majority vote of
    # reviews[]"). Null until an admin has reviewed the article - EXCEPT for
    # apolitical articles, which the pipeline sets directly (Section 4.3:
    # apolitical skips straight to publish, no review needed).
    published_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Phase 2 additions (not in the original Section 6 spec) ---

    # Local MiniLM embedding of (headline + body_text), used for clustering
    # and as the substrate for embedding-similarity zero-shot classification
    # (see app/llm/local_classification.py). Fixed dimension because only
    # one embedding provider is active at a time in this schema - adding a
    # second provider's embeddings (different dimension) would need a new
    # column or table, not a resize of this one. Not indexed (no ivfflat/
    # hnsw) - POC-scale full-scan cosine distance via pgvector's <=>
    # operator is fast enough and needs no index maintenance.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    # Which model produced `embedding`, e.g. "local:sentence-transformers/
    # all-MiniLM-L6-v2" - recorded for provenance/debugging. Only one
    # embedding provider is active at a time (see EMBEDDING_PROVIDER in
    # config), so clustering never actually compares embeddings from two
    # different models today; if a second provider is ever added, this
    # column is what a mixed-model guard in app/processing/clustering.py
    # would need to check against - not implemented now since it can't
    # happen yet.
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Section 4.3's entity-trigger net fired: the classifier's first pass
    # called this article apolitical, but it mentions a political entity
    # (MLA/MP, ministry, party, government tender), so the apolitical tag
    # was overridden and it was routed through pro/anti classification
    # instead. Recorded so a future admin queue can prioritize/flag these -
    # they're exactly the cases Section 4.3 says need a second look.
    entity_trigger_override: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # --- Phase 3 additions: Section 7 stage 6 (queue) ---

    # Section 5: "Each admin has their own queue (no overlap)". Set by
    # app/review/assignment.py once an article is establishment-relevant
    # and classified; NULL means "not yet queued" (still apolitical,
    # unclassified, or a duplicate that never enters review at all).
    assigned_admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), nullable=True, index=True)
    # When this article entered its assigned admin's queue - the clock the
    # 48-hour SLA (Section 5) is measured against. Deliberately not
    # published_at: an article can sit unclassified for a while after
    # publication (ingestion/processing lag), and the SLA is about review
    # turnaround, not how old the underlying news is. Queue *order* is
    # still oldest published_at first per Section 5's literal wording.
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Best-effort full-text scrape of the article's own page (Section 5:
    # admins need enough text to review accurately, which the RSS teaser in
    # body_text often isn't). See app/review/scraping.py's module docstring
    # for the legal/ethical posture - this is for internal admin review
    # only, never shown to or stored for an end user, and app/review/
    # assignment.py only attempts it for articles that actually reach an
    # admin's queue (never for apolitical articles, which are never
    # reviewed at all). NULL means "not attempted yet"; scrape_attempted_at
    # non-null with scraped_body_text still NULL means "tried and failed" -
    # see scrape_error for why. The review UI falls back to body_text (the
    # RSS teaser) when this is unavailable.
    scraped_body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scrape_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scrape_error: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    outlet: Mapped["Outlet"] = relationship(back_populates="articles")
    cluster: Mapped["StoryCluster | None"] = relationship(back_populates="articles")
    assigned_admin: Mapped["Admin | None"] = relationship(back_populates="assigned_articles")
    duplicate_of: Mapped["Article | None"] = relationship(remote_side=[id])
    system_tag: Mapped["SystemTag | None"] = relationship(
        back_populates="article", uselist=False, cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", order_by="Review.timestamp"
    )
