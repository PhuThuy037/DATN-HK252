import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = rid

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)