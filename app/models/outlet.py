from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Outlet(Base):
    """Section 6: Outlet. Hidden from admin review view, visible to super admin."""

    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    rss_feed_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Lets ingestion skip a feed (e.g. dead URL) without deleting outlet history.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="outlet")
