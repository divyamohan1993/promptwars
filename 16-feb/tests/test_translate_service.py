import pytest
from unittest.mock import MagicMock, patch

from app.services.translate_service import TranslateService


class TestTranslateService:
    @patch("app.services.translate_service.translate.Client")
    def test_translate_returns_result(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.translate.return_value = {"translatedText": "Hola mundo"}
        mock_client_cls.return_value = mock_client

        svc = TranslateService()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            svc.translate_text("Hello world", "es")
        )
        assert result["translated_text"] == "Hola mundo"
        assert result["source_language"] == "en"

    @patch("app.services.translate_service.translate.Client")
    def test_caching_works(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.translate.return_value = {"translatedText": "Bonjour"}
        mock_client_cls.return_value = mock_client

        svc = TranslateService()

        import asyncio
        loop = asyncio.get_event_loop()
        result1 = loop.run_until_complete(svc.translate_text("Hello", "fr"))
        result2 = loop.run_until_complete(svc.translate_text("Hello", "fr"))

        assert result1["translated_text"] == "Bonjour"
        assert result2["translated_text"] == "Bonjour"
        # Should only call API once due to caching
        assert mock_client.translate.call_count == 1

    @patch("app.services.translate_service.translate.Client")
    def test_failure_returns_original_text(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.translate.side_effect = Exception("API down")
        mock_client_cls.return_value = mock_client

        svc = TranslateService()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            svc.translate_text("Hello", "es")
        )
        assert result["translated_text"] == "Hello"
        assert result["source_language"] == "en"
