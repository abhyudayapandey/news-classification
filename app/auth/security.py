"""Password hashing for admin accounts. bcrypt: free, no external service,
well-vetted, and the resulting hash is self-contained (salt included), so
Admin.password_hash needs no separate salt column.
"""

import bcrypt

# bcrypt truncates silently past 72 bytes - reject upfront rather than let
# someone set a long password that only its first 72 bytes actually protect.
_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"Password too long ({_MAX_PASSWORD_BYTES}-byte limit)")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for rows we wrote ourselves) -
        # fail closed rather than raise past the login handler.
        return False
