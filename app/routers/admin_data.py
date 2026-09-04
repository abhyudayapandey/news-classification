"""Manual data-seeding endpoints. HTTP counterpart to CLI commands that
need to run somewhere without shell access - notably Render's free tier,
which has no interactive shell. Same unauthenticated-debug-endpoint caveat
as the other routers here: not the Phase 3 admin API.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.data.jurisdiction_seed import seed_jurisdictions
from app.db import get_db
from app.models import Admin
from app.models.enums import AdminRole

router = APIRouter(prefix="/admin-data", tags=["admin-data"])


@router.post("/seed-jurisdictions")
def trigger_seed_jurisdictions(db: Session = Depends(get_db)) -> dict:
    inserted, updated = seed_jurisdictions(db)
    return {
        "inserted": inserted,
        "updated": updated,
        "note": "See app/data/jurisdiction_seed.py's module docstring for what's confirmed vs. still needs verification.",
    }


class BootstrapSuperAdminRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


@router.post("/bootstrap-super-admin")
def bootstrap_super_admin(body: BootstrapSuperAdminRequest, db: Session = Depends(get_db)) -> dict:
    """Creates the first super-admin account. Only works when the `admins`
    table is empty - a chicken-and-egg fix for Render's free tier (no
    shell to run `python -m app.cli create-admin`), NOT a general-purpose
    account-creation endpoint. Once any admin exists, this always 403s;
    use the authenticated super-admin UI (/admin/admins) for every account
    after the first.
    """
    if db.query(Admin).count() > 0:
        raise HTTPException(
            status_code=403,
            detail="An admin account already exists - use the authenticated /admin/admins UI to create more.",
        )
    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    admin = Admin(username=body.username, name=body.name, password_hash=password_hash, role=AdminRole.SUPER_ADMIN)
    db.add(admin)
    db.commit()
    return {"created": body.username, "role": "super_admin"}
