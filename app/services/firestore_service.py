"""Google Cloud Firestore integration for persistent game state storage."""

import logging
from typing import Any

from google.cloud.firestore_v1 import AsyncClient

from app.config import settings

logger = logging.getLogger(__name__)


class FirestoreService:
    """Async Firestore client for game state CRUD operations."""

    def __init__(self) -> None:
        self._db = AsyncClient(project=settings.gcp_project_id)
        self._collection = settings.firestore_collection

    async def save_game(self, game_id: str, state: dict[str, Any]) -> None:
        doc_ref = self._db.collection(self._collection).document(game_id)
        await doc_ref.set(state)
        logger.info("Saved game %s to Firestore", game_id)

    async def load_game(self, game_id: str) -> dict[str, Any] | None:
        doc_ref = self._db.collection(self._collection).document(game_id)
        doc = await doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def delete_game(self, game_id: str) -> None:
        doc_ref = self._db.collection(self._collection).document(game_id)
        await doc_ref.delete()
        logger.info("Deleted game %s from Firestore", game_id)
