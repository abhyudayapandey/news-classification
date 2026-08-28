from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AdminRole


class Admin(Base):
    """Section 6: Admin. No auth fields yet - Phase 1 has no admin UI/login;
    those land alongside the review workflow in Phase 3.
    """

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(SAEnum(AdminRole, name="admin_role"), nullable=False, default=AdminRole.ADMIN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reviews: Mapped[list["Review"]] = relationship(back_populates="admin")
