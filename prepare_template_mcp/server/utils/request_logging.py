"""
Request Logging Middleware
==========================
Logs all MCP requests with correlation IDs for debugging
"""

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing and correlation ID"""
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())[:8]
        request.state.correlation_id = correlation_id
        
        # Skip logging for health checks (too noisy)
        if request.url.path in ["/healthz", "/health"]:
            return await call_next(request)
        
        # Log request start
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        logger.info(f"[{correlation_id}] → {method} {path}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log successful response
            duration_ms = int((time.time() - start_time) * 1000)
            status = response.status_code
            
            if status >= 500:
                logger.error(f"[{correlation_id}] ← {status} {method} {path} ({duration_ms}ms)")
            elif status >= 400:
                logger.warning(f"[{correlation_id}] ← {status} {method} {path} ({duration_ms}ms)")
            else:
                logger.info(f"[{correlation_id}] ← {status} {method} {path} ({duration_ms}ms)")
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as e:
            # Log exceptions
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"[{correlation_id}] ✗ {method} {path} ({duration_ms}ms) - {str(e)}")
            raise
