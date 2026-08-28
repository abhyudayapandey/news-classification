from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Article(Base):
    """Section 6: Article.

    cluster_id and system_tag stay nullable in Phase 1 - nothing populates
    them until Phase 2 (clustering) and the classifier exist. duplicate_of_id
    implements the Section 5 wire-copy dedup: a non-null value means "this
    row is a verbatim duplicate of another outlet's copy of the same wire
    story", and Phase 2/3 queries should filter WHERE duplicate_of_id IS NULL
    to get one canonical article per story before clustering/review.
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
    # reviews[]"). Null until an admin has reviewed the article.
    published_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    outlet: Mapped["Outlet"] = relationship(back_populates="articles")
    cluster: Mapped["StoryCluster | None"] = relationship(back_populates="articles")
    duplicate_of: Mapped["Article | None"] = relationship(remote_side=[id])
    system_tag: Mapped["SystemTag | None"] = relationship(
        back_populates="article", uselist=False, cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="article", cascade="all, delete-orphan", order_by="Review.timestamp"
    )
