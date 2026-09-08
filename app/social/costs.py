"""Section 13's super-admin cost visibility + client access management.
Kept separate from app/social/pipeline.py (which fetches and accrues
cost) - this module only reads/reports on what's already accrued, and
manages the ClientSubject grants that decide future fetching, but never
itself talks to X or YouTube.
"""

import enum
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Client, ClientSubject, Entity, EntitySocialConfig


class CeilingStatus(str, enum.Enum):
    OK = "ok"
    APPROACHING = "approaching"
    HIT = "hit"
    NO_ACCESS = "no_access"  # x_access is False - this client isn't paying for X on this entity at all
    NO_CEILING = "no_ceiling"  # x_access True but no ceiling on record - a setup gap, not a spend problem


@dataclass
class ClientCostStatus:
    client_id: int
    client_name: str
    entity_id: int
    entity_name: str
    x_access: bool
    x_spend_ceiling_usd: Decimal | None
    entity_current_spend_usd: Decimal
    status: CeilingStatus


def grant_x_access(db: Session, client_id: int, entity_id: int, spend_ceiling_usd: Decimal) -> ClientSubject:
    """The only way x_access ever becomes True - enforces the one rule
    that makes the alerting system meaningful: you cannot grant access
    without a ceiling to alert against. Idempotent (updates in place if a
    ClientSubject row for this client+entity already exists, e.g. from
    being tracked without X access previously).
    """
    if spend_ceiling_usd <= 0:
        raise ValueError("spend_ceiling_usd must be positive - granting X access requires a real ceiling to alert against.")

    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is None:
        subject = ClientSubject(client_id=client_id, entity_id=entity_id)
        db.add(subject)
    subject.x_access = True
    subject.x_spend_ceiling_usd = spend_ceiling_usd
    db.commit()
    return subject


def revoke_x_access(db: Session, client_id: int, entity_id: int) -> ClientSubject | None:
    """Turns off this client's access without deleting the tracking
    relationship itself (they can still track the entity without X data) -
    the next fetch call re-checks live access and simply won't fetch X for
    this entity anymore if no other client's grant keeps it active.
    """
    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is None:
        return None
    subject.x_access = False
    db.commit()
    return subject


def _status_for(ceiling: Decimal | None, current_spend: Decimal, x_access: bool) -> CeilingStatus:
    if not x_access:
        return CeilingStatus.NO_ACCESS
    if ceiling is None:
        return CeilingStatus.NO_CEILING
    if current_spend >= ceiling:
        return CeilingStatus.HIT
    if current_spend >= ceiling * Decimal(str(settings.social_ceiling_warn_ratio)):
        return CeilingStatus.APPROACHING
    return CeilingStatus.OK


def list_client_cost_statuses(db: Session) -> list[ClientCostStatus]:
    """Every ClientSubject with x_access ever granted (current or
    revoked), each compared against its entity's real *shared* current-
    period spend - the per-client half of Section 13's "both visible"
    requirement. Informational only: nothing here throttles anything,
    per direct instruction - a HIT status is something for a super admin
    to act on (renegotiate, eat the overage, or ask the client), not an
    automatic cutoff of a contracted service.
    """
    subjects = (
        db.query(ClientSubject)
        .join(Client, Client.id == ClientSubject.client_id)
        .join(Entity, Entity.id == ClientSubject.entity_id)
        .filter(ClientSubject.x_access.is_(True))
        .all()
    )

    statuses = []
    for subject in subjects:
        config = db.get(EntitySocialConfig, subject.entity_id)
        current_spend = config.x_spend_usd if config is not None else Decimal("0")
        statuses.append(
            ClientCostStatus(
                client_id=subject.client_id,
                client_name=subject.client.name,
                entity_id=subject.entity_id,
                entity_name=subject.entity.name,
                x_access=subject.x_access,
                x_spend_ceiling_usd=subject.x_spend_ceiling_usd,
                entity_current_spend_usd=current_spend,
                status=_status_for(subject.x_spend_ceiling_usd, current_spend, subject.x_access),
            )
        )
    return statuses


@dataclass
class EntitySpendSummary:
    entity_id: int
    entity_name: str
    x_active: bool
    x_spend_usd: Decimal
    x_last_fetched_at: object  # datetime | None, left loose to avoid importing datetime just for the hint
    tracked_by_client_count: int


def list_entity_spend_summaries(db: Session) -> list[EntitySpendSummary]:
    """The entity-level half of "both visible": real running spend per
    entity, regardless of which/how many clients benefit from it - the
    shared-cost view that a per-client report alone can't show.
    """
    configs = db.query(EntitySocialConfig).filter(EntitySocialConfig.x_spend_usd > 0).all()
    summaries = []
    for config in configs:
        client_count = (
            db.query(ClientSubject)
            .join(Client, Client.id == ClientSubject.client_id)
            .filter(
                ClientSubject.entity_id == config.entity_id,
                ClientSubject.x_access.is_(True),
                Client.active.is_(True),
            )
            .count()
        )
        summaries.append(
            EntitySpendSummary(
                entity_id=config.entity_id,
                entity_name=config.entity.name,
                x_active=config.x_active,
                x_spend_usd=config.x_spend_usd,
                x_last_fetched_at=config.x_last_fetched_at,
                tracked_by_client_count=client_count,
            )
        )
    return summaries
