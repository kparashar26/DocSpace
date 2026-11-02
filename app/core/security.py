
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import settings


# Password hashing using Argon2
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a user's password before storing it."""
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against its stored hash."""
    return password_hasher.verify(plain_password, hashed_password)


# In-memory token denylist for logout
_revoked_tokens: dict[str, datetime] = {}


def create_access_token(subject: str) -> str:
    """Create a signed JWT access token."""

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "exp": expires_at,
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token."""

    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        return None


def revoke_token(token_id: str, expires_at: int | float) -> None:
    """Add a token to the logout denylist."""

    _revoked_tokens[token_id] = datetime.fromtimestamp(
        expires_at,
        tz=timezone.utc,
    )


def is_token_revoked(token_id: str) -> bool:
    """Check whether a token has been revoked."""

    now = datetime.now(timezone.utc)

    # Remove expired entries from the denylist
    expired_tokens = [
        jti
        for jti, expiry in _revoked_tokens.items()
        if expiry <= now
    ]

    for jti in expired_tokens:
        del _revoked_tokens[jti]

    return token_id in _revoked_tokens
