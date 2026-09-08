from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ClientSubject(Base):
    """Section 13.6: which entities a client tracks - `client_id` +
    `entity_id` is the composite key (one row per client-per-entity, same
    shape as ArticleEntity's join). `backfilled` is carried over from the
    original planning-doc schema (Section 13.6's onboarding flow: a
    one-time historical-article backfill once a client's subject is
    linked) - not acted on by any code yet, since the onboarding flow
    itself is portal-phase work; the column exists so it isn't a schema
    change later.

    `x_access` + `x_spend_ceiling_usd` are this phase's addition, and are
    deliberately *per (client, entity)*, not a single per-client number:
    a PR agency tracking three subjects can reasonably want a different
    contracted budget for each. `x_access` is the per-client permission
    layer - separate from whether X fetching for the entity is actually
    happening at all (EntitySocialConfig.x_active, derived from whether
    *any* client's x_access is True for that entity - see
    app/models/entity_social_config.py's docstring for why these two
    layers can't be collapsed into one field).

    The ceiling is compared against the entity's *shared* current-period
    spend (EntitySocialConfig.x_spend_usd), not a per-client fractional
    slice of it: the underlying X fetch is genuinely shared infrastructure
    (one fetch serves every client tracking that entity), so "is this
    client near what they contracted for" is answered by comparing their
    own ceiling against the real total cost of the entity they have
    access to, not by trying to divide one fetch's cost across clients.
    """

    __tablename__ = "client_subjects"

    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    backfilled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    x_access: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Nullable: only meaningful once x_access is True. Enforced at the
    # application layer (app/social/pipeline.py's grant_x_access), not a
    # DB constraint - granting access without a ceiling is a real error
    # (the alert system has nothing to compare against), but the column
    # itself stays permissive so existing rows/migrations don't need a
    # backfilled value to satisfy a NOT NULL.
    x_spend_ceiling_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # Visibility-only, unlike x_access: YouTube is free/unconditional per
    # Section 13's own design (fetched for every tracked entity regardless
    # of any client's settings - see EntitySocialConfig's docstring), so
    # this never gates fetching, only whether THIS client's dashboard
    # renders YouTube mentions for this subject. Defaults to False, per
    # direct instruction: a newly tracked subject starts with nothing
    # visible on the client's dashboard - YouTube, X, and news coverage
    # are each turned on explicitly by a super admin once payment is
    # actually received, never implicitly on just because tracking began.
    youtube_access: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Same visibility-only shape as youtube_access, for the "News
    # articles" tab (published_tag-based articles mentioning this entity -
    # app/routers/client_ui.py). Also defaults False for the same
    # payment-gating reason - a client's News tab is empty until this is
    # explicitly turned on for them, even though the underlying articles
    # themselves are already public-site-published and cost nothing extra
    # to show (unlike X, there's no real spend being gated here - this is
    # purely "don't show a paying-nothing-yet client anything until
    # they've paid," not a cost-control mechanism like x_access is).
    news_access: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    client: Mapped["Client"] = relationship(back_populates="subjects")
    entity: Mapped["Entity"] = relationship(back_populates="client_subjects")
