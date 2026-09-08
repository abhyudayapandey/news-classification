from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ClientUser(Base):
    """Section 13.6's client-portal login account - the piece Client's own
    docstring originally deferred ("nothing in this phase needs a client
    to ever log in") until building the actual portal was asked for.

    A ClientUser belongs to exactly one Client and can only ever see that
    client's own tracked entities, mentions, and ceiling status - never
    another client's data, and never the cross-client internal cost view
    that /admin/social-costs shows (that screen stays super-admin-only;
    app/routers/client_ui.py's dashboard is scoped to one client's own
    contract, a narrower disclosure than the internal aggregate view).

    Password hashing reuses app/auth/security.py, same scheme as Admin -
    no reason for a second hashing implementation for the same problem
    (verify a password against a stored bcrypt hash).

    `is_active` mirrors Admin.is_active / Client.active's "deactivate,
    don't delete" posture: revoking one login (e.g. an employee leaving
    the client's org) shouldn't require touching the Client record or any
    other login the same client might have.
    """

    __tablename__ = "client_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["Client"] = relationship(back_populates="users")
