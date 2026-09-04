from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ReviewDecision


class Review(Base):
    """Section 6: Article.reviews[] - one-to-many now so multi-admin
    reconciliation (Section 11, deferred) can be added later without a
    schema change; POC code only ever creates one row per article.
    """

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=False)
    # Indexed: Phase 3's filterable review listing (app/review/queries.py)
    # and the future super-admin analytics dashboard both filter/group by
    # admin, decision, and time range - this is groundwork explicitly asked
    # to be query-efficient, not premature optimization.
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"), nullable=False, index=True)
    final_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[ReviewDecision] = mapped_column(
        SAEnum(ReviewDecision, name="review_decision"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    article: Mapped["Article"] = relationship(back_populates="reviews")
    admin: Mapped["Admin"] = relationship(back_populates="reviews")
