"""
Security utilities for Semantic Drive Search.

Provides rate limiting, input validation, and security headers.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


@dataclass
class ClientState:
    """Track rate limit state for a single client."""
    minute_count: int = 0
    hour_count: int = 0
    burst_count: int = 0
    last_minute_reset: float = field(default_factory=time.time)
    last_hour_reset: float = field(default_factory=time.time)
    last_request: float = 0


class RateLimiter:
    """
    Simple in-memory rate limiter.

    For production, consider using Redis-backed rate limiting.
    """

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.clients: dict[str, ClientState] = defaultdict(ClientState)

    def _get_client_key(self, request: Request) -> str:
        """Get a unique key for the client."""
        # Use X-Forwarded-For if behind a proxy, otherwise use client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> tuple[bool, str | None]:
        """
        Check if the request should be allowed.

        Returns:
            Tuple of (allowed, error_message)
        """
        key = self._get_client_key(request)
        now = time.time()
        state = self.clients[key]

        # Reset counters if time windows have passed
        if now - state.last_minute_reset >= 60:
            state.minute_count = 0
            state.last_minute_reset = now

        if now - state.last_hour_reset >= 3600:
            state.hour_count = 0
            state.last_hour_reset = now

        # Check burst (requests in last second)
        if now - state.last_request < 1:
            state.burst_count += 1
            if state.burst_count > self.config.burst_size:
                return False, f"Rate limit exceeded: max {self.config.burst_size} requests per second"
        else:
            state.burst_count = 1

        # Check minute limit
        if state.minute_count >= self.config.requests_per_minute:
            return False, f"Rate limit exceeded: max {self.config.requests_per_minute} requests per minute"

        # Check hour limit
        if state.hour_count >= self.config.requests_per_hour:
            return False, f"Rate limit exceeded: max {self.config.requests_per_hour} requests per hour"

        # Update counters
        state.minute_count += 1
        state.hour_count += 1
        state.last_request = now

        return True, None

    def cleanup(self, max_age: int = 7200):
        """Remove stale client entries (older than max_age seconds)."""
        now = time.time()
        stale = [k for k, v in self.clients.items() if now - v.last_request > max_age]
        for k in stale:
            del self.clients[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, config: RateLimitConfig = None, exempt_paths: list[str] = None):
        super().__init__(app)
        self.limiter = RateLimiter(config)
        self.exempt_paths = exempt_paths or ["/health", "/auth/", "/static/"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if path is exempt
        for exempt in self.exempt_paths:
            if request.url.path.startswith(exempt):
                return await call_next(request)

        # Check rate limit
        allowed, error = self.limiter.check(request)
        if not allowed:
            raise HTTPException(status_code=429, detail=error)

        return await call_next(request)


def validate_folder_id(folder_id: str) -> str:
    """
    Validate and sanitize a Google Drive folder ID.

    Args:
        folder_id: Raw folder ID or URL

    Returns:
        Sanitized folder ID

    Raises:
        ValueError: If the folder ID is invalid
    """
    import re

    if not folder_id:
        raise ValueError("Folder ID is required")

    # Extract from URL if needed
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", folder_id)
    if match:
        folder_id = match.group(1)

    # Validate format (Google Drive IDs are alphanumeric with - and _)
    folder_id = folder_id.strip()
    if not re.match(r"^[a-zA-Z0-9_-]+$", folder_id):
        raise ValueError("Invalid folder ID format")

    if len(folder_id) > 100:
        raise ValueError("Folder ID too long")

    return folder_id


def validate_search_query(query: str) -> str:
    """
    Validate and sanitize a search query.

    Args:
        query: Raw search query

    Returns:
        Sanitized query

    Raises:
        ValueError: If the query is invalid
    """
    if not query:
        raise ValueError("Search query is required")

    query = query.strip()

    if len(query) < 1:
        raise ValueError("Search query is too short")

    if len(query) > 500:
        raise ValueError("Search query is too long (max 500 characters)")

    # Remove any control characters
    import re
    query = re.sub(r"[\x00-\x1f\x7f]", "", query)

    return query


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe display.

    Args:
        filename: Raw filename

    Returns:
        Sanitized filename
    """
    import re

    if not filename:
        return "unknown"

    # Remove path separators and null bytes
    filename = re.sub(r"[/\\:\x00]", "_", filename)

    # Limit length
    if len(filename) > 255:
        filename = filename[:252] + "..."

    return filename


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://lh3.googleusercontent.com https://drive.google.com; "
            "media-src 'self' https://drive.google.com; "
            "connect-src 'self';"
        )

        # Other security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
