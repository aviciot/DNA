"""
Rate Limiting Middleware (OPTIONAL)
===================================
Limits requests per client to prevent abuse

To enable:
1. pip install slowapi
2. Uncomment code in server.py
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance (key by IP address)
limiter = Limiter(key_func=get_remote_address)

# Usage in server.py:
# from utils.rate_limiting import limiter
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# app.add_middleware(SlowAPIMiddleware)

# Usage on specific tools:
# @limiter.limit("60/minute")  # Max 60 requests per minute
# @mcp.tool()
# async def expensive_query(...):
#     pass
