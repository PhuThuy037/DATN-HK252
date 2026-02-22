from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.common.errors import AppError


def create_access_token(
    *,
    subject: str,
    secret_key: str,
    algorithm: str,
    expires_minutes: int = 60,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)

    payload = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(
    *,
    token: str,
    secret_key: str,
    algorithm: str,
) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise AppError.unauthorized("Token expired")
    except jwt.InvalidTokenError:
        raise AppError.unauthorized("Invalid token")

    if payload.get("type") != "access":
        raise AppError.unauthorized("Invalid token type")

    if "sub" not in payload:
        raise AppError.unauthorized("Token missing subject")

    return payload