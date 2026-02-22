"""Health check endpoint for Cloud Run liveness / readiness probes.

Returns service metadata and feature-flag status so that operators and
monitoring dashboards can verify which Google Cloud integrations are active.
"""

import time

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api", tags=["health"])

_START_TIME = time.monotonic()


@router.get("/health")
async def health_check() -> dict:
    """Return service health status with version, uptime, and feature flags."""
    return {
        "status": "healthy",
        "service": settings.app_title,
        "version": settings.app_version,
        "uptime_seconds": round(time.monotonic() - _START_TIME),
        "features": {
            "gemini": True,
            "firestore": settings.enable_firestore,
            "tts": settings.enable_tts,
            "translate": settings.enable_translate,
            "storage": settings.enable_storage,
            "imagen": settings.enable_imagen,
        },
    }
