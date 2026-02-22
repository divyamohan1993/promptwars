"""QuestForge application entry point.

Configures FastAPI with middleware, routes, and static file serving.
Integrates Google Cloud services: Gemini AI, Firestore, TTS, Translate,
Imagen, Cloud Storage, and Cloud Logging.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.logging_config import setup_logging
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.routes.game import router as game_router
from app.routes.health import router as health_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application startup and shutdown lifecycle.

    Logs enabled Google Cloud service integrations at startup and
    performs clean shutdown logging.
    """
    enabled_services = [
        name
        for name, flag in [
            ("Firestore", settings.enable_firestore),
            ("TTS", settings.enable_tts),
            ("Translate", settings.enable_translate),
            ("Storage", settings.enable_storage),
            ("Imagen", settings.enable_imagen),
        ]
        if flag
    ]
    logger.info(
        "QuestForge %s starting — enabled services: %s",
        settings.app_version,
        ", ".join(enabled_services) or "core only",
    )
    if not settings.google_api_key:
        logger.warning("GOOGLE_API_KEY is not set — Gemini calls will fail")
    yield
    logger.info("QuestForge %s shutting down", settings.app_version)


app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware stack — applied in reverse order of addition.
#   Request flow: CORS → GZip → RateLimit → Logging → SecurityHeaders
# ---------------------------------------------------------------------------
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.rate_limit_per_minute)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# API routes (registered before static mount so they take priority)
app.include_router(health_router)
app.include_router(game_router)

# Static files served from root path; html=True serves index.html for "/"
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=True,
    )
