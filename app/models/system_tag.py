from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ClassificationTag


class SystemTag(Base):
    """Section 6: Article.system_tag, modeled as its own 1:1 table.

    A dedicated table (rather than columns inlined on Article) makes the
    Phase 3 super-admin analytics view (system tag vs. admin decision,
    confidence calibration) a straightforward join/aggregate, and lets the
    classifier evolve (e.g. add a model_version column) without touching
    Article. Nothing writes to this table until Phase 2's classifier exists.

    jurisdiction/ruling_party are nullable because they only apply when
    classification is pro/anti (Section 4.2); an apolitical tag has neither.
    """

    __tablename__ = "system_tags"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    classification: Mapped[ClassificationTag] = mapped_column(
        SAEnum(ClassificationTag, name="classification_tag"), nullable=False
    )
    # "centre" or "state:<name>" - see JurisdictionRulingParty for the lookup table.
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ruling_party: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped["Article"] = relationship(back_populates="system_tag")
