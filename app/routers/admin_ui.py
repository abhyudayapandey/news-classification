"""Phase 3 admin/super-admin review UI - server-rendered Jinja2 pages in
the same FastAPI app, no separate frontend build. Internal tool for 2-3
known users, so this trades some things a public-facing app would need
(CSRF tokens, rate limiting on login) for simplicity - see README's Phase 3
section for what's deliberately not built and why that's an acceptable
POC-scale tradeoff, not an oversight.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.security import hash_password, verify_password
from app.auth.session import get_current_admin, get_current_admin_optional, require_super_admin
from app.config import settings
from app.db import get_db
from app.models import Admin, Article, ArticleEntity, Client, ClientSubject, ClientUser, Entity, EntitySocialConfig, Review
from app.models.enums import AdminRole, ClassificationTag, EntityProminence, ReviewDecision, SubjectSentiment
from app.public.formatting import excerpt as make_excerpt
from app.public.formatting import format_jurisdiction
from app.review.assignment import reassign_admin_queue
from app.review.blinding import blind_headline_and_body
from app.review.queries import ReviewFilters, query_reviews
from app.social.costs import (
    grant_x_access,
    list_client_cost_statuses,
    list_entity_spend_summaries,
    revoke_x_access,
    status_for,
)

router = APIRouter(prefix="/admin", tags=["admin-ui"])
templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template: str, current_admin: Admin | None, status_code: int = 200, **context):
    return templates.TemplateResponse(
        request, template, {"current_admin": current_admin, **context}, status_code=status_code
    )


# --- Auth ---


@router.get("/")
def admin_root(current_admin: Admin | None = Depends(get_current_admin_optional)):
    return RedirectResponse("/admin/queue" if current_admin else "/admin/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, current_admin: Admin | None = Depends(get_current_admin_optional)):
    if current_admin:
        return RedirectResponse("/admin/queue", status_code=303)
    return render(request, "login.html", None)


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = db.query(Admin).filter(Admin.username == username).one_or_none()
    if admin is None or not admin.is_active or not verify_password(password, admin.password_hash):
        return render(request, "login.html", None, status_code=401, error="Invalid username or password.")
    request.session["admin_id"] = admin.id
    return RedirectResponse("/admin/queue", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


# --- Admin queue + review ---


def _blind_article(article: Article) -> tuple[str, str, str]:
    """Prefers the scraped full text (app/review/scraping.py) over the RSS
    teaser in body_text - both go through the same redaction either way.
    Returns (blinded_headline, blinded_body, body_source) where
    body_source is "scraped" or "rss" so the template can label which one
    the admin is actually looking at.
    """
    if article.scraped_body_text:
        body_source = "scraped"
        source_body = article.scraped_body_text
    else:
        body_source = "rss"
        source_body = article.body_text
    blinded_headline, blinded_body = blind_headline_and_body(article.headline, source_body, article.outlet.name)
    return blinded_headline, blinded_body, body_source


def _record_review(db: Session, article: Article, admin: Admin, final_tag: str) -> None:
    """Shared by both the normal (blinded) review flow and the Manual
    Review flow - decision/published_tag logic doesn't depend on how the
    admin got to read the article.
    """
    decision = (
        ReviewDecision.AGREED_WITH_SYSTEM
        if final_tag == article.system_tag.classification.value
        else ReviewDecision.OVERRODE
    )
    db.add(Review(article_id=article.id, admin_id=admin.id, final_tag=final_tag, decision=decision))
    article.published_tag = final_tag
    db.commit()


_ENTITY_SENTIMENT_FIELD_PREFIX = "entity_sentiment_"
_VALID_SENTIMENT_VALUES = {s.value for s in SubjectSentiment}
_PROMINENCE_SORT_ORDER = {EntityProminence.PRIMARY: 0, EntityProminence.SECONDARY: 1, EntityProminence.MENTIONED: 2}


def _sorted_entity_mentions(article: Article) -> list:
    """Most-central entities first, so an admin scanning a many-entity
    article (see the review.html card's own note on this) at least sees
    the entities most likely to matter before the incidental ones."""
    return sorted(
        article.entity_mentions,
        key=lambda ae: (_PROMINENCE_SORT_ORDER[ae.prominence], -ae.mention_count),
    )


def _record_entity_sentiment_reviews(db: Session, article: Article, admin: Admin, submitted_by_entity_id: dict[int, str]) -> None:
    """Section 13.2: folded into the SAME admin action that reviews the
    article's establishment tag (submit_review / submit_manual_review),
    per direct instruction - one submit records both axes, no second
    queue. An entity missing from `submitted_by_entity_id` (the bulk-
    confirm path never renders the full form at all) defaults to agreeing
    with its system sentiment - the same "didn't open it, agreeing with
    everything system-generated" semantics bulk-confirm already uses for
    the establishment tag.
    """
    now = datetime.now(timezone.utc)
    for ae in article.entity_mentions:
        submitted = submitted_by_entity_id.get(ae.entity_id, ae.system_subject_sentiment.value)
        if submitted not in _VALID_SENTIMENT_VALUES:
            submitted = ae.system_subject_sentiment.value
        ae.published_subject_sentiment = submitted
        ae.subject_sentiment_decision = (
            ReviewDecision.AGREED_WITH_SYSTEM
            if submitted == ae.system_subject_sentiment.value
            else ReviewDecision.OVERRODE
        )
        ae.subject_sentiment_reviewed_by_id = admin.id
        ae.subject_sentiment_reviewed_at = now
    db.commit()


def _queue_item(article: Article) -> dict:
    """Includes the same blinded headline/excerpt an admin would see on the
    full review page - requested directly so an admin can tell at a glance,
    right from the queue list, whether an article is an obvious case (agree
    with the system tag, select it, bulk-publish) without opening each one.
    The excerpt is the same length/truncation as the public site's card
    teaser (app/public/formatting.excerpt) since it's meant to give the
    admin the same "headline + hero text" a reader would eventually see.

    Also carries jurisdiction/ruling_party, formatted the same way review.html
    already shows them - requested directly: the same headline can be pro for
    one party/jurisdiction and anti for another, so an admin judging an
    "obvious" case straight from the queue list (the whole point of the
    excerpt above) needs that context in the table itself, not just after
    opening the full review page.
    """
    hours_elapsed = (datetime.now(timezone.utc) - article.queued_at).total_seconds() / 3600
    overdue = hours_elapsed > settings.review_sla_hours
    blinded_headline, blinded_body, _ = _blind_article(article)
    return {
        "article": article,
        "headline": blinded_headline,
        "excerpt": make_excerpt(blinded_body) if blinded_body.strip() else None,
        "jurisdiction": format_jurisdiction(article.system_tag.jurisdiction) or "-",
        "ruling_party": article.system_tag.ruling_party or "unresolved",
        "overdue": overdue,
        "hours_remaining": max(0, round(settings.review_sla_hours - hours_elapsed)),
    }


def _build_client_queue_groups(db: Session, articles: list[Article]) -> list[dict]:
    """Section 13.6's own "Operational note": admins need visibility into
    which pending articles relate to a paying client's tracked subject, so
    review priority isn't dependent on a side conversation. This is a
    priority LENS over the same one queue `my_queue` already builds, not a
    second parallel queue - the same article still needs the same single
    review action either way, whichever tab it was found through.

    An article mentioning entities tracked by more than one client (or
    several subjects for the same client) appears under every relevant
    one, not just the first match - a client whose tracked subject is
    genuinely mentioned should never be missing it just because some
    other client also tracks a co-mentioned entity.
    """
    all_entity_ids = {ae.entity_id for article in articles for ae in article.entity_mentions}
    if not all_entity_ids:
        return []

    # entity_id -> [(client_id, client_name), ...] - only active clients,
    # same "an offboarded client's grant doesn't keep mattering" posture
    # already applied to X-fetch gating (app/social/pipeline.py).
    entity_to_clients: dict[int, list[tuple[int, str]]] = {}
    rows = (
        db.query(ClientSubject.entity_id, Client.id, Client.name)
        .join(Client, Client.id == ClientSubject.client_id)
        .filter(ClientSubject.entity_id.in_(all_entity_ids), Client.active.is_(True))
        .all()
    )
    for entity_id, client_id, client_name in rows:
        entity_to_clients.setdefault(entity_id, []).append((client_id, client_name))
    if not entity_to_clients:
        return []

    # client_id -> {name, article_ids (for the count, deduped), subjects: {entity_id: {entity_name, articles}}}
    by_client: dict[int, dict] = {}
    for article in articles:
        for ae in article.entity_mentions:
            for client_id, client_name in entity_to_clients.get(ae.entity_id, []):
                bucket = by_client.setdefault(client_id, {"name": client_name, "article_ids": set(), "subjects": {}})
                bucket["article_ids"].add(article.id)
                subject = bucket["subjects"].setdefault(ae.entity_id, {"entity_name": ae.entity.name, "articles": []})
                subject["articles"].append(article)

    groups = []
    for client_id, data in sorted(by_client.items(), key=lambda kv: kv[1]["name"]):
        subjects = [
            # "queue_items", not "items" - a plain dict's own .items()
            # method shadows a same-named key when accessed via Jinja's
            # dot notation, silently returning the bound method instead
            # of the list (caught while testing: `len(s.items)` blew up
            # with "builtin_function_or_method has no len()").
            {"entity_id": eid, "entity_name": s["entity_name"], "queue_items": [_queue_item(a) for a in s["articles"]]}
            for eid, s in sorted(data["subjects"].items(), key=lambda kv: kv[1]["entity_name"])
        ]
        groups.append({
            "client_id": client_id, "client_name": data["name"],
            "count": len(data["article_ids"]), "subjects": subjects,
        })
    return groups


@router.get("/queue", response_class=HTMLResponse)
def my_queue(
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Grouped into the three system-tag categories rather than one flat
    list - requested directly (Phase 4): a single long undifferentiated
    list read as more daunting to an admin than three shorter, categorized
    ones, even though the total review volume is identical either way.
    Order within each category is newest published_at first - a Phase 4
    departure from Section 5's original oldest-first wording, requested
    directly: publishing the most recent articles first keeps their
    context current and matches what an end user sees first on the public
    site (also newest-first), whereas the review/publish order was never
    itself the thing Section 5's SLA cares about (that's queued_at, not
    published_at - see Article.queued_at's field comment). Apolitical
    articles reach here too now - see app/review/assignment.py's module
    docstring for why.

    The three categories render as tabs, not three stacked full-length
    lists - stacking them still forced exactly the scrolling-through-a-
    long-list problem the categorization itself was meant to solve, just
    spread across three lists instead of one. Only one tab's articles are
    in the DOM as visible at a time; the other two are still rendered
    (so switching tabs is instant, no extra request) but hidden.
    """
    stmt = (
        select(Article)
        .where(Article.assigned_admin_id == current_admin.id, ~Article.reviews.any())
        .order_by(Article.published_at.desc())
        # Eager-load what _queue_item()/_blind_article() touch per article
        # (system_tag.classification, outlet.name) - both default to
        # lazy="select", so without this a queue of N articles fires ~2N
        # extra round-trips (one per article per relationship) instead of
        # this one extra batched query each. Invisible on an empty/small
        # test database (never caught in local testing), real once the
        # queue has actual accumulated volume, especially over a network
        # connection to a remote DB.
        .options(
            selectinload(Article.system_tag), selectinload(Article.outlet),
            selectinload(Article.entity_mentions).selectinload(ArticleEntity.entity),
        )
    )
    articles = list(db.scalars(stmt))
    items_by_tag: dict[ClassificationTag, list[dict]] = {tag: [] for tag in ClassificationTag}
    for article in articles:
        items_by_tag[article.system_tag.classification].append(_queue_item(article))

    pro_items = items_by_tag[ClassificationTag.PRO_ESTABLISHMENT]
    anti_items = items_by_tag[ClassificationTag.ANTI_ESTABLISHMENT]
    apolitical_items = items_by_tag[ClassificationTag.APOLITICAL]
    # Default to the first category that actually has something to review,
    # so an admin with (say) only apolitical articles pending doesn't land
    # on an empty Pro-Establishment tab.
    if pro_items:
        active_tab = "pro"
    elif anti_items:
        active_tab = "anti"
    else:
        active_tab = "apolitical"

    client_groups = _build_client_queue_groups(db, articles)

    return render(
        request, "queue.html", current_admin,
        pro_items=pro_items,
        anti_items=anti_items,
        apolitical_items=apolitical_items,
        active_tab=active_tab,
        total=len(articles),
        client_groups=client_groups,
    )


@router.get("/review/{article_id}", response_class=HTMLResponse)
def review_article(
    article_id: int,
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if (
        article is None
        or article.assigned_admin_id != current_admin.id
        or article.reviews
        or article.system_tag is None
    ):
        # Not this admin's to review (wrong owner, already done, or doesn't
        # exist) - same redirect-to-queue behavior as the POST handler
        # below, rather than a bare 404.
        return RedirectResponse("/admin/queue", status_code=303)

    blinded_headline, blinded_body, body_source = _blind_article(article)
    hours_elapsed = (datetime.now(timezone.utc) - article.queued_at).total_seconds() / 3600
    return render(
        request, "review.html", current_admin,
        article=article,
        blinded_headline=blinded_headline,
        blinded_body=blinded_body,
        body_source=body_source,
        system_tag=article.system_tag,
        entity_mentions=_sorted_entity_mentions(article),
        overdue=hours_elapsed > settings.review_sla_hours,
    )


@router.post("/review/{article_id}")
async def submit_review(
    article_id: int,
    request: Request,
    final_tag: str = Form(...),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if article is None or article.assigned_admin_id != current_admin.id or article.reviews or article.system_tag is None:
        return RedirectResponse("/admin/queue", status_code=303)

    if final_tag not in (
        ClassificationTag.PRO_ESTABLISHMENT.value,
        ClassificationTag.ANTI_ESTABLISHMENT.value,
        ClassificationTag.APOLITICAL.value,
    ):
        blinded_headline, blinded_body, body_source = _blind_article(article)
        return render(
            request, "review.html", current_admin, status_code=400,
            article=article, blinded_headline=blinded_headline, blinded_body=blinded_body,
            body_source=body_source, system_tag=article.system_tag,
            entity_mentions=_sorted_entity_mentions(article), overdue=False,
            error="Choose one of the tags.",
        )

    # Entity sentiment radios use a dynamic field name per entity
    # (entity_sentiment_<id>) since an article can carry any number of
    # them - read via the raw form rather than a fixed set of Form(...)
    # params, which can't express a per-article-variable field set.
    form = await request.form()
    submitted_by_entity_id = {
        int(key[len(_ENTITY_SENTIMENT_FIELD_PREFIX):]): value
        for key, value in form.items()
        if key.startswith(_ENTITY_SENTIMENT_FIELD_PREFIX)
    }

    _record_review(db, article, current_admin, final_tag)
    _record_entity_sentiment_reviews(db, article, current_admin, submitted_by_entity_id)
    return RedirectResponse("/admin/queue", status_code=303)


@router.post("/queue/bulk-confirm")
def bulk_confirm(
    article_ids: list[int] = Form(default=[]),
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """The checkbox+"Publish selected" flow on /admin/queue: for obvious
    cases an admin can already judge from the queue list's headline+excerpt
    alone, this skips opening each article individually. Always agrees with
    the system tag already shown for that row - there's no per-article tag
    picker here, so this can only confirm, never override (an override
    still goes through the full single-article review page). Silently
    ignores any id that isn't actually this admin's to review (wrong owner,
    already reviewed, stale page) rather than erroring the whole batch.
    """
    if article_ids:
        stmt = select(Article).where(
            Article.id.in_(article_ids),
            Article.assigned_admin_id == current_admin.id,
            ~Article.reviews.any(),
        )
        for article in db.scalars(stmt):
            if article.system_tag is not None:
                _record_review(db, article, current_admin, article.system_tag.classification.value)
                # No form was ever opened for this article, so there's
                # nothing "submitted" for any of its entities either -
                # an empty dict makes _record_entity_sentiment_reviews
                # agree with the system sentiment for every one of them,
                # consistent with what bulk-confirming already means for
                # the establishment tag above.
                _record_entity_sentiment_reviews(db, article, current_admin, {})
    return RedirectResponse("/admin/queue", status_code=303)


# --- Super admin: Manual Review bucket (Article.needs_manual_link_review) ---
#
# Articles with no usable text at all - scrape failed/rejected AND the RSS
# teaser is also empty (app/review/assignment.py's _needs_manual_review) -
# never reach a regular admin's blinded queue, since there'd be nothing to
# show them. They land here instead: super-admin only, showing the raw
# source URL (blinding is a regular-admin protection, not applicable when
# a human has to visit the link directly to read and classify it).


@router.get("/manual-review", response_class=HTMLResponse)
def manual_review_list(
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Article)
        .where(Article.needs_manual_link_review.is_(True), ~Article.reviews.any())
        .order_by(Article.published_at.asc())
    )
    articles = list(db.scalars(stmt))
    return render(request, "manual_review_list.html", current_admin, articles=articles)


@router.get("/manual-review/{article_id}", response_class=HTMLResponse)
def manual_review_article(
    article_id: int,
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if article is None or not article.needs_manual_link_review or article.reviews or article.system_tag is None:
        return RedirectResponse("/admin/manual-review", status_code=303)
    return render(
        request, "manual_review_detail.html", current_admin, article=article, system_tag=article.system_tag,
        entity_mentions=_sorted_entity_mentions(article),
    )


@router.post("/manual-review/{article_id}")
async def submit_manual_review(
    article_id: int,
    request: Request,
    final_tag: str = Form(...),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if article is None or not article.needs_manual_link_review or article.reviews or article.system_tag is None:
        return RedirectResponse("/admin/manual-review", status_code=303)

    if final_tag not in (
        ClassificationTag.PRO_ESTABLISHMENT.value,
        ClassificationTag.ANTI_ESTABLISHMENT.value,
        ClassificationTag.APOLITICAL.value,
    ):
        return render(
            request, "manual_review_detail.html", current_admin, status_code=400,
            article=article, system_tag=article.system_tag,
            entity_mentions=_sorted_entity_mentions(article), error="Choose one of the tags.",
        )

    form = await request.form()
    submitted_by_entity_id = {
        int(key[len(_ENTITY_SENTIMENT_FIELD_PREFIX):]): value
        for key, value in form.items()
        if key.startswith(_ENTITY_SENTIMENT_FIELD_PREFIX)
    }

    _record_review(db, article, current_admin, final_tag)
    _record_entity_sentiment_reviews(db, article, current_admin, submitted_by_entity_id)
    return RedirectResponse("/admin/manual-review", status_code=303)


# --- Super admin: admin account CRUD ---


@router.get("/admins", response_class=HTMLResponse)
def list_admins(
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    admins = db.query(Admin).order_by(Admin.created_at.asc()).all()
    return render(request, "admins_list.html", current_admin, admins=admins, message=message, error=error)


@router.get("/admins/new", response_class=HTMLResponse)
def new_admin_form(request: Request, current_admin: Admin = Depends(require_super_admin)):
    return render(request, "admin_form.html", current_admin, admin=None)


@router.post("/admins/new")
def create_admin(
    request: Request,
    username: str = Form(...),
    name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    if db.query(Admin).filter(Admin.username == username).one_or_none() is not None:
        return render(request, "admin_form.html", current_admin, status_code=400, admin=None, error="Username already taken.")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        return render(request, "admin_form.html", current_admin, status_code=400, admin=None, error=str(exc))

    db.add(Admin(username=username, name=name, role=AdminRole(role), password_hash=password_hash))
    db.commit()
    return RedirectResponse(f"/admin/admins?message=Created {username}.", status_code=303)


@router.get("/admins/{admin_id}/edit", response_class=HTMLResponse)
def edit_admin_form(
    admin_id: int, request: Request, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    target = db.get(Admin, admin_id)
    if target is None:
        return RedirectResponse("/admin/admins", status_code=303)
    return render(request, "admin_form.html", current_admin, admin=target)


@router.post("/admins/{admin_id}/edit")
def edit_admin(
    admin_id: int,
    request: Request,
    name: str = Form(...),
    role: str = Form(...),
    is_active: str | None = Form(default=None),
    password: str = Form(default=""),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(Admin, admin_id)
    if target is None:
        return RedirectResponse("/admin/admins", status_code=303)

    was_active = target.is_active
    new_is_active = is_active == "1"
    new_role = AdminRole(role)

    if target.id == current_admin.id and not new_is_active:
        return render(request, "admin_form.html", current_admin, status_code=400, admin=target, error="You can't deactivate your own account.")

    # Losing super-admin status isn't just deactivation - demoting the role
    # to "admin" while leaving is_active checked loses it just as
    # thoroughly, and would otherwise slip past a check that only looked
    # at is_active.
    losing_super_admin_status = target.role == AdminRole.SUPER_ADMIN and (new_role != AdminRole.SUPER_ADMIN or not new_is_active)
    if losing_super_admin_status:
        remaining = db.query(Admin).filter(Admin.role == AdminRole.SUPER_ADMIN, Admin.is_active.is_(True), Admin.id != target.id).count()
        if remaining == 0:
            return render(request, "admin_form.html", current_admin, status_code=400, admin=target, error="This would leave zero active super admins - promote another account first.")

    target.name = name
    target.role = new_role
    target.is_active = new_is_active
    if password:
        try:
            target.password_hash = hash_password(password)
        except ValueError as exc:
            return render(request, "admin_form.html", current_admin, status_code=400, admin=target, error=str(exc))
    db.commit()

    if was_active and not new_is_active:
        reassign_admin_queue(db, target.id)

    return RedirectResponse(f"/admin/admins?message=Updated {target.username}.", status_code=303)


@router.post("/admins/{admin_id}/deactivate")
def deactivate_admin(
    admin_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    target = db.get(Admin, admin_id)
    if target is None:
        return RedirectResponse("/admin/admins", status_code=303)
    if target.id == current_admin.id:
        return RedirectResponse("/admin/admins?error=You can't deactivate your own account.", status_code=303)
    if target.role == AdminRole.SUPER_ADMIN:
        remaining = db.query(Admin).filter(Admin.role == AdminRole.SUPER_ADMIN, Admin.is_active.is_(True), Admin.id != target.id).count()
        if remaining == 0:
            return RedirectResponse("/admin/admins?error=Can't deactivate the last active super admin.", status_code=303)

    target.is_active = False
    db.commit()
    moved = reassign_admin_queue(db, target.id)
    return RedirectResponse(f"/admin/admins?message=Deactivated {target.username}, reassigned {moved} pending article(s).", status_code=303)


# --- Super admin: oversight ---


@router.get("/articles/{article_id}/compare", response_class=HTMLResponse)
def compare_article(
    article_id: int, request: Request, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    article = db.get(Article, article_id)
    if article is None or article.system_tag is None:
        return RedirectResponse("/admin/reviews", status_code=303)
    review = article.reviews[-1] if article.reviews else None
    return render(request, "article_compare.html", current_admin, article=article, system_tag=article.system_tag, review=review)


@router.get("/reviews", response_class=HTMLResponse)
def list_reviews(
    request: Request,
    admin_id: int | None = Query(default=None),
    decision: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    limit: int = Query(default=25, le=200),
    offset: int = Query(default=0, ge=0),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    filters = ReviewFilters(
        admin_id=admin_id,
        decision=ReviewDecision(decision) if decision else None,
        date_from=datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc) if date_from else None,
        date_to=(datetime.fromisoformat(date_to) + timedelta(days=1)).replace(tzinfo=timezone.utc) if date_to else None,
    )
    reviews, total = query_reviews(db, filters, limit=limit, offset=offset)
    all_admins = db.query(Admin).order_by(Admin.name.asc()).all()

    query_parts = []
    if admin_id:
        query_parts.append(f"admin_id={admin_id}")
    if decision:
        query_parts.append(f"decision={decision}")
    if date_from:
        query_parts.append(f"date_from={date_from}")
    if date_to:
        query_parts.append(f"date_to={date_to}")

    return render(
        request, "reviews_list.html", current_admin,
        reviews=reviews, total=total, all_admins=all_admins,
        filters={"admin_id": admin_id, "decision": decision, "date_from": date_from, "date_to": date_to},
        limit=limit, offset=offset, query_string="&".join(query_parts),
    )


@router.get("/social-costs", response_class=HTMLResponse)
def social_costs(
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Section 13's cost visibility, deliberately gated behind
    require_super_admin rather than living as an open debug endpoint like
    /entities or /articles - this is business-confidential spend/contract
    data, "a screen that could never be the one shared on a client call"
    per direct instruction. Shows both halves of the shared-fetch/per-
    client-access split: real spend per entity (app/models/
    entity_social_config.py), and each client's own ceiling status against
    that same shared number (app/models/client_subject.py) - informational
    only, nothing here throttles anything.
    """
    return render(
        request, "social_costs.html", current_admin,
        entity_summaries=list_entity_spend_summaries(db),
        client_statuses=list_client_cost_statuses(db),
    )


# --- Super admin: B2B client CRUD (Section 13.6's actual portal) ---
#
# Everything below was previously CLI-only (create-client, add-client-
# subject, python -m app.cli social-cost-report) - this is the same
# underlying data (Client, ClientSubject, app.social.costs.grant_x_access/
# revoke_x_access) exposed as web forms once a real end-to-end walkthrough
# (create a client, grant/revoke X access, create their login, see their
# dashboard) was asked for, rather than CLI-only interaction.


@router.get("/clients", response_class=HTMLResponse)
def list_clients(
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """Nested per-subject view (each client's tracked entities as their own
    rows, YouTube/X toggles included right here) rather than one aggregate-
    count row per client - built once per-subject toggles existed, so a
    super admin can see and change access without a click-through to each
    client's own detail page for the common case.
    """
    clients = db.query(Client).order_by(Client.created_at.asc()).all()
    rows = []
    for c in clients:
        subject_rows = []
        for s in sorted(c.subjects, key=lambda s: s.entity.name):
            config = db.get(EntitySocialConfig, s.entity_id)
            current_spend = config.x_spend_usd if config is not None else Decimal("0")
            subject_rows.append({
                "entity": s.entity,
                "x_access": s.x_access,
                "youtube_access": s.youtube_access,
                "news_access": s.news_access,
                "x_spend_ceiling_usd": s.x_spend_ceiling_usd,
                "current_spend_usd": current_spend,
                "status": status_for(s.x_spend_ceiling_usd, current_spend, s.x_access),
            })
        rows.append({"client": c, "subject_rows": subject_rows, "user_count": len(c.users)})
    return render(request, "clients_list.html", current_admin, rows=rows, message=message, error=error)


@router.get("/clients/new", response_class=HTMLResponse)
def new_client_form(
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
    error: str | None = Query(default=None),
):
    entities = db.query(Entity).order_by(Entity.name.asc()).all()
    return render(request, "client_form.html", current_admin, entities=entities, error=error)


@router.post("/clients/new")
def create_client(
    name: str = Form(...),
    username: str = Form(default=""),
    contact_name: str = Form(default=""),
    password: str = Form(default=""),
    entity_id: str = Form(default=""),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Consolidated form, per direct instruction: the common case (a new
    client with its first login and first tracked subject) used to take
    three separate submissions across two pages - this does all three in
    one, while /admin/clients/{id}'s own incremental "add login"/"add
    tracked entity" forms stay in place for adding more later. Login and
    subject are both genuinely optional here (blank username = no login
    created yet, blank entity = no subject tracked yet) since a client can
    legitimately be created before either is known.
    """
    username = username.strip()
    contact_name = contact_name.strip()

    if username and (not contact_name or not password):
        return RedirectResponse(
            "/admin/clients/new?error=A login needs both a contact name and a password.", status_code=303
        )
    if username and db.query(ClientUser).filter(ClientUser.username == username).one_or_none() is not None:
        return RedirectResponse("/admin/clients/new?error=Username already taken.", status_code=303)
    if username:
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            return RedirectResponse(f"/admin/clients/new?error={exc}", status_code=303)

    client = Client(name=name, contract_start=date.today())
    db.add(client)
    db.flush()

    if username:
        db.add(ClientUser(client_id=client.id, username=username, name=contact_name, password_hash=password_hash))

    # Toggles all default False on the column itself - deliberately not
    # set here, so a subject added at creation time starts exactly as
    # invisible as one added later via /subjects/new, per the same
    # "nothing visible until payment" instruction that set those defaults.
    if entity_id.strip():
        db.add(ClientSubject(client_id=client.id, entity_id=int(entity_id)))

    db.commit()
    return RedirectResponse(f"/admin/clients/{client.id}?message=Created {name}.", status_code=303)


@router.post("/clients/{client_id}/deactivate")
def deactivate_client(client_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/admin/clients", status_code=303)
    # Deactivate, don't delete - same posture as Admin.is_active (Phase 3).
    # app/social/pipeline.py's live access check already excludes inactive
    # clients, so this alone stops any further X spend on their grants
    # without erasing what they used to have access to.
    client.active = False
    db.commit()
    return RedirectResponse(f"/admin/clients?message=Deactivated {client.name}.", status_code=303)


@router.post("/clients/{client_id}/reactivate")
def reactivate_client(client_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/admin/clients", status_code=303)
    client.active = True
    db.commit()
    return RedirectResponse(f"/admin/clients?message=Reactivated {client.name}.", status_code=303)


@router.get("/clients/{client_id}", response_class=HTMLResponse)
def client_detail(
    client_id: int,
    request: Request,
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
    message: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/admin/clients", status_code=303)

    subject_rows = []
    for s in sorted(client.subjects, key=lambda s: s.entity.name):
        config = db.get(EntitySocialConfig, s.entity_id)
        current_spend = config.x_spend_usd if config is not None else Decimal("0")
        subject_rows.append({
            "entity": s.entity,
            "x_access": s.x_access,
            "youtube_access": s.youtube_access,
            "news_access": s.news_access,
            "x_spend_ceiling_usd": s.x_spend_ceiling_usd,
            "current_spend_usd": current_spend,
            "status": status_for(s.x_spend_ceiling_usd, current_spend, s.x_access),
            "social_fetch_max_results": config.social_fetch_max_results if config is not None else None,
            "social_fetch_lookback_days": config.social_fetch_lookback_days if config is not None else None,
        })

    tracked_entity_ids = {s.entity_id for s in client.subjects}
    entities_query = db.query(Entity).order_by(Entity.name.asc())
    if tracked_entity_ids:
        entities_query = entities_query.filter(~Entity.id.in_(tracked_entity_ids))
    available_entities = entities_query.all()

    return render(
        request, "client_detail.html", current_admin,
        client=client, subject_rows=subject_rows, available_entities=available_entities,
        client_users=sorted(client.users, key=lambda u: u.created_at),
        message=message, error=error,
    )


@router.post("/clients/{client_id}/subjects/new")
def add_client_subject(
    client_id: int,
    entity_id: int = Form(...),
    grant_x: str | None = Form(default=None),
    x_ceiling: str = Form(default=""),
    grant_youtube: str | None = Form(default=None),
    grant_news: str | None = Form(default=None),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/admin/clients", status_code=303)

    if grant_x == "1":
        try:
            ceiling = Decimal(x_ceiling) if x_ceiling.strip() else None
        except InvalidOperation:
            ceiling = None
        if ceiling is None or ceiling <= 0:
            return RedirectResponse(
                f"/admin/clients/{client_id}?error=A positive monthly X ceiling is required to grant X access.",
                status_code=303,
            )
        subject = grant_x_access(db, client_id, entity_id, ceiling)
    else:
        # Track without X access - same as the CLI's add-client-subject
        # with no --x-ceiling: a real ClientSubject row exists (so the
        # entity shows up on the client's dashboard), just with x_access
        # left at its default False.
        subject = db.get(ClientSubject, (client_id, entity_id))
        if subject is None:
            subject = ClientSubject(client_id=client_id, entity_id=entity_id)
            db.add(subject)
            db.commit()

    # All three visibility toggles default to False on the column itself
    # (per direct instruction: nothing is visible on a client's dashboard
    # until a super admin turns it on, once payment is actually received) -
    # so these only need to act when the admin explicitly CHECKED the box
    # at creation time, the opposite of this form's old youtube-only logic.
    if grant_youtube == "1" and not subject.youtube_access:
        subject.youtube_access = True
        db.commit()
    if grant_news == "1" and not subject.news_access:
        subject.news_access = True
        db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Tracking updated.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/grant-x")
def grant_client_subject_x_access(
    client_id: int,
    entity_id: int,
    x_ceiling: str = Form(default=""),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Turning X on for an already-tracked subject - distinct from
    add_client_subject above (which only runs once, when the subject is
    first tracked). A toggle needs to work in both directions at any
    time, and turning X on always needs a ceiling (grant_x_access itself
    enforces that), so this is a real form submit, not a bare on/off
    flip.
    """
    try:
        ceiling = Decimal(x_ceiling) if x_ceiling.strip() else None
    except InvalidOperation:
        ceiling = None
    if ceiling is None or ceiling <= 0:
        return RedirectResponse(
            f"/admin/clients/{client_id}?error=A positive monthly X ceiling is required to grant X access.",
            status_code=303,
        )
    grant_x_access(db, client_id, entity_id, ceiling)
    return RedirectResponse(f"/admin/clients/{client_id}?message=X access granted.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/revoke")
def revoke_client_subject(
    client_id: int, entity_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    revoke_x_access(db, client_id, entity_id)
    return RedirectResponse(f"/admin/clients/{client_id}?message=X access revoked.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/youtube/enable")
def enable_client_subject_youtube(
    client_id: int, entity_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is not None:
        subject.youtube_access = True
        db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=YouTube visibility enabled.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/youtube/disable")
def disable_client_subject_youtube(
    client_id: int, entity_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    """Visibility-only, unlike X's revoke: YouTube keeps fetching for this
    entity regardless (free, shared, unconditional per Section 13) - this
    only stops it from rendering on this one client's dashboard.
    """
    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is not None:
        subject.youtube_access = False
        db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=YouTube visibility disabled.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/news/enable")
def enable_client_subject_news(
    client_id: int, entity_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is not None:
        subject.news_access = True
        db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=News visibility enabled.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/news/disable")
def disable_client_subject_news(
    client_id: int, entity_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    """Same visibility-only shape as YouTube's disable - the articles
    themselves stay published on the B2C site regardless, this only stops
    them rendering on this one client's dashboard.
    """
    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is not None:
        subject.news_access = False
        db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=News visibility disabled.", status_code=303)


@router.post("/clients/{client_id}/entities/{entity_id}/social-fetch-config")
def update_entity_social_fetch_config(
    client_id: int,
    entity_id: int,
    max_results: str = Form(default=""),
    lookback_days: str = Form(default=""),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Entity-level, not client-level - see EntitySocialConfig's docstring
    for why "how much to fetch" has to be one shared number regardless of
    how many clients track the same entity. Reached from a client's own
    detail page (the natural place a super admin is already looking at
    this entity), but changing it here affects every client tracking it.
    Blank input resets to "use the global default" (settings.
    social_fetch_max_results_per_entity / no lookback bound), not zero.
    """
    config = db.get(EntitySocialConfig, entity_id)
    if config is None:
        config = EntitySocialConfig(entity_id=entity_id)
        db.add(config)

    def _parse_positive_int(raw: str) -> int | None:
        try:
            value = int(raw.strip())
        except ValueError:
            return None
        return value if value > 0 else None

    config.social_fetch_max_results = _parse_positive_int(max_results)
    config.social_fetch_lookback_days = _parse_positive_int(lookback_days)
    db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Fetch settings updated.", status_code=303)


@router.post("/clients/{client_id}/subjects/{entity_id}/remove")
def remove_client_subject(
    client_id: int, entity_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    subject = db.get(ClientSubject, (client_id, entity_id))
    if subject is not None:
        db.delete(subject)
        db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Stopped tracking that entity.", status_code=303)


@router.post("/clients/{client_id}/users/new")
def create_client_user(
    client_id: int,
    username: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    client = db.get(Client, client_id)
    if client is None:
        return RedirectResponse("/admin/clients", status_code=303)
    if db.query(ClientUser).filter(ClientUser.username == username).one_or_none() is not None:
        return RedirectResponse(f"/admin/clients/{client_id}?error=Username already taken.", status_code=303)
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        return RedirectResponse(f"/admin/clients/{client_id}?error={exc}", status_code=303)

    db.add(ClientUser(client_id=client_id, username=username, name=name, password_hash=password_hash))
    db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Created login '{username}'.", status_code=303)


@router.post("/clients/{client_id}/users/{user_id}/deactivate")
def deactivate_client_user(
    client_id: int, user_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    user = db.get(ClientUser, user_id)
    if user is None or user.client_id != client_id:
        return RedirectResponse(f"/admin/clients/{client_id}", status_code=303)
    user.is_active = False
    db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Deactivated login '{user.username}'.", status_code=303)


@router.post("/clients/{client_id}/users/{user_id}/reactivate")
def reactivate_client_user(
    client_id: int, user_id: int, current_admin: Admin = Depends(require_super_admin), db: Session = Depends(get_db)
):
    user = db.get(ClientUser, user_id)
    if user is None or user.client_id != client_id:
        return RedirectResponse(f"/admin/clients/{client_id}", status_code=303)
    user.is_active = True
    db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Reactivated login '{user.username}'.", status_code=303)


@router.post("/clients/{client_id}/users/{user_id}/reset-password")
def reset_client_user_password(
    client_id: int,
    user_id: int,
    password: str = Form(...),
    current_admin: Admin = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """A super admin setting a new password directly - there's no forgot-
    password/email flow anywhere in this project (Phase 7's README section
    already flags this as out of scope), so this is the only way a client's
    login ever gets a new password, same as how Admin passwords are reset
    today (edit_admin's optional password field).
    """
    user = db.get(ClientUser, user_id)
    if user is None or user.client_id != client_id:
        return RedirectResponse(f"/admin/clients/{client_id}", status_code=303)
    try:
        user.password_hash = hash_password(password)
    except ValueError as exc:
        return RedirectResponse(f"/admin/clients/{client_id}?error={exc}", status_code=303)
    db.commit()
    return RedirectResponse(f"/admin/clients/{client_id}?message=Password reset for '{user.username}'.", status_code=303)
