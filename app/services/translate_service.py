"""Google Cloud Translate API integration for multi-language narrative support.

Uses the v2 REST client with an LRU in-memory cache to avoid redundant
API calls for repeated translations (e.g. common UI strings).

Note: The v2 translate client is synchronous.  We wrap the blocking call
in ``asyncio.to_thread`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import OrderedDict

from google.cloud import translate_v2 as translate

logger = logging.getLogger(__name__)

_CACHE_MAX_SIZE = 100


class TranslateService:
    """Translates narrative text to the player's chosen language."""

    def __init__(self) -> None:
        self._client = translate.Client()
        self._cache: OrderedDict[str, str] = OrderedDict()

    async def translate_text(
        self, text: str, target_language: str, source_language: str = "en"
    ) -> dict[str, str]:
        """Translate *text* into *target_language*.

        Returns a dict with ``translated_text`` and ``source_language``.
        Cached results are returned immediately without an API call.
        """
        cache_key = hashlib.sha256(
            f"{target_language}:{text}".encode()
        ).hexdigest()

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            logger.debug("Translation cache hit for %s", cache_key[:12])
            return {"translated_text": self._cache[cache_key], "source_language": source_language}

        try:
            # The v2 client is synchronous — run in a thread so the
            # event loop is not blocked.
            result = await asyncio.to_thread(
                self._client.translate, text, target_language=target_language
            )
            translated: str = result["translatedText"]

            if len(self._cache) >= _CACHE_MAX_SIZE:
                self._cache.popitem(last=False)
            self._cache[cache_key] = translated

            logger.info(
                "Translated %d chars %s->%s", len(text), source_language, target_language
            )
            return {"translated_text": translated, "source_language": source_language}
        except Exception as e:
            logger.error("Translation failed: %s", e)
            return {"translated_text": text, "source_language": source_language}
