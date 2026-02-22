from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

from app.common.enums import MemberRole
from app.common.errors import AppError
from app.common.error_codes import ErrorCode


class Action(str, Enum):
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(slots=True)
class AuthContext:
    user_id: UUID
    role: MemberRole
    company_id: Optional[UUID] = None


def forbid(
    message: str = "Forbidden", *, field: str | None = None, reason: str = "forbidden"
) -> AppError:
    details = [{"field": field, "reason": reason}] if field else []
    return AppError(403, ErrorCode.FORBIDDEN, message, details=details)


def not_found(
    message: str = "Not found", *, field: str | None = None, reason: str = "not_found"
) -> AppError:
    details = [{"field": field, "reason": reason}] if field else []
    return AppError(404, ErrorCode.NOT_FOUND, message, details=details)