from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import EntityProminence, ReviewDecision, SubjectSentiment


class ArticleEntity(Base):
    """Section 13.1 + 13.2: one article's mention of one entity - prominence
    (how central the entity is to this article) and subject-specific
    sentiment (how this article portrays that entity specifically), scored
    independently.

    Composite (article_id, entity_id) primary key rather than a surrogate
    id: this is a genuine many-to-many join row, and an article can only
    have ONE prominence/sentiment record per entity (repeated mentions of
    the same entity accumulate into this one row's mention_count, they
    don't create additional rows) - the same reasoning SystemTag uses
    article_id as its own primary key rather than a surrogate one.

    Deliberately named "subject_sentiment", never "pro"/"anti" anywhere in
    this table: this measures sentiment toward ONE entity, independent of
    the article's overall pro-establishment/anti-establishment framing
    (SystemTag.classification / Article.published_tag) - an anti-
    establishment article can be favorable toward an opposition figure it
    quotes approvingly. Conflating the two axes' naming would misrepresent
    what each one measures (see the planning doc's Section 13.2), so this
    table has no "classification" column at all - only "sentiment".

    system_subject_sentiment mirrors SystemTag.classification (the
    classifier's raw call); published_subject_sentiment mirrors
    Article.published_tag (null until an admin reviews it, per Section
    13.2's "same pipeline shape... system-generated, then admin-reviewed").
    Unlike Article, there is no reviews[]-style history table here - the
    review is folded into the SAME admin action that reviews the article's
    establishment tag (app/routers/admin_ui.py's submit_review), so a flat
    "who reviewed this, when, and did they agree" on this row itself is
    enough; a full multi-row audit trail wasn't asked for and would be
    speculative for what's currently a single-admin-per-article model.
    """

    __tablename__ = "article_entities"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), primary_key=True)

    # --- Prominence (13.1) - see app/processing/entities.py for how these
    # three raw signals are computed and combined into `prominence`. Stored
    # alongside the derived category (not just the category alone) so a
    # future re-tuning of the heuristic's weights/thresholds can recompute
    # `prominence` from these without re-scanning the article's text.
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    in_headline: Mapped[bool] = mapped_column(Boolean, nullable=False)
    first_mention_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    prominence: Mapped[EntityProminence] = mapped_column(
        SAEnum(EntityProminence, name="entity_prominence"), nullable=False
    )

    # --- Subject sentiment (13.2) ---
    system_subject_sentiment: Mapped[SubjectSentiment] = mapped_column(
        SAEnum(SubjectSentiment, name="subject_sentiment"), nullable=False
    )
    subject_sentiment_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Which EntitySentimentProvider produced this - same provenance idea as
    # SystemTag.provider, kept per-row (not just per-article) since a future
    # provider swap could in principle be evaluated per entity.
    subject_sentiment_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    published_subject_sentiment: Mapped[SubjectSentiment | None] = mapped_column(
        SAEnum(SubjectSentiment, name="subject_sentiment"), nullable=True
    )
    subject_sentiment_decision: Mapped[ReviewDecision | None] = mapped_column(
        SAEnum(ReviewDecision, name="review_decision"), nullable=True
    )
    subject_sentiment_reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"), nullable=True)
    subject_sentiment_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    article: Mapped["Article"] = relationship(back_populates="entity_mentions")
    entity: Mapped["Entity"] = relationship(back_populates="mentions")
    reviewed_by: Mapped["Admin | None"] = relationship()
