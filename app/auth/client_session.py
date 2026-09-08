"""Session-based auth for the client portal (Section 13.6), parallel to
app/auth/session.py's admin auth but a deliberately separate session key
("client_user_id" vs "admin_id") and a separate exception type. Two
reasons these aren't unified into one auth module: (1) a ClientUser and
an Admin are different account types with no shared identity - there's no
"log in once, be either" case to support - and (2) an auth failure needs
to redirect to a different login page (/client/login vs /admin/login),
which app/main.py's exception handlers key off the exception type.

Uses request.session.pop("client_user_id", None) rather than
request.session.clear() (which get_current_admin uses) on a stale/
deactivated session - clear() would also drop an unrelated admin_id if
the same browser session happened to carry both, which is unlikely in
practice but costs nothing to avoid.
"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ClientUser


class ClientNotAuthenticated(Exception):
    pass


def get_current_client_user(request: Request, db: Session = Depends(get_db)) -> ClientUser:
    client_user_id = request.session.get("client_user_id")
    if not client_user_id:
        raise ClientNotAuthenticated()

    client_user = db.get(ClientUser, client_user_id)
    if client_user is None or not client_user.is_active or not client_user.client.active:
        # Deactivated login, or the client itself was deactivated, since
        # the session was created - drop the stale session rather than
        # silently keep honoring it.
        request.session.pop("client_user_id", None)
        raise ClientNotAuthenticated()

    return client_user


def get_current_client_user_optional(request: Request, db: Session = Depends(get_db)) -> ClientUser | None:
    try:
        return get_current_client_user(request, db)
    except ClientNotAuthenticated:
        return None
