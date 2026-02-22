from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.api.deps import SessionDep
from app.auth import service as auth_service
from app.auth.jwt import decode_access_token
from app.auth.model import User
from app.common.errors import AppError
from app.core.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(slots=True)
class Principal:
    user_id: UUID


def get_current_principal(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> Principal:
    token = creds.credentials
    payload = decode_access_token(
        token=token,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    sub = payload.get("sub")
    try:
        user_id = UUID(str(sub))
    except (TypeError, ValueError):
        raise AppError.unauthorized("Invalid token subject")

    return Principal(user_id=user_id)


def get_current_user(
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: SessionDep,
) -> User:
    cached: Optional[User] = getattr(request.state, "current_user", None)
    if cached is not None:
        return cached

    user = auth_service.get_user_by_id(session=session, user_id=principal.user_id)
    request.state.current_user = user
    return user


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
CurrentUser = Annotated[User, Depends(get_current_user)]