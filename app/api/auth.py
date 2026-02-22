from __future__ import annotations

from fastapi import APIRouter, Request
from app.common.request_id import get_request_id
from app.auth.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenPairResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutRequest,
    MessageResponse,
)
from app.auth.service import AuthService
from app.common.schemas import ApiResponse, ok
from app.api.deps import SessionDep

router = APIRouter(prefix="/v1/auth", tags=["auth"])
svc = AuthService()


@router.post("/register", response_model=ApiResponse[RegisterResponse])
def register(payload: RegisterRequest, session: SessionDep, request: Request):
    rid = get_request_id(request)
    data = svc.register(session=session, payload=payload)
    return ok(data, request_id=rid)


@router.post("/login", response_model=ApiResponse[TokenPairResponse])
def login(payload: LoginRequest, session: SessionDep, request: Request):
    rid = get_request_id(request)
    data = svc.login(session=session, payload=payload)
    return ok(data, request_id=rid)


@router.post("/refresh", response_model=ApiResponse[RefreshResponse])
def refresh(payload: RefreshRequest, session: SessionDep, request: Request):
    rid = get_request_id(request)
    data = svc.refresh(session=session, refresh_token=payload.refresh_token)
    return ok(data, request_id=rid)


@router.post("/logout", response_model=ApiResponse[MessageResponse])
def logout(payload: LogoutRequest, session: SessionDep, request: Request):
    svc.logout(session=session, refresh_token=payload.refresh_token)
    rid = get_request_id(request)
    return ok(MessageResponse(message="Logged out"), request_id=rid)