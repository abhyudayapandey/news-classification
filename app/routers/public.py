"""Phase 4, Sections 8-9: the public-facing site. Same architecture as
Phase 3's admin UI - server-rendered Jinja2 in this one FastAPI app, no
separate frontend build (Section 8: "website is a client of the API, not a
place where business logic lives" - the actual read logic lives in
app/public/queries.py, this module is just the HTTP layer over it).

No auth here at all: everything this router shows is, by construction
(see app/public/queries.py's module docstring), already safe for anyone to
see.
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.public.queries import get_home_columns

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    limit: int = Query(default=15, le=50, description="Max story clusters shown per column"),
    db: Session = Depends(get_db),
):
    columns = get_home_columns(db, limit_per_column=limit)
    return templates.TemplateResponse(request, "public_home.html", {"columns": columns})


@router.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request, "public_about.html", {})
