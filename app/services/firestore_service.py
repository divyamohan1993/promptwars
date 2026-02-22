"""Google Cloud Firestore integration for persistent game state storage.

Uses the async Firestore client so that save / load operations do not
block the asyncio event loop.  The collection name is configurable via
the ``FIRESTORE_COLLECTION`` environment variable.
"""

from __future__ import annotations

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

    def _doc_ref(self, game_id: str):
        """Return a document reference for the given game ID."""
        return self._db.collection(self._collection).document(game_id)

    async def save_game(self, game_id: str, state: dict[str, Any]) -> None:
        """Persist game state to Firestore."""
        await self._doc_ref(game_id).set(state)
        logger.info("Saved game %s to Firestore", game_id)

    async def load_game(self, game_id: str) -> dict[str, Any] | None:
        """Load game state from Firestore by game ID."""
        doc = await self._doc_ref(game_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def delete_game(self, game_id: str) -> None:
        """Delete a game document from Firestore."""
        await self._doc_ref(game_id).delete()
        logger.info("Deleted game %s from Firestore", game_id)
