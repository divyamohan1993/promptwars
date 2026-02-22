"""Application middleware for security, rate limiting, and request logging.

Middleware is added to the FastAPI application in reverse order so that the
outermost layer (CORS) runs first on the request path and last on the
response path.  The order in main.py is:

    SecurityHeaders → Logging → RateLimit → GZip → CORS

Which means the actual request processing order is:

    CORS → GZip → RateLimit → Logging → SecurityHeaders → Route handler
"""

import logging
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# File extensions considered static assets (matched by suffix).
_STATIC_EXTENSIONS = frozenset(
    (".css", ".js", ".ico", ".png", ".jpg", ".jpeg", ".svg", ".webp",
     ".woff2", ".woff", ".ttf", ".map", ".webmanifest")
)


def _is_static_asset(path: str) -> bool:
    """Return True if the request path is for a static file."""
    dot = path.rfind(".")
    return dot != -1 and path[dot:] in _STATIC_EXTENSIONS


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defensive security headers to every response.

    Covers OWASP recommended headers: CSP, HSTS, X-Frame-Options,
    X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        h = response.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["X-XSS-Protection"] = "1; mode=block"
        h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        h["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        h["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob: https://storage.googleapis.com; "
            "media-src 'self' data: blob:; "
            "connect-src 'self'; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        # HSTS: instruct browsers to always use HTTPS (1 year).
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Cache static assets aggressively at the browser / CDN layer.
        if _is_static_asset(request.url.path):
            h["Cache-Control"] = "public, max-age=86400, immutable"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Memory-bounded, per-IP sliding-window rate limiter.

    Expired timestamps are pruned on every request.  If the number of
    tracked IPs exceeds ``_MAX_TRACKED_IPS`` the oldest entries are evicted
    to prevent unbounded memory growth from many unique clients.
    """

    _MAX_TRACKED_IPS = 10_000

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for static assets and health probes.
        if _is_static_asset(request.url.path) or request.url.path == "/api/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Prune expired timestamps for this IP.
        timestamps = self._requests[client_ip]
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._requests[client_ip]) >= self.max_requests:
            logger.warning("Rate limit exceeded for %s", client_ip)
            return Response(
                content='{"detail":"Rate limit exceeded. Please wait before retrying."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._requests[client_ip].append(now)

        # Evict oldest IPs if tracking too many unique clients.
        if len(self._requests) > self._MAX_TRACKED_IPS:
            oldest_keys = sorted(
                self._requests,
                key=lambda k: self._requests[k][-1] if self._requests[k] else 0,
            )[: len(self._requests) - self._MAX_TRACKED_IPS]
            for key in oldest_keys:
                del self._requests[key]

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs request method, path, status, and latency for observability.

    Integrates with Google Cloud Trace by extracting the
    ``x-cloud-trace-context`` header propagated by Cloud Run.
    """

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
