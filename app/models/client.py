from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Client(Base):
    """Section 13.6's B2B client portal, minimal slice: a paying client's
    identity record. Built now, ahead of the portal itself, because
    per-client social-listening access (ClientSubject.x_access, this
    phase) has nowhere to attach without it - NOT a signal that the portal
    (login accounts, client-facing dashboards) is starting now. There is
    deliberately no ClientUser here yet (Section 13.6's login-account
    table) - nothing in this phase needs a client to ever log in.

    `active=False` (rather than deleting a row) is the same "deactivate,
    don't hard-delete" posture as Admin (Phase 3) - a cancelled client's
    history (which entities they tracked, what they were billed) stays
    intact, and app/social/pipeline.py's access check excludes inactive
    clients from triggering new X spend without erasing the record of
    what they used to have access to.
    """

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subjects: Mapped[list["ClientSubject"]] = relationship(back_populates="client", cascade="all, delete-orphan")
