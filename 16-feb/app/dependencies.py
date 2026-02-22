"""FastAPI dependency injection for service singletons.

Provides lazy-initialized, cacheable service instances that can be
overridden in tests via ``app.dependency_overrides``.

Each Google Cloud service is guarded by its feature toggle in
:mod:`app.config`.  When a service is disabled the corresponding
dependency returns ``None`` and the route layer responds with 503.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.services.firestore_service import FirestoreService
    from app.services.game_engine import GameEngine
    from app.services.gemini_service import GeminiService
    from app.services.imagen_service import ImagenService
    from app.services.storage_service import StorageService
    from app.services.translate_service import TranslateService
    from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

# Lazy singletons — initialised on first request, reused for lifetime.
_gemini_service: GeminiService | None = None
_game_engine: GameEngine | None = None
_tts_service: TTSService | None = None
_translate_service: TranslateService | None = None
_storage_service: StorageService | None = None
_imagen_service: ImagenService | None = None


def get_gemini_service() -> GeminiService:
    """Return (or create) the singleton GeminiService."""
    global _gemini_service
    if _gemini_service is None:
        from app.services.gemini_service import GeminiService
        _gemini_service = GeminiService()
        logger.info("Initialized GeminiService")
    return _gemini_service


def get_game_engine() -> GameEngine:
    """Return (or create) the singleton GameEngine."""
    global _game_engine
    if _game_engine is None:
        from app.services.game_engine import GameEngine
        firestore = _init_firestore()
        _game_engine = GameEngine(
            gemini_service=get_gemini_service(),
            firestore_service=firestore,
        )
        logger.info("Initialized GameEngine (firestore=%s)", firestore is not None)
    return _game_engine


def get_tts_service() -> TTSService | None:
    """Return TTSService if enabled, ``None`` otherwise."""
    global _tts_service
    if not settings.enable_tts:
        return None
    if _tts_service is None:
        from app.services.tts_service import TTSService
        _tts_service = TTSService()
        logger.info("Initialized TTSService")
    return _tts_service


def get_translate_service() -> TranslateService | None:
    """Return TranslateService if enabled, ``None`` otherwise."""
    global _translate_service
    if not settings.enable_translate:
        return None
    if _translate_service is None:
        from app.services.translate_service import TranslateService
        _translate_service = TranslateService()
        logger.info("Initialized TranslateService")
    return _translate_service


def get_storage_service() -> StorageService | None:
    """Return StorageService if enabled, ``None`` otherwise."""
    global _storage_service
    if not settings.enable_storage:
        return None
    if _storage_service is None:
        from app.services.storage_service import StorageService
        _storage_service = StorageService()
        logger.info("Initialized StorageService")
    return _storage_service


def get_imagen_service() -> ImagenService | None:
    """Return ImagenService if enabled, ``None`` otherwise."""
    global _imagen_service
    if not settings.enable_imagen:
        return None
    if _imagen_service is None:
        from app.services.imagen_service import ImagenService
        _imagen_service = ImagenService()
        logger.info("Initialized ImagenService")
    return _imagen_service


def _init_firestore() -> FirestoreService | None:
    """Attempt to initialise Firestore; fall back to ``None`` on failure."""
    if not settings.enable_firestore:
        return None
    try:
        from app.services.firestore_service import FirestoreService
        return FirestoreService()
    except Exception as e:
        logger.warning("Firestore unavailable, using in-memory storage: %s", e)
        return None
