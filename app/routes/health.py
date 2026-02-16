"""Health check endpoint for Cloud Run liveness/readiness probes."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Return service health status with version and feature flags."""
    return {
        "status": "healthy",
        "service": settings.app_title,
        "version": settings.app_version,
        "features": {
            "firestore": settings.enable_firestore,
            "tts": settings.enable_tts,
        },
    }
