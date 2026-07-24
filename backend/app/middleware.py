"""HTTP middleware."""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.logging_config import request_id_ctx

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request ID to every request for tracing across replicas.

    Reuses an inbound ``X-Request-ID`` (e.g. from a load balancer) if present,
    otherwise generates one. The ID is stored in a context var so structured logs
    emitted while handling the request are correlated, and echoed back in the
    response header.

    Also the last line of defense for unhandled errors: any exception escaping the
    route is logged (with request-id + traceback) and turned into a uniform, safe
    500 body — internals never leak to the client, regardless of debug mode.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )
        finally:
            request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
