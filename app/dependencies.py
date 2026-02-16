"""FastAPI dependency injection for service singletons.

Provides lazy-initialized, cacheable service instances that can be
overridden in tests via the app.dependency_overrides mechanism.
"""

import logging

from app.config import settings
from app.services.gemini_service import GeminiService
from app.services.game_engine import GameEngine

logger = logging.getLogger(__name__)

_gemini_service: GeminiService | None = None
_game_engine: GameEngine | None = None


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
        logger.info("Initialized GeminiService")
    return _gemini_service


def get_game_engine() -> GameEngine:
    global _game_engine
    if _game_engine is None:
        firestore = _init_firestore()
        _game_engine = GameEngine(
            gemini_service=get_gemini_service(),
            firestore_service=firestore,
        )
        logger.info("Initialized GameEngine (firestore=%s)", firestore is not None)
    return _game_engine


def get_tts_service():
    """Returns TTSService if enabled, None otherwise."""
    if not settings.enable_tts:
        return None
    from app.services.tts_service import TTSService
    return TTSService()


def _init_firestore():
    if not settings.enable_firestore:
        return None
    try:
        from app.services.firestore_service import FirestoreService
        return FirestoreService()
    except Exception as e:
        logger.warning("Firestore unavailable, using in-memory storage: %s", e)
        return None
