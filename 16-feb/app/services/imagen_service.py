"""Vertex AI Imagen integration for scene illustration generation.

Uses the ``imagen-3.0-generate-002`` model with strict safety filters
and person-generation disabled to produce child-safe pixel-art scenes.
The synchronous SDK call is offloaded to a thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import base64
import logging

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

from app.config import settings

logger = logging.getLogger(__name__)


class ImagenService:
    """Generate scene illustrations using Vertex AI Imagen."""

    def __init__(self) -> None:
        vertexai.init(project=settings.gcp_project_id, location="us-central1")
        self._model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

    async def generate_scene_image(
        self, scene_description: str, style: str = "pixel art"
    ) -> str | None:
        """Generate a scene image. Returns base64-encoded PNG or ``None`` on failure."""
        # Truncate description to prevent excessively long prompts.
        safe_desc = scene_description[:300]
        prompt = (
            f"A {style} illustration for a children's adventure game: {safe_desc}. "
            f"Retro 80s aesthetic, neon glow effects, safe for children, "
            f"colorful, no text in image, no people."
        )
        try:
            response = await asyncio.to_thread(
                self._model.generate_images,
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="block_most",
                person_generation="dont_allow",
            )
            if response.images:
                image_bytes = response.images[0]._image_bytes
                b64 = base64.b64encode(image_bytes).decode("utf-8")
                logger.info("Generated scene image for: %s", safe_desc[:50])
                return b64
            return None
        except Exception as e:
            logger.error("Imagen generation failed: %s", e)
            return None
