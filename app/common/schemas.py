from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    reason: str
    extra: Optional[Any] = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class Meta(BaseModel):
    request_id: Optional[str] = None
    # Bạn có thể mở rộng: pagination, version, timing, ...


class ApiResponse(BaseModel, Generic[T]):
    ok: bool = True
    data: Optional[T] = None
    error: Optional[ErrorBody] = None
    meta: Meta = Field(default_factory=Meta)


def ok(data: T | None = None, request_id: str | None = None) -> ApiResponse[T]:
    return ApiResponse(ok=True, data=data, error=None, meta=Meta(request_id=request_id))


def fail(
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    request_id: str | None = None,
) -> ApiResponse[None]:
    return ApiResponse(
        ok=False,
        data=None,
        error=ErrorBody(code=code, message=message, details=details or []),
        meta=Meta(request_id=request_id),
    )