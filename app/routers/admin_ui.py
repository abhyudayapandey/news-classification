"""Phase 3 admin/super-admin review UI - server-rendered Jinja2 pages in
the same FastAPI app, no separate frontend build. Internal tool for 2-3
known users, so this trades some things a public-facing app would need
(CSRF tokens, rate limiting on login) for simplicity - see README's Phase 3
section for what's deliberately not built and why that's an acceptable
POC-scale tradeoff, not an oversight.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.auth.session import get_current_admin, get_current_admin_optional, require_super_admin
from app.config import settings
from app.db import get_db
from app.models import Admin, Article, Review
from app.models.enums import AdminRole, ClassificationTag, ReviewDecision
from app.public.formatting import excerpt as make_excerpt
from app.review.assignment import reassign_admin_queue
from app.review.blinding import blind_headline_and_body
from app.review.queries import ReviewFilters, query_reviews

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


def _queue_item(article: Article) -> dict:
    """Includes the same blinded headline/excerpt an admin would see on the
    full review page - requested directly so an admin can tell at a glance,
    right from the queue list, whether an article is an obvious case (agree
    with the system tag, select it, bulk-publish) without opening each one.
    The excerpt is the same length/truncation as the public site's card
    teaser (app/public/formatting.excerpt) since it's meant to give the
    admin the same "headline + hero text" a reader would eventually see.
    """
    hours_elapsed = (datetime.now(timezone.utc) - article.queued_at).total_seconds() / 3600
    overdue = hours_elapsed > settings.review_sla_hours
    blinded_headline, blinded_body, _ = _blind_article(article)
    return {
        "article": article,
        "headline": blinded_headline,
        "excerpt": make_excerpt(blinded_body) if blinded_body.strip() else None,
        "overdue": overdue,
        "hours_remaining": max(0, round(settings.review_sla_hours - hours_elapsed)),
    }


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
    Order within each category is still oldest published_at first
    (Section 5). Apolitical articles reach here too now - see
    app/review/assignment.py's module docstring for why.
    """
    stmt = (
        select(Article)
        .where(Article.assigned_admin_id == current_admin.id, ~Article.reviews.any())
        .order_by(Article.published_at.asc())
    )
    articles = list(db.scalars(stmt))
    items_by_tag: dict[ClassificationTag, list[dict]] = {tag: [] for tag in ClassificationTag}
    for article in articles:
        items_by_tag[article.system_tag.classification].append(_queue_item(article))
    return render(
        request, "queue.html", current_admin,
        pro_items=items_by_tag[ClassificationTag.PRO_ESTABLISHMENT],
        anti_items=items_by_tag[ClassificationTag.ANTI_ESTABLISHMENT],
        apolitical_items=items_by_tag[ClassificationTag.APOLITICAL],
        total=len(articles),
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
        overdue=hours_elapsed > settings.review_sla_hours,
    )


@router.post("/review/{article_id}")
def submit_review(
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
            body_source=body_source, system_tag=article.system_tag, overdue=False,
            error="Choose one of the tags.",
        )

    _record_review(db, article, current_admin, final_tag)
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
        request, "manual_review_detail.html", current_admin, article=article, system_tag=article.system_tag
    )


@router.post("/manual-review/{article_id}")
def submit_manual_review(
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
            article=article, system_tag=article.system_tag, error="Choose one of the tags.",
        )

    _record_review(db, article, current_admin, final_tag)
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
