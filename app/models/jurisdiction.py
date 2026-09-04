from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JurisdictionRulingParty(Base):
    """Section 6 / 4.2: date-ranged jurisdiction -> ruling party lookup.

    effective_to = NULL means "still in effect". Must be updated by hand as
    governments change (e.g. a state election) - there is no automated feed
    for this, by design (Section 4.2 flags this as a silent-mislabeling risk
    if left stale).
    """

    __tablename__ = "jurisdiction_ruling_parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction: Mapped[str] = mapped_column(String(128), nullable=False)
    ruling_party: Mapped[str] = mapped_column(String(128), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
