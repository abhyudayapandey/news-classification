from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ClassificationTag, SeatType


class SystemTag(Base):
    """Section 6: Article.system_tag, modeled as its own 1:1 table.

    A dedicated table (rather than columns inlined on Article) makes the
    Phase 3 super-admin analytics view (system tag vs. admin decision,
    confidence calibration) a straightforward join/aggregate, and lets the
    classifier evolve (e.g. add a model_version column) without touching
    Article. Nothing writes to this table until Phase 2's classifier exists.

    jurisdiction/ruling_party are nullable because they only apply when
    classification is pro/anti (Section 4.2); an apolitical tag has neither.

    state/district/constituency/seat_type are a separate axis from
    jurisdiction, computed for EVERY article regardless of classification
    (app/processing/geography.py, called unconditionally in
    app/processing/pipeline.py's _process_one - unlike jurisdiction, which
    only exists for pro/anti articles and is folded into the
    ClassificationProvider's own output). This is "what place is this
    content about", a plain fact about the text, not "which government's
    establishment does this framing concern" - the two questions are
    independent and a story can have one, both, or neither. Content-
    derived per direct instruction (article text - never a tag manually
    assigned to an Entity), so these are sparse and best-effort: null
    simply means the text didn't name a place clearly enough to guess.
    """

    __tablename__ = "system_tags"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    classification: Mapped[ClassificationTag] = mapped_column(
        SAEnum(ClassificationTag, name="classification_tag"), nullable=False
    )
    # "centre" or "state:<name>" - see JurisdictionRulingParty for the lookup table.
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ruling_party: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    constituency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seat_type: Mapped[SeatType | None] = mapped_column(SAEnum(SeatType, name="seat_type"), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Which ClassificationProvider produced this tag, e.g. "local",
    # "openai:gpt-4o-mini", "gemini:gemini-1.5-flash". This table stays
    # strictly 1:1 with Article per Section 6 (system_tag is singular in the
    # spec, unlike reviews[]) - re-classifying an article with a different
    # provider overwrites this row rather than adding a second one. Manual
    # side-by-side provider comparison is a separate CLI utility
    # (`python -m app.cli compare-providers`) that does not write here.
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped["Article"] = relationship(back_populates="system_tag")
