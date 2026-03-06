"""API key authentication middleware"""
import hashlib
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config):
        super().__init__(app)
        self.config = config

    async def dispatch(self, request, call_next):
        if not self.config.is_authentication_enabled():
            return await call_next(request)

        if request.url.path.startswith(("/health", "/healthz", "/version", "/_info")):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(status_code=401, content={"error": "Missing or invalid Authorization header"})

        client_name = self.config.get_api_keys().get(parts[1])
        if not client_name:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        session_id = request.headers.get("x-session-id") or (
            "fp_" + hashlib.sha256(
                f"{request.client.host}:{request.headers.get('user-agent', '')}".encode()
            ).hexdigest()[:32]
        )
        request.state.client_id = client_name
        request.state.session_id = session_id
        return await call_next(request)
