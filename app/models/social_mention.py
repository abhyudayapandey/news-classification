from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import SeatType, SocialSource, SubjectSentiment


class SocialMention(Base):
    """One fetched X post or YouTube video mentioning a tracked Entity.
    Same table regardless of which client(s) can see it - client
    visibility is enforced at query time via ClientSubject, never by
    storing a duplicate copy per client (Section 13's own instruction: the
    fetch is shared, the data is shared, only access is per-client).

    `cost_usd` is the cost attributed to *this row specifically* - 0 for
    YouTube (free tier), `settings.x_cost_per_post_usd` for X, recorded at
    the moment this row was first stored. This is a per-item audit trail
    alongside EntitySocialConfig.x_spend_usd's running aggregate, not a
    substitute for it: the aggregate is incremented by the full read count
    of every fetch call (see app/social/pipeline.py), including re-reads
    of a post already stored here (X bills per read, not per new-to-us
    post) - so summing this column will not always reconcile exactly with
    the aggregate, and that's expected, not a bug to fix by making the two
    agree.

    Unique on (entity_id, source, url): the same post re-returned by a
    later fetch call is still billed again (see above) but not stored
    again - this constraint is what makes storage idempotent while cost
    accounting stays honest about repeat reads.
    """

    __tablename__ = "social_mentions"
    __table_args__ = (UniqueConstraint("entity_id", "source", "url", name="uq_social_mention_entity_source_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    source: Mapped[SocialSource] = mapped_column(SAEnum(SocialSource, name="social_source"), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"), server_default="0")

    # Same axis and provider pattern as ArticleEntity.system_subject_sentiment
    # (Section 13.2) - favorable/unfavorable/neutral toward the entity this
    # mention is about, not the platform's separate pro/anti-establishment
    # framing axis. Nullable: only ever set at storage time for a NEWLY
    # fetched mention (app/social/pipeline.py's store_new_mentions) - never
    # backfilled automatically for rows stored before this column existed.
    # Deliberately no review/approval workflow yet, unlike the article axis'
    # admin-reviewed published_subject_sentiment - this is system-generated
    # only for now, a scoped-out future phase per direct instruction.
    sentiment: Mapped[SubjectSentiment | None] = mapped_column(
        SAEnum(SubjectSentiment, name="subject_sentiment"), nullable=True
    )
    sentiment_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # A single denormalized "how engaged was this" number, recorded once at
    # fetch time and never updated afterward (re-polling a post's current
    # counts would cost another billed X read for no product benefit) -
    # YouTube's is the video's view count, X's is retweet+like+reply+quote
    # summed (see app/social/x_api.py). Used purely for display/sort
    # ordering (most-engaged-first, per direct instruction), never for cost
    # accounting - cost_usd above is the only column that feeds spend math.
    engagement_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Same content-derived geography axis as SystemTag's state/district/
    # constituency/seat_type (app/processing/geography.py), guessed from
    # `content_text` at storage time - never from anything assigned to the
    # Entity this mention is about. Set once when a mention is newly
    # stored (app/social/pipeline.py's store_new_mentions), same "never
    # re-computed on re-fetch" discipline as sentiment above.
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    constituency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seat_type: Mapped[SeatType | None] = mapped_column(SAEnum(SeatType, name="seat_type", create_type=False), nullable=True)

    entity: Mapped["Entity"] = relationship(back_populates="social_mentions")
