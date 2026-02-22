from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.common.error_codes import ErrorCode
from app.common.errors import AppError
from app.common.request_id import get_request_id
from app.common.schemas import ErrorDetail, fail


def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = get_request_id(request)
    details = [ErrorDetail(**d) for d in exc.details]
    payload = fail(
        code=exc.code.value, message=exc.message, details=details, request_id=rid
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    rid = get_request_id(request)
    details: list[ErrorDetail] = []

    for e in exc.errors():
        loc = e.get("loc", [])
        field = ".".join(
            str(x)
            for x in loc
            if x not in ("body", "query", "path", "header", "cookie")
        )
        details.append(
            ErrorDetail(
                field=field or None, reason=e.get("msg", "invalid"), extra=e.get("type")
            )
        )

    payload = fail(
        code=ErrorCode.VALIDATION_ERROR.value,
        message="Invalid request",
        details=details,
        request_id=rid,
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = get_request_id(request)

    status_map = {
        401: ErrorCode.UNAUTHORIZED.value,
        403: ErrorCode.FORBIDDEN.value,
        404: ErrorCode.NOT_FOUND.value,
        409: ErrorCode.CONFLICT.value,
        429: ErrorCode.RATE_LIMITED.value,
    }
    code = status_map.get(exc.status_code, f"HTTP_{exc.status_code}")

    payload = fail(code=code, message=str(exc.detail), details=[], request_id=rid)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = get_request_id(request)
    payload = fail(
        code=ErrorCode.INTERNAL_ERROR.value,
        message="Something went wrong",
        details=[],
        request_id=rid,
    )
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump()
    )