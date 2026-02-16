import pytest
from unittest.mock import AsyncMock

from app.models.schemas import Genre


class TestHealthEndpoint:
    async def test_returns_200(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200

    async def test_returns_service_info(self, client):
        data = (await client.get("/api/health")).json()
        assert data["status"] == "healthy"
        assert data["service"] == "QuestForge"
        assert "version" in data
        assert "features" in data


class TestStartGame:
    async def test_creates_game(self, client, mock_gemini_response):
        resp = await client.post("/api/game/start", json={"player_name": "Hero", "genre": "fantasy"})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert data["narrative"] == mock_gemini_response["narrative"]
        assert data["health"] == 100
        assert data["turn_count"] == 1
        assert data["is_alive"] is True

    async def test_invalid_genre_returns_422(self, client):
        resp = await client.post("/api/game/start", json={"player_name": "Hero", "genre": "romance"})
        assert resp.status_code == 422

    async def test_empty_name_returns_422(self, client):
        resp = await client.post("/api/game/start", json={"player_name": "", "genre": "fantasy"})
        assert resp.status_code == 422

    async def test_all_genres_work(self, client):
        for genre in Genre:
            resp = await client.post(
                "/api/game/start",
                json={"player_name": "Hero", "genre": genre.value},
            )
            assert resp.status_code == 200, f"Genre {genre.value} failed"
            data = resp.json()
            assert data["is_alive"] is True
            assert "game_id" in data


class TestTakeAction:
    async def test_processes_action(self, client, mock_gemini_response):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "genre": "fantasy"})
        game_id = start.json()["game_id"]
        resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Follow the path"})
        assert resp.status_code == 200
        assert resp.json()["turn_count"] == 2

    async def test_invalid_game_id_returns_404(self, client):
        resp = await client.post("/api/game/action", json={"game_id": "nonexistent", "action": "test"})
        assert resp.status_code == 404

    async def test_action_with_health_delta(self, client, mock_gemini_service, mock_gemini_response):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "genre": "fantasy"})
        game_id = start.json()["game_id"]
        mock_gemini_service.generate_response.return_value = {
            **mock_gemini_response, "health_delta": -15,
        }
        resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Fight"})
        assert resp.json()["health"] == 85

    async def test_dead_game_returns_400(self, client, mock_gemini_service, mock_gemini_response):
        """Start a game, kill the player via massive damage, then verify
        further actions return 400 (game over)."""
        start = await client.post("/api/game/start", json={"player_name": "Hero", "genre": "fantasy"})
        game_id = start.json()["game_id"]
        # Set response so the player takes lethal damage
        mock_gemini_service.generate_response.return_value = {
            **mock_gemini_response,
            "health_delta": -200,
            "is_complete": False,
        }
        death_resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Walk into trap"})
        assert death_resp.json()["health"] == 0
        assert death_resp.json()["is_alive"] is False
        # Now try another action on the dead game
        resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Try again"})
        assert resp.status_code == 400


class TestGetGame:
    async def test_returns_game_state(self, client):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "genre": "fantasy"})
        game_id = start.json()["game_id"]
        resp = await client.get(f"/api/game/{game_id}")
        assert resp.status_code == 200
        assert resp.json()["game_id"] == game_id

    async def test_invalid_id_returns_404(self, client):
        resp = await client.get("/api/game/nonexistent")
        assert resp.status_code == 404


class TestTTS:
    async def test_tts_disabled_returns_503(self, client):
        resp = await client.post("/api/game/tts", json={"text": "Hello"})
        assert resp.status_code == 503

    async def test_tts_empty_text_returns_422(self, client):
        resp = await client.post("/api/game/tts", json={"text": ""})
        assert resp.status_code == 422

    async def test_tts_text_too_long_returns_422(self, client):
        resp = await client.post("/api/game/tts", json={"text": "A" * 2001})
        assert resp.status_code == 422
