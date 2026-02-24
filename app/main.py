from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
import app.db.all_models
from app.api.auth import router as auth_router
from app.api.conversation import router as conversation_router
from app.api.debug import router as debug_router

from app.common.errors import AppError
from app.common.handlers import (
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.common.request_id import RequestIdMiddleware

app = FastAPI()

app.add_middleware(RequestIdMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(auth_router)
app.include_router(conversation_router)
app.include_router(debug_router)


@app.get("/health")
def health():
    return {"status": "ok"}
