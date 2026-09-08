"""Phase 4, Sections 8-9: the public-facing site. Same architecture as
Phase 3's admin UI - server-rendered Jinja2 in this one FastAPI app, no
separate frontend build (Section 8: "website is a client of the API, not a
place where business logic lives" - the actual read logic lives in
app/public/queries.py, this module is just the HTTP layer over it).

No auth here at all: everything this router shows is, by construction
(see app/public/queries.py's module docstring), already safe for anyone to
see.
"""

from datetime import date as date_cls

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.public.formatting import format_date_long, recent_date_options
from app.public.queries import get_cluster_comparison, get_home_columns, list_available_states, today_ist

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    date: str | None = Query(
        default=None,
        description="YYYY-MM-DD, IST calendar day - defaults to today. A future date redirects to today.",
    ),
    limit: int = Query(default=15, le=50, description="Max story clusters shown per column"),
    state: str | None = Query(
        default=None, description="Content-derived state to filter to - good-to-have, per direct instruction"
    ),
    db: Session = Depends(get_db),
):
    today = today_ist()

    selected_date = today
    if date is not None:
        try:
            selected_date = date_cls.fromisoformat(date)
        except ValueError:
            # Malformed input (hand-edited URL, bad bookmark) - fall back
            # to today rather than a 400 over what's purely a cosmetic
            # query param.
            selected_date = today
        if selected_date > today:
            # Never show (or let the date picker imply) a future date -
            # nothing published there could ever be legitimate.
            return RedirectResponse(f"/?date={today.isoformat()}", status_code=303)

    date_options = recent_date_options(today)
    if selected_date.isoformat() not in {iso for iso, _ in date_options}:
        # A direct/shared link older than the dropdown's own lookback
        # window - still a perfectly valid view (get_home_columns below
        # doesn't care), so represent it honestly in the <select> instead
        # of letting the browser silently fall back to showing "Today" as
        # selected while the page itself is showing an older date.
        date_options = [(selected_date.isoformat(), format_date_long(selected_date)), *date_options]

    state_options = list_available_states(db)
    selected_state = state if state in state_options else None

    columns = get_home_columns(db, limit_per_column=limit, day=selected_date, state=selected_state)
    return templates.TemplateResponse(
        request,
        "public_home.html",
        {
            "columns": columns,
            "selected_date": selected_date,
            "selected_date_display": format_date_long(selected_date),
            "date_options": date_options,
            "is_today": selected_date == today,
            "state_options": state_options,
            "selected_state": selected_state,
        },
    )


@router.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request, "public_about.html", {})


@router.get("/compare/{cluster_id}")
def compare(cluster_id: int, request: Request, db: Session = Depends(get_db)):
    comparison = get_cluster_comparison(db, cluster_id)
    if comparison is None:
        # Doesn't exist, or nothing published for it yet (e.g. a stale/
        # guessed URL) - same "just go home" behavior as the admin UI uses
        # for a missing/inaccessible resource, rather than a bare 404.
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "public_compare.html", {"comparison": comparison})
