import pytest
from unittest.mock import MagicMock, patch


class TestImagenService:
    @patch("app.services.imagen_service.vertexai")
    @patch("app.services.imagen_service.ImageGenerationModel")
    def test_generate_returns_base64(self, mock_model_cls, mock_vertexai):
        mock_image = MagicMock()
        mock_image._image_bytes = b"fake_png_bytes"
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[mock_image])
        mock_model_cls.from_pretrained.return_value = mock_model

        from app.services.imagen_service import ImagenService
        svc = ImagenService()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            svc.generate_scene_image("A dark forest")
        )
        assert result is not None
        import base64
        decoded = base64.b64decode(result)
        assert decoded == b"fake_png_bytes"

    @patch("app.services.imagen_service.vertexai")
    @patch("app.services.imagen_service.ImageGenerationModel")
    def test_failure_returns_none(self, mock_model_cls, mock_vertexai):
        mock_model = MagicMock()
        mock_model.generate_images.side_effect = Exception("API error")
        mock_model_cls.from_pretrained.return_value = mock_model

        from app.services.imagen_service import ImagenService
        svc = ImagenService()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            svc.generate_scene_image("test")
        )
        assert result is None

    @patch("app.services.imagen_service.vertexai")
    @patch("app.services.imagen_service.ImageGenerationModel")
    def test_no_images_returns_none(self, mock_model_cls, mock_vertexai):
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[])
        mock_model_cls.from_pretrained.return_value = mock_model

        from app.services.imagen_service import ImagenService
        svc = ImagenService()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            svc.generate_scene_image("test")
        )
        assert result is None

    @patch("app.services.imagen_service.vertexai")
    @patch("app.services.imagen_service.ImageGenerationModel")
    def test_safety_filters_in_prompt(self, mock_model_cls, mock_vertexai):
        mock_model = MagicMock()
        mock_model.generate_images.return_value = MagicMock(images=[])
        mock_model_cls.from_pretrained.return_value = mock_model

        from app.services.imagen_service import ImagenService
        svc = ImagenService()

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            svc.generate_scene_image("A forest", style="watercolor")
        )

        call_kwargs = mock_model.generate_images.call_args
        assert call_kwargs[1]["safety_filter_level"] == "block_most"
        assert call_kwargs[1]["person_generation"] == "dont_allow"
