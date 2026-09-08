from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EntitySocialConfig(Base):
    """One row per Entity - the *shared* side of social listening's two-
    layer design (see ClientSubject's docstring for the other side).

    Why two layers, not one global toggle or one per-client toggle:
    "should we fetch X data for this entity at all" and "does this
    specific client have access to it" are genuinely different questions
    that happen to be correlated. Collapsing them into a single per-client
    flag would mean fetching (and paying for) the same public X data once
    per client tracking the same entity - wasteful, and wrong besides,
    since X's own terms are about the content being fetched, not who
    happens to be looking at it afterward. Collapsing them into a single
    global flag would mean one client's access decision silently exposes
    (or removes) X data for every OTHER client tracking the same entity,
    with no per-client record of who actually authorized the spend.
    Keeping them separate means: the fetch (and its real dollar cost)
    happens at most once per entity regardless of how many clients track
    it (this table), while each client's own permission and contracted
    ceiling stays theirs alone (ClientSubject).

    `x_active` is a **derived, cached** field - the real gating decision
    (app/social/pipeline.py's `_entity_has_active_x_access`) always
    re-checks ClientSubject live at fetch time rather than trusting this
    column, so a stale cache here can never cause an unauthorized fetch or
    a missed one. This column exists purely so a display (the super-admin
    cost screen) doesn't need to re-run that join just to show "is X
    currently on for this entity" - kept in sync as a side effect of every
    fetch-decision check, not as the source of truth.

    `x_spend_usd` is scoped to the *current* period (`x_spend_period_start`,
    the first of the current calendar month) - reset lazily (checked and
    rolled over the next time this entity's cost is touched, not on a
    schedule) rather than kept as a lifetime total, since ClientSubject's
    ceilings are explicitly monthly. See app/social/pipeline.py's
    `_roll_spend_period_if_needed`.
    """

    __tablename__ = "entity_social_configs"

    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), primary_key=True)

    x_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    x_spend_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"), server_default="0")
    x_spend_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    x_last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # YouTube costs nothing per Section's "free tier, always available, no
    # cost gating needed" - tracked here only for "when did we last check"
    # operational visibility, not spend.
    youtube_last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entity: Mapped["Entity"] = relationship(back_populates="social_config")
