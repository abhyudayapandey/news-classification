from datetime import datetime

from sqlalchemy import ARRAY, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import EntityType


class Entity(Base):
    """Section 13.1: a named political entity (person or party) this
    platform can track mentions of - the data model the future B2B client
    portal (Section 13.6) queries against, though nothing client-facing is
    built yet.

    Promoted out of app/processing/entity_triggers.py, which only ever
    detected *that* some political entity was present (a binary trigger for
    the apolitical safety net) - never *which* one. That trigger net is
    unchanged and still serves its own purpose; this table is a separate,
    queryable record of specific entities, seeded from
    app/data/entity_seed.py (which reuses and extends the trigger net's
    party list - see that module for exactly what's seeded and, just as
    important, what's deliberately left out for lack of confident
    knowledge).

    `name` is unique and is the canonical display form (e.g. "Narendra
    Modi", not "PM Modi") - variant forms belong in `aliases`, not as a
    second Entity row, so a client's "show me every article about X" query
    (Section 13.1) never has to know to search under multiple names for the
    same real-world subject.
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[EntityType] = mapped_column(SAEnum(EntityType, name="entity_type"), nullable=False)
    # Name variants matched in addition to `name` itself - e.g. "PM Modi",
    # "Narendra Modi" both resolving to the one Entity named "Narendra
    # Modi". See app/processing/entities.py for how these are matched (the
    # same word-boundary regex approach as entity_triggers.py, deliberately
    # not an NER model - see that module's docstring for why).
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False, default=list, server_default="{}")
    # Free-form: party affiliation + role for a person (e.g. {"party": "BJP",
    # "role": "Prime Minister"}), or jurisdiction scope for a party (e.g.
    # {"scope": "national"} vs {"scope": "state", "state": "Tamil Nadu"}).
    # JSONB rather than fixed columns since what's worth recording differs
    # by entity type and will keep evolving - see app/data/entity_seed.py
    # for what's actually populated today.
    entity_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mentions: Mapped[list["ArticleEntity"]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    # Section 13 social listening additions - see the respective models'
    # docstrings for the shared-vs-per-client design these two split apart.
    social_config: Mapped["EntitySocialConfig | None"] = relationship(
        back_populates="entity", uselist=False, cascade="all, delete-orphan"
    )
    social_mentions: Mapped[list["SocialMention"]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    client_subjects: Mapped[list["ClientSubject"]] = relationship(back_populates="entity", cascade="all, delete-orphan")
