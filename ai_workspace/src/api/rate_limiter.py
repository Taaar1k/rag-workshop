"""
Rate Limiter for RAG API Server.

Provides per-user rate limiting with configurable limits.
Uses slowapi with in-memory storage.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
from starlette.requests import Request
import os

# Rate limit configuration
DEFAULT_ANONYMOUS_LIMIT = os.getenv("RATE_LIMIT_ANONYMOUS", "100 per minute")
DEFAULT_AUTHENTICATED_LIMIT = os.getenv("RATE_LIMIT_AUTHENTICATED", "1000 per minute")
DEFAULT_BURST_LIMIT = os.getenv("RATE_LIMIT_BURST", "20 per minute")


def get_rate_limit_key(request: Request) -> str:
    """Key function for slowapi that returns different keys based on auth status.
    
    This allows slowapi to track rate limits separately for authenticated vs anonymous users.
    """
    # Check for Bearer token (JWT)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        return f"auth:{get_remote_address(request)}"
    return f"anon:{get_remote_address(request)}"


# Initialize limiter with in-memory storage and custom key function
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[DEFAULT_ANONYMOUS_LIMIT],
    storage_uri="memory://"
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    retry_after = 60  # seconds
    headers = {}
    if exc.limit:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": retry_after
        },
        headers=headers
    )


def get_rate_limit_for_user(request: Request) -> str:
    """Get appropriate rate limit based on user authentication status.
    
    Used for documentation and testing purposes.
    """
    # Check for Bearer token (JWT)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        return DEFAULT_AUTHENTICATED_LIMIT
    return DEFAULT_ANONYMOUS_LIMIT
