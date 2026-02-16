import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.gemini_service import GeminiService


@pytest.fixture
def mock_gemini_response():
    """Canned response matching GeminiService output format."""
    return {
        "narrative": "You find yourself in a dark, enchanted forest. Ancient trees tower above you, their branches whispering secrets.",
        "choices": [
            "Follow the glowing path deeper into the forest",
            "Climb the nearest tree to get a better view",
            "Search the undergrowth for useful items",
        ],
        "health_delta": 0,
        "new_items": ["rusty sword"],
        "removed_items": [],
        "is_complete": False,
    }


@pytest.fixture
def mock_gemini_service(mock_gemini_response):
    """Mock GeminiService that returns canned responses without needing a real API key."""
    service = AsyncMock(spec=GeminiService)
    service.generate_opening.return_value = mock_gemini_response
    service.generate_response.return_value = mock_gemini_response
    return service


@pytest.fixture
async def async_client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
