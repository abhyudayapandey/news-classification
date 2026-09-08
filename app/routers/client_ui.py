"""Section 13.6's actual client-facing portal: a logged-in ClientUser sees
only their own client's tracked entities and only the mentions their
ClientSubject.x_access/youtube_access actually permit - never another
client's data.

Real dollar spend/ceiling figures are deliberately NEVER rendered here,
not even the client's own - that's this platform's internal cost of
fetching (app/models/entity_social_config.py's x_spend_usd) and an
internal control (ClientSubject.x_spend_ceiling_usd) for a super admin to
manage, not a number to hand a paying client. What a client is billed and
what an API call actually costs the platform are two separate things that
must never be conflated by literally showing one as the other - a raw
cost-passthrough figure would also expose margin/pricing structure to the
client looking at it. This is stronger than just "no cross-client
aggregate" (which /admin/social-costs already restricts to super-admin
only) - it's "no dollar figures here at all, this client's own included."
A client sees only whether a subject's coverage is included or not.

Visibility enforcement lives here, at query time, exactly as
SocialMention's docstring describes: mentions are stored once per
(entity, source, url) regardless of which clients can see them, and this
router is the one place that decides what a given login is allowed to
see, by checking their own ClientSubject rows rather than by any
duplicated per-client copy of the data.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.client_session import get_current_client_user, get_current_client_user_optional
from app.auth.security import verify_password
from app.db import get_db
from app.models import Article, ArticleEntity, ClientSubject, ClientUser, Entity, SocialMention
from app.models.enums import SocialSource
from app.public.formatting import excerpt as make_excerpt
from app.public.formatting import format_jurisdiction

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
    rows = [
        {"entity": s.entity, "x_access": s.x_access, "youtube_access": s.youtube_access}
        for s in subjects
    ]
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

    youtube_mentions = []
    if subject.youtube_access:
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

    # Same "published_tag-based data only" standard as the B2C public site
    # (Section 13.6) - an unreviewed article never appears here just
    # because it happens to mention this entity. Eager-loaded outlet/
    # system_tag to avoid the same N+1 pattern already fixed on the admin
    # queue (app/routers/admin_ui.py's my_queue).
    stmt = (
        select(Article)
        .join(ArticleEntity, ArticleEntity.article_id == Article.id)
        .where(ArticleEntity.entity_id == entity_id, Article.published_tag.is_not(None))
        .order_by(Article.published_at.desc())
        .limit(25)
        .options(selectinload(Article.system_tag), selectinload(Article.outlet))
    )
    articles = list(db.scalars(stmt))
    news_articles = [
        {
            "headline": a.headline,
            "url": a.url,
            "outlet_name": a.outlet.name,
            "published_at": a.published_at,
            "published_tag": a.published_tag,
            "jurisdiction": format_jurisdiction(a.system_tag.jurisdiction) if a.system_tag else None,
            "ruling_party": a.system_tag.ruling_party if a.system_tag else None,
            "excerpt": make_excerpt(a.body_text) if a.body_text.strip() else None,
        }
        for a in articles
    ]

    return render(
        request, "client_entity_detail.html", current_client_user,
        entity=subject.entity, subject=subject,
        news_articles=news_articles, youtube_mentions=youtube_mentions, x_mentions=x_mentions,
    )
