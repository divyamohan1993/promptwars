import pytest
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routes.game import set_game_engine, _engine
from app.services.game_engine import GameEngine
from app.services.gemini_service import GeminiService


@pytest.fixture
def mock_gemini_response():
    return {
        "narrative": "You stand at the gates of an ancient castle.",
        "choices": [
            "Enter through the main gate",
            "Sneak around to the side entrance",
            "Inspect the moat",
        ],
        "health_delta": 0,
        "new_items": ["torch"],
        "removed_items": [],
        "is_complete": False,
    }


@pytest.fixture
def engine_with_mock(mock_gemini_response):
    mock_service = AsyncMock(spec=GeminiService)
    mock_service.generate_opening.return_value = mock_gemini_response
    mock_service.generate_response.return_value = mock_gemini_response
    engine = GameEngine(mock_service)
    set_game_engine(engine)
    yield engine, mock_service
    set_game_engine(None)


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "QuestForge"


@pytest.mark.asyncio
async def test_start_game(engine_with_mock, mock_gemini_response):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/game/start",
            json={"player_name": "TestHero", "genre": "fantasy"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "game_id" in data
    assert data["narrative"] == mock_gemini_response["narrative"]
    assert data["choices"] == mock_gemini_response["choices"]
    assert data["health"] == 100
    assert "torch" in data["inventory"]
    assert data["turn_count"] == 1
    assert data["is_alive"] is True
    assert data["is_complete"] is False


@pytest.mark.asyncio
async def test_process_action(mock_gemini_response):
    mock_service = AsyncMock(spec=GeminiService)
    mock_service.generate_opening.return_value = mock_gemini_response

    action_response = {
        "narrative": "You push open the heavy gate and step inside.",
        "choices": ["Explore the courtyard", "Head to the tower", "Check the armory"],
        "health_delta": -10,
        "new_items": ["old key"],
        "removed_items": [],
        "is_complete": False,
    }
    mock_service.generate_response.return_value = action_response

    engine = GameEngine(mock_service)
    set_game_engine(engine)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            start_response = await client.post(
                "/api/game/start",
                json={"player_name": "TestHero", "genre": "fantasy"},
            )
            game_id = start_response.json()["game_id"]

            response = await client.post(
                "/api/game/action",
                json={"game_id": game_id, "action": "Enter through the main gate"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["game_id"] == game_id
        assert data["narrative"] == action_response["narrative"]
        assert data["health"] == 90
        assert "old key" in data["inventory"]
        assert data["turn_count"] == 2
    finally:
        set_game_engine(None)


@pytest.mark.asyncio
async def test_get_game_state(engine_with_mock):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        start_response = await client.post(
            "/api/game/start",
            json={"player_name": "TestHero", "genre": "fantasy"},
        )
        game_id = start_response.json()["game_id"]
        response = await client.get(f"/api/game/{game_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["game_id"] == game_id
    assert data["health"] == 100
    assert data["turn_count"] == 1


@pytest.mark.asyncio
async def test_get_game_invalid_id_returns_404(engine_with_mock):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/game/nonexistent-game-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_action_with_invalid_game_id_returns_404(engine_with_mock):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/game/action",
            json={"game_id": "nonexistent-game-id", "action": "Try something"},
        )
    assert response.status_code == 404
