"""Application middleware for security, rate limiting, and request logging."""

import logging
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# File extensions considered static assets.
_STATIC_EXTENSIONS = (".css", ".js", ".ico", ".png", ".jpg", ".svg", ".woff2")


def _is_static_asset(path: str) -> bool:
    """Return True if the path looks like a static file request."""
    return path.startswith("/static") or path.endswith(_STATIC_EXTENSIONS)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "media-src 'self' data: blob:; "
            "connect-src 'self'; "
            "font-src 'self'"
        )
        # HSTS: instruct browsers to always use HTTPS (1 year).
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        # Cache static assets aggressively at the browser / CDN layer.
        if request.url.path.endswith(_STATIC_EXTENSIONS):
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per client IP."""

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for static assets and health checks.
        if _is_static_asset(request.url.path) or request.url.path == "/api/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        timestamps = self._requests[client_ip]
        self._requests[client_ip] = [
            t for t in timestamps if now - t < self.window_seconds
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            logger.warning("Rate limit exceeded for %s", client_ip)
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before retrying."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs request method, path, status, and latency for observability."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        if not _is_static_asset(request.url.path):
            # Extract Cloud Trace context propagated by Cloud Run.
            trace_header = request.headers.get("x-cloud-trace-context", "")
            trace_id = trace_header.split("/")[0] if trace_header else ""

            logger.info(
                "%s %s -> %d (%.1fms) trace=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                trace_id or "none",
            )
        return response
