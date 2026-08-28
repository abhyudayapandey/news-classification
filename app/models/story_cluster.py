from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class StoryCluster(Base):
    """Section 6: Story Cluster. Nothing populates this until Phase 2's
    embedding-based clustering exists; the table is created now so Article
    can carry a real FK from day one.
    """

    __tablename__ = "story_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Section 4.3: set True when any member article's establishment-relevance
    # changes post-publish, re-flagging the whole cluster for review.
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="cluster")
