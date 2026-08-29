"""Manual data-seeding endpoints. HTTP counterpart to CLI commands that
need to run somewhere without shell access - notably Render's free tier,
which has no interactive shell. Same unauthenticated-debug-endpoint caveat
as the other routers here: not the Phase 3 admin API.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.data.jurisdiction_seed import seed_jurisdictions
from app.db import get_db

router = APIRouter(prefix="/admin-data", tags=["admin-data"])


@router.post("/seed-jurisdictions")
def trigger_seed_jurisdictions(db: Session = Depends(get_db)) -> dict:
    inserted, updated = seed_jurisdictions(db)
    return {
        "inserted": inserted,
        "updated": updated,
        "note": "See app/data/jurisdiction_seed.py's module docstring for what's confirmed vs. still needs verification.",
    }
