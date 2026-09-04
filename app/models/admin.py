from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AdminRole


class Admin(Base):
    """Section 6: Admin, extended in Phase 3 with auth fields.

    is_active supports Section 10's "deactivate, don't hard-delete" - a
    deactivated admin keeps their full review history (Review.admin_id
    stays valid), just stops receiving new queue assignments and can't log
    in. See app/review/assignment.py for how a deactivation reassigns that
    admin's pending (unreviewed) queue to remaining active admins.
    """

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(SAEnum(AdminRole, name="admin_role"), nullable=False, default=AdminRole.ADMIN)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reviews: Mapped[list["Review"]] = relationship(back_populates="admin")
    assigned_articles: Mapped[list["Article"]] = relationship(back_populates="assigned_admin")
