"""Section 13.6's actual client-facing portal: a logged-in ClientUser sees
only their own client's tracked entities, only the mentions their
ClientSubject.x_access actually permits, and only their own contracted
ceiling against their own entity's spend - never another client's data,
and never the cross-client aggregate view that /admin/social-costs shows
(that stays super-admin-only, per Section 13's own instruction that it
"could never be the one shared on a client call").

Visibility enforcement lives here, at query time, exactly as
SocialMention's docstring describes: mentions are stored once per
(entity, source, url) regardless of which clients can see them, and this
router is the one place that decides what a given login is allowed to
see, by checking their own ClientSubject rows rather than by any
duplicated per-client copy of the data.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.client_session import get_current_client_user, get_current_client_user_optional
from app.auth.security import verify_password
from app.db import get_db
from app.models import ClientSubject, ClientUser, Entity, EntitySocialConfig, SocialMention
from app.models.enums import SocialSource

router = APIRouter(prefix="/client", tags=["client-portal"])
templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template: str, current_client_user: ClientUser | None, status_code: int = 200, **context):
    return templates.TemplateResponse(
        request, template, {"current_client_user": current_client_user, **context}, status_code=status_code
    )


@router.get("/")
def client_root(current_client_user: ClientUser | None = Depends(get_current_client_user_optional)):
    return RedirectResponse("/client/dashboard" if current_client_user else "/client/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def client_login_form(request: Request, current_client_user: ClientUser | None = Depends(get_current_client_user_optional)):
    if current_client_user:
        return RedirectResponse("/client/dashboard", status_code=303)
    return render(request, "client_login.html", None)


@router.post("/login")
def client_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(ClientUser).filter(ClientUser.username == username).one_or_none()
    if (
        user is None
        or not user.is_active
        or not user.client.active
        or not verify_password(password, user.password_hash)
    ):
        return render(request, "client_login.html", None, status_code=401, error="Invalid username or password.")
    request.session["client_user_id"] = user.id
    return RedirectResponse("/client/dashboard", status_code=303)


@router.post("/logout")
def client_logout(request: Request):
    request.session.pop("client_user_id", None)
    return RedirectResponse("/client/login", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
def client_dashboard(
    request: Request,
    current_client_user: ClientUser = Depends(get_current_client_user),
    db: Session = Depends(get_db),
):
    subjects = (
        db.query(ClientSubject)
        .join(Entity, Entity.id == ClientSubject.entity_id)
        .filter(ClientSubject.client_id == current_client_user.client_id)
        .order_by(Entity.name.asc())
        .all()
    )
    rows = []
    for s in subjects:
        config = db.get(EntitySocialConfig, s.entity_id)
        # Only this client's own entity's spend - never another client's,
        # and never the cross-entity aggregate view. Defaults to 0 (not
        # None) when x_access is True but no fetch has happened yet for
        # this entity (EntitySocialConfig is only created lazily on first
        # fetch - see app/social/pipeline.py's _get_or_create_config).
        current_spend = (config.x_spend_usd if config is not None else Decimal("0")) if s.x_access else None
        rows.append({
            "entity": s.entity,
            "x_access": s.x_access,
            "x_spend_ceiling_usd": s.x_spend_ceiling_usd,
            "current_spend_usd": current_spend,
        })
    return render(request, "client_dashboard.html", current_client_user, subjects=rows)


@router.get("/entities/{entity_id}", response_class=HTMLResponse)
def client_entity_detail(
    entity_id: int,
    request: Request,
    current_client_user: ClientUser = Depends(get_current_client_user),
    db: Session = Depends(get_db),
):
    subject = db.get(ClientSubject, (current_client_user.client_id, entity_id))
    if subject is None:
        # Not tracked by this client - redirect rather than 404, so this
        # never confirms or denies that the entity exists at all to a
        # client who isn't tracking it.
        return RedirectResponse("/client/dashboard", status_code=303)

    youtube_mentions = (
        db.query(SocialMention)
        .filter(SocialMention.entity_id == entity_id, SocialMention.source == SocialSource.YOUTUBE)
        .order_by(SocialMention.fetched_at.desc())
        .limit(25)
        .all()
    )
    x_mentions = []
    if subject.x_access:
        x_mentions = (
            db.query(SocialMention)
            .filter(SocialMention.entity_id == entity_id, SocialMention.source == SocialSource.X)
            .order_by(SocialMention.fetched_at.desc())
            .limit(25)
            .all()
        )

    config = db.get(EntitySocialConfig, entity_id)
    current_spend = (config.x_spend_usd if config is not None else Decimal("0")) if subject.x_access else None
    return render(
        request, "client_entity_detail.html", current_client_user,
        entity=subject.entity, subject=subject,
        youtube_mentions=youtube_mentions, x_mentions=x_mentions,
        current_spend_usd=current_spend,
    )
