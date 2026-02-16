import pytest
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.dependencies import get_game_engine
from app.services.game_engine import GameEngine
from app.services.gemini_service import GeminiService


@pytest.fixture
def mock_gemini_response():
    return {
        "narrative": "You find yourself in a dark, enchanted forest.",
        "choices": ["Follow the path", "Climb a tree", "Search the ground"],
        "health_delta": 0,
        "new_items": ["rusty sword"],
        "removed_items": [],
        "is_complete": False,
    }


@pytest.fixture
def mock_gemini_service(mock_gemini_response):
    service = AsyncMock(spec=GeminiService)
    service.generate_opening.return_value = mock_gemini_response
    service.generate_response.return_value = mock_gemini_response
    return service


@pytest.fixture
def game_engine(mock_gemini_service):
    return GameEngine(gemini_service=mock_gemini_service)


@pytest.fixture
def app_with_engine(game_engine):
    """Override the dependency to use our test engine."""
    app.dependency_overrides[get_game_engine] = lambda: game_engine
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_with_engine):
    transport = ASGITransport(app=app_with_engine)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
