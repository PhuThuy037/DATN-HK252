from __future__ import annotations

from typing import Optional
from app.common.error_codes import ErrorCode


class AppError(Exception):
    __slots__ = ("status_code", "code", "message", "details")

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: Optional[list[dict]] = None,
    ):
        Exception.__init__(self, message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []

    @staticmethod
    def not_found(message: str = "Resource not found") -> "AppError":
        return AppError(404, ErrorCode.NOT_FOUND, message)

    @staticmethod
    def conflict(code: ErrorCode, message: str, field: str | None = None) -> "AppError":
        details = [{"field": field, "reason": "conflict"}] if field else []
        return AppError(409, code, message, details=details)

    @staticmethod
    def forbidden(message: str = "Forbidden") -> "AppError":
        return AppError(403, ErrorCode.FORBIDDEN, message)

    @staticmethod
    def unauthorized(message: str = "Unauthorized") -> "AppError":
        return AppError(401, ErrorCode.UNAUTHORIZED, message)