"""Session-based auth for the Phase 3 admin UI. Session state is just
{"admin_id": int}, stored in a signed cookie via Starlette's
SessionMiddleware (see app/main.py) - no server-side session store needed
at this scale, and nothing free-tier-unfriendly about it.

NotAuthenticated/Forbidden are exceptions rather than HTTPException(...)
directly because an HTML page wants a redirect to the login page on auth
failure, not a bare 401/403 - see the exception handlers registered in
app/main.py.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Admin
from app.models.enums import AdminRole


class NotAuthenticated(Exception):
    pass


class Forbidden(Exception):
    pass


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise NotAuthenticated()

    admin = db.get(Admin, admin_id)
    if admin is None or not admin.is_active:
        # Deactivated or deleted since the session was created - drop the
        # stale session rather than silently keep honoring it.
        request.session.clear()
        raise NotAuthenticated()

    return admin


def require_super_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    if admin.role != AdminRole.SUPER_ADMIN:
        raise Forbidden()
    return admin


def get_current_admin_optional(request: Request, db: Session = Depends(get_db)) -> Admin | None:
    """Non-raising variant for contexts that render regardless of login
    state (the base template's nav needs to know who's logged in, if
    anyone, without every route re-deriving that).
    """
    try:
        return get_current_admin(request, db)
    except NotAuthenticated:
        return None
