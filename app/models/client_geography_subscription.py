from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import SeatType


class ClientGeographySubscription(Base):
    """A client subscribing to a whole district or seat directly, rather
    than to a specific entity (ClientSubject) - the geography-map feature's
    upsell path: "content is always of the subscribed subject(s) only; a
    client who wants everything happening in a district/seat regardless of
    who it's about subscribes to that geography instead, priced
    separately." Reuses the same state/district/constituency/seat_type
    axis as SystemTag/SocialMention (app/processing/geography.py) so a
    subscription and a piece of content are compared on identical fields.

    Exactly one of `district` or (`constituency` + `seat_type`) is set per
    row - a district-level subscription surfaces every entity's content
    geo-tagged to that district; a constituency-level one surfaces every
    entity's content geo-tagged to that exact constituency+seat_type (an
    MP and MLA seat sharing a name are different subscriptions, same
    disambiguation as everywhere else this axis is used). Enforced at the
    application layer (app/routers/admin_ui.py's add_geography_subscription),
    not a DB constraint, matching ClientSubject.x_spend_ceiling_usd's own
    "permissive column, checked at the point of creation" precedent.

    news_access/youtube_access/x_access are visibility-only for all
    three here - unlike ClientSubject.x_access, which doubles as the
    permission to trigger real per-tweet-read spend on a not-yet-tracked
    entity, a geography subscription never causes any NEW fetching of
    its own: it only draws from entities some ClientSubject (this
    client's own or another client's) is already tracking. Turning this
    x_access on costs nothing extra to the platform, so there's no
    ceiling field here the way ClientSubject has one - same reasoning as
    youtube_access's own docstring, just extended to all three channels.
    Same payment-gating default (False) as ClientSubject though: a new
    geography subscription starts fully closed until a super admin turns
    each channel on once payment is actually received.
    """

    __tablename__ = "client_geography_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    constituency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seat_type: Mapped[SeatType | None] = mapped_column(SAEnum(SeatType, name="seat_type", create_type=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    news_access: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    youtube_access: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    x_access: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    client: Mapped["Client"] = relationship(back_populates="geography_subscriptions")

    @property
    def kind(self) -> str:
        return "constituency" if self.constituency else "district"

    @property
    def value(self) -> str:
        return self.constituency if self.constituency else self.district

    @property
    def label(self) -> str:
        if self.constituency:
            seat_label = f" ({self.seat_type.value.upper()})" if self.seat_type else ""
            return f"{self.state} – {self.constituency}{seat_label}"
        return f"{self.state} – {self.district} district"
