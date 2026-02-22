from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.auth.passwords import hash_password, verify_password
from app.auth.refresh_tokens import generate_refresh_token, hash_refresh_token
from app.auth.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenPairResponse,
    RefreshResponse,
    UserPublic,
)
from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.core.config import get_settings
from app.auth.model import User, RefreshToken  # chỉnh import path theo project mày
from app.common.enums import UserStatus
from app.auth.jwt import create_access_token  # file jwt mày đưa


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AuthService:
    def register(
        self, *, session: Session, payload: RegisterRequest
    ) -> RegisterResponse:
        # email unique check
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise AppError.conflict(
                ErrorCode.USER_EMAIL_EXISTS, "Email already exists", field="email"
            )

        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            name=payload.name,
            status=UserStatus.active,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        return RegisterResponse(user=UserPublic.model_validate(user))

    def login(self, *, session: Session, payload: LoginRequest) -> TokenPairResponse:
        settings = get_settings()

        user = session.exec(select(User).where(User.email == payload.email)).first()
        # production-like: không leak user tồn tại hay không
        if not user or not verify_password(payload.password, user.hashed_password):
            raise AppError(
                401, ErrorCode.AUTH_INVALID_CREDENTIALS, "Invalid credentials"
            )

        if user.status != UserStatus.active:
            raise AppError.unauthorized("User is inactive")

        access = create_access_token(
            subject=str(user.id),
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            expires_minutes=settings.jwt_access_token_expire_minutes,
        )

        raw_refresh = generate_refresh_token()
        refresh_hash = hash_refresh_token(raw_refresh)
        expires_at = _now_utc() + timedelta(days=settings.jwt_refresh_token_expire_days)

        rt = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            revoked_at=None,
        )

        session.add(rt)
        session.commit()

        return TokenPairResponse(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=UserPublic.model_validate(user),
        )

    def refresh(self, *, session: Session, refresh_token: str) -> RefreshResponse:
        settings = get_settings()
        now = _now_utc()

        token_hash = hash_refresh_token(refresh_token)
        rt = session.exec(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).first()

        if not rt:
            raise AppError(401, ErrorCode.AUTH_REFRESH_INVALID, "Invalid refresh token")

        if rt.revoked_at is not None:
            raise AppError(401, ErrorCode.AUTH_REFRESH_REVOKED, "Refresh token revoked")

        if rt.expires_at <= now:
            raise AppError(401, ErrorCode.AUTH_REFRESH_EXPIRED, "Refresh token expired")

        user = session.get(User, rt.user_id)
        if not user:
            raise AppError.unauthorized("Invalid session")

        if user.status != UserStatus.active:
            raise AppError.unauthorized("User is inactive")

        # ROTATE:
        # 1) revoke old token
        rt.revoked_at = now
        session.add(rt)

        # 2) create new refresh token row
        new_raw = generate_refresh_token()
        new_hash = hash_refresh_token(new_raw)
        new_expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)

        new_rt = RefreshToken(
            user_id=rt.user_id,
            token_hash=new_hash,
            expires_at=new_expires_at,
            revoked_at=None,
        )
        session.add(new_rt)

        # 3) issue new access token
        access = create_access_token(
            subject=str(user.id),
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            expires_minutes=settings.jwt_access_token_expire_minutes,
        )

        session.commit()

        return RefreshResponse(
            access_token=access,
            refresh_token=new_raw,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    def logout(self, *, session: Session, refresh_token: str) -> None:
        # Idempotent logout: token không tồn tại cũng coi như ok
        token_hash = hash_refresh_token(refresh_token)
        rt = session.exec(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).first()
        if not rt:
            return

        if rt.revoked_at is None:
            rt.revoked_at = _now_utc()
            session.add(rt)
            session.commit()