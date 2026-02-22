"""Google Cloud Storage for generated assets (audio, images).

Wraps the synchronous GCS client with ``asyncio.to_thread`` so that
blocking upload / lookup operations do not stall the event loop.
"""

from __future__ import annotations

import asyncio
import logging

from google.cloud import storage

from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Upload and retrieve assets from Google Cloud Storage."""

    def __init__(self) -> None:
        self._client = storage.Client(project=settings.gcp_project_id)
        self._bucket = self._client.bucket(settings.gcs_bucket_name)

    async def upload_bytes(self, data: bytes, blob_name: str, content_type: str) -> str:
        """Upload *data* to GCS and return its public URL."""
        blob = self._bucket.blob(blob_name)
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        await asyncio.to_thread(blob.make_public)
        url: str = blob.public_url
        logger.info("Uploaded %s (%d bytes) to GCS", blob_name, len(data))
        return url

    async def get_public_url(self, blob_name: str) -> str | None:
        """Return the public URL of *blob_name*, or ``None`` if it does not exist."""
        blob = self._bucket.blob(blob_name)
        exists = await asyncio.to_thread(blob.exists)
        if exists:
            return blob.public_url
        return None
