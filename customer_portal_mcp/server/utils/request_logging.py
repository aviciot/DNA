"""Request logging middleware"""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in ("/healthz", "/health"):
            return await call_next(request)
        cid = str(uuid.uuid4())[:8]
        start = time.time()
        response = await call_next(request)
        ms = int((time.time() - start) * 1000)
        logger.info(f"[{cid}] {request.method} {request.url.path} → {response.status_code} ({ms}ms)")
        return response
