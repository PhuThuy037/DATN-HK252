from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

import app.db.all_models
from app.api.auth import router as auth_router
from app.api.company import router as company_router
from app.api.company_rules import router as company_rules_router
from app.api.company_settings import router as company_settings_router
from app.api.conversation import router as conversation_router
from app.api.debug import router as debug_router
from app.api.policy_admin import router as policy_admin_router
from app.api.rule_suggestions import router as rule_suggestions_router
from app.common.errors import AppError
from app.common.handlers import (
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.common.request_id import RequestIdMiddleware
from app.core.config import get_settings


def _parse_csv_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _parse_wildcard_or_list(raw: str | None) -> list[str]:
    values = _parse_csv_list(raw)
    if not values:
        return ["*"]
    if "*" in values:
        return ["*"]
    return values


settings = get_settings()
app = FastAPI()

origins = _parse_wildcard_or_list(settings.cors_allowed_origins)
allow_methods = _parse_wildcard_or_list(settings.cors_allow_methods)
allow_headers = _parse_wildcard_or_list(settings.cors_allow_headers)

# CORS spec does not allow credentials=true with wildcard origin.
allow_credentials = bool(settings.cors_allow_credentials and origins != ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)
app.add_middleware(RequestIdMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(auth_router)
app.include_router(company_router)
app.include_router(company_rules_router)
app.include_router(company_settings_router)
app.include_router(conversation_router)
app.include_router(debug_router)
app.include_router(policy_admin_router)
app.include_router(rule_suggestions_router)


@app.get("/health")
def health():
    return {"status": "ok"}

