"""Google Cloud Text-to-Speech integration for narrative narration."""

import base64
import hashlib
import logging
from collections import OrderedDict

from google.cloud import texttospeech_v1 as texttospeech

logger = logging.getLogger(__name__)

# Maximum number of TTS responses to keep in the in-memory cache.
_CACHE_MAX_SIZE = 50


class TTSService:
    """Converts narrative text to spoken audio using Google Cloud TTS."""

    def __init__(self) -> None:
        self._client = texttospeech.TextToSpeechAsyncClient()
        # OrderedDict gives us LRU semantics: oldest entries are evicted first.
        self._cache: OrderedDict[str, str] = OrderedDict()

    def _cache_key(self, text: str, language_code: str) -> str:
        """Create a deterministic cache key from the input parameters."""
        raw = f"{language_code}:{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def synthesize(
        self, text: str, language_code: str = "en-US"
    ) -> str:
        """Convert text to speech. Returns base64-encoded MP3 audio."""
        key = self._cache_key(text, language_code)

        # Return cached response if available.
        if key in self._cache:
            logger.info("TTS cache hit for %d-char text (key=%s)", len(text), key[:12])
            # Move to end so it is treated as most-recently used.
            self._cache.move_to_end(key)
            return self._cache[key]

        logger.info("TTS cache miss for %d-char text (key=%s)", len(text), key[:12])

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
        )

        try:
            response = await self._client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
            )
            audio_b64 = base64.b64encode(response.audio_content).decode("utf-8")
            logger.info("TTS synthesized %d chars -> %d bytes audio", len(text), len(response.audio_content))

            # Store in cache, evicting oldest entry if at capacity.
            if len(self._cache) >= _CACHE_MAX_SIZE:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.debug("TTS cache evicted entry %s", evicted_key[:12])
            self._cache[key] = audio_b64

            return audio_b64
        except Exception as e:
            logger.error("TTS synthesis failed: %s", e)
            raise
