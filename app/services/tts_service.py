"""Google Cloud Text-to-Speech integration for narrative narration."""

import base64
import logging

from google.cloud import texttospeech_v1 as texttospeech

logger = logging.getLogger(__name__)


class TTSService:
    """Converts narrative text to spoken audio using Google Cloud TTS."""

    def __init__(self) -> None:
        self._client = texttospeech.TextToSpeechAsyncClient()

    async def synthesize(
        self, text: str, language_code: str = "en-US"
    ) -> str:
        """Convert text to speech. Returns base64-encoded MP3 audio."""
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
            return audio_b64
        except Exception as e:
            logger.error("TTS synthesis failed: %s", e)
            raise
