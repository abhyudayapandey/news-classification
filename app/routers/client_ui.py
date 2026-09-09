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

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.client_session import get_current_client_user, get_current_client_user_optional
from app.auth.security import verify_password
from app.db import get_db
from app.models import Article, ArticleEntity, ClientSubject, ClientUser, Entity, SocialMention
from app.models.enums import SocialSource, SubjectSentiment
from app.public.formatting import entity_initials, entity_subtitle, youtube_thumbnail_url
from app.public.formatting import excerpt as make_excerpt
from app.public.formatting import format_jurisdiction

router = APIRouter(prefix="/client", tags=["client-portal"])
templates = Jinja2Templates(directory="app/templates")

# Viewing-window options for the YouTube/X tabs (per direct instruction:
# "just the day's mentions are not enough"). Independent of how far BACK a
# fetch actually looked (EntitySocialConfig.social_fetch_lookback_days) -
# this only filters what's already stored, by posted_at, for display.
SOCIAL_RANGES = ("today", "yesterday", "3d", "7d")
_DEFAULT_SOCIAL_RANGE = "7d"


def _social_range_bounds(range_key: str) -> tuple[datetime, datetime | None]:
    """Returns (start, end) in UTC for a SOCIAL_RANGES key - end is None
    meaning "through now". "yesterday" is the only bounded-both-ends option
    (the single prior calendar day), everything else is an open-ended
    "since N days ago" window.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "today":
        return today_start, None
    if range_key == "yesterday":
        return today_start - timedelta(days=1), today_start
    if range_key == "3d":
        return today_start - timedelta(days=2), None
    return today_start - timedelta(days=6), None  # "7d", and the fallback default


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
        {
            "entity": s.entity,
            "subtitle": entity_subtitle(s.entity),
            "initials": entity_initials(s.entity.name),
            "x_access": s.x_access,
            "youtube_access": s.youtube_access,
            "news_access": s.news_access,
        }
        for s in subjects
    ]
    return render(request, "client_dashboard.html", current_client_user, subjects=rows)


def _geo_options_from(*item_lists) -> list[dict]:
    """Distinct (kind, value) geography tags actually present across the
    given items - state/district/constituency alike, each kept as its own
    option rather than merged, since a client might want to filter by
    exactly one of these axes. Per direct instruction ("whatever is
    available"): only ever offers what's actually tagged on content
    currently in view, never a fixed master list.
    """
    seen: dict[tuple[str, str], dict] = {}
    for items in item_lists:
        for item in items:
            state = item.get("state") if isinstance(item, dict) else item.state
            district = item.get("district") if isinstance(item, dict) else item.district
            constituency = item.get("constituency") if isinstance(item, dict) else item.constituency
            seat_type = item.get("seat_type") if isinstance(item, dict) else item.seat_type
            if state:
                seen[("state", state)] = {"key": f"state:{state}", "label": f"State: {state}"}
            if district:
                seen[("district", district)] = {"key": f"district:{district}", "label": f"District: {district}"}
            if constituency:
                seat_label = f" ({seat_type.value.upper()})" if seat_type else ""
                seen[("constituency", constituency)] = {
                    "key": f"constituency:{constituency}",
                    "label": f"Constituency: {constituency}{seat_label}",
                }
    return sorted(seen.values(), key=lambda o: o["label"])


def _matches_geo(item, geo_kind: str, geo_value: str) -> bool:
    value = item.get(geo_kind) if isinstance(item, dict) else getattr(item, geo_kind)
    return value == geo_value


def _split_by_sentiment(mentions: list[SocialMention]) -> tuple[list, list, list]:
    """Buckets social mentions into (favorable, neutral, unfavorable) for
    the YouTube/X tabs' sentiment columns - the same three-column pattern
    already used for articles' pro/anti/apolitical split above, applied to
    Section 13.2's subject-sentiment axis instead. A mention that predates
    sentiment scoring (SocialMention.sentiment is None - see
    app/social/backfill.py) falls into Neutral rather than disappearing
    from every column; in practice this is rare since backfill covers
    existing rows and every new mention is scored at storage time.
    """
    favorable, neutral, unfavorable = [], [], []
    for m in mentions:
        if m.sentiment == SubjectSentiment.FAVORABLE:
            favorable.append(m)
        elif m.sentiment == SubjectSentiment.UNFAVORABLE:
            unfavorable.append(m)
        else:
            neutral.append(m)
    return favorable, neutral, unfavorable


@router.get("/entities/{entity_id}", response_class=HTMLResponse)
def client_entity_detail(
    entity_id: int,
    request: Request,
    range_param: str = Query(default=_DEFAULT_SOCIAL_RANGE, alias="range"),
    geo: str | None = Query(default=None, description="'state:<name>' / 'district:<name>' / 'constituency:<name>'"),
    current_client_user: ClientUser = Depends(get_current_client_user),
    db: Session = Depends(get_db),
):
    subject = db.get(ClientSubject, (current_client_user.client_id, entity_id))
    if subject is None:
        # Not tracked by this client - redirect rather than 404, so this
        # never confirms or denies that the entity exists at all to a
        # client who isn't tracking it.
        return RedirectResponse("/client/dashboard", status_code=303)

    social_range = range_param if range_param in SOCIAL_RANGES else _DEFAULT_SOCIAL_RANGE
    range_start, range_end = _social_range_bounds(social_range)

    def _mentions_for(source: SocialSource) -> list[SocialMention]:
        # Most-engaged-first per direct instruction (the fetchers
        # themselves already return/store mentions in that order, but a
        # later re-fetch's new rows would otherwise appear out of order
        # against older ones without an explicit ORDER BY here). Ties
        # (typically 0-engagement rows) fall back to newest-first.
        q = db.query(SocialMention).filter(
            SocialMention.entity_id == entity_id, SocialMention.source == source,
            SocialMention.posted_at.is_not(None), SocialMention.posted_at >= range_start,
        )
        if range_end is not None:
            q = q.filter(SocialMention.posted_at < range_end)
        return q.order_by(SocialMention.engagement_count.desc(), SocialMention.posted_at.desc()).limit(25).all()

    youtube_mentions = _mentions_for(SocialSource.YOUTUBE) if subject.youtube_access else []
    x_mentions = _mentions_for(SocialSource.X) if subject.x_access else []

    # Same "published_tag-based data only" standard as the B2C public site
    # (Section 13.6) - an unreviewed article never appears here just
    # because it happens to mention this entity. Eager-loaded outlet/
    # system_tag to avoid the same N+1 pattern already fixed on the admin
    # queue (app/routers/admin_ui.py's my_queue). Gated by news_access,
    # same visibility-only pattern as youtube_access/x_access above - the
    # articles exist and are already public regardless, but this client's
    # News tab stays empty until a super admin turns it on for them.
    news_articles = []
    if subject.news_access:
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
                "state": a.system_tag.state if a.system_tag else None,
                "district": a.system_tag.district if a.system_tag else None,
                "constituency": a.system_tag.constituency if a.system_tag else None,
                "seat_type": a.system_tag.seat_type if a.system_tag else None,
                "excerpt": make_excerpt(a.body_text) if a.body_text.strip() else None,
            }
            for a in articles
        ]

    # Content-derived geography filter (app/processing/geography.py) -
    # applied across all three lists uniformly, after the range filter
    # above, and only ever offering options actually present in what's
    # currently in view (per direct instruction: "whatever is available").
    geo_options = _geo_options_from(news_articles, youtube_mentions, x_mentions)
    selected_geo = geo if geo in {o["key"] for o in geo_options} else None
    if selected_geo is not None:
        geo_kind, geo_value = selected_geo.split(":", 1)
        news_articles = [a for a in news_articles if _matches_geo(a, geo_kind, geo_value)]
        youtube_mentions = [m for m in youtube_mentions if _matches_geo(m, geo_kind, geo_value)]
        x_mentions = [m for m in x_mentions if _matches_geo(m, geo_kind, geo_value)]

    # Grouped into the same three framing columns the B2C public site uses
    # (Section 8-9) - per direct instruction, the client's own News tab
    # should look like what end users see, not one mixed list with an
    # inline tag badge per card. Newest-first within each column, same
    # order the query itself already returned.
    pro_articles = [a for a in news_articles if a["published_tag"] == "pro-establishment"]
    anti_articles = [a for a in news_articles if a["published_tag"] == "anti-establishment"]
    apolitical_articles = [a for a in news_articles if a["published_tag"] == "apolitical"]

    youtube_favorable, youtube_neutral, youtube_unfavorable = _split_by_sentiment(youtube_mentions)
    x_favorable, x_neutral, x_unfavorable = _split_by_sentiment(x_mentions)

    return render(
        request, "client_entity_detail.html", current_client_user,
        entity=subject.entity, subject=subject, subtitle=entity_subtitle(subject.entity),
        news_articles=news_articles, youtube_mentions=youtube_mentions, x_mentions=x_mentions,
        pro_articles=pro_articles, anti_articles=anti_articles, apolitical_articles=apolitical_articles,
        youtube_favorable=youtube_favorable, youtube_neutral=youtube_neutral, youtube_unfavorable=youtube_unfavorable,
        x_favorable=x_favorable, x_neutral=x_neutral, x_unfavorable=x_unfavorable,
        youtube_thumbnail_url=youtube_thumbnail_url,
        social_range=social_range, social_ranges=SOCIAL_RANGES,
        geo_options=geo_options, selected_geo=selected_geo,
    )
