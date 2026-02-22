import pytest
from unittest.mock import AsyncMock

from app.models.schemas import Adventure


class TestHealthEndpoint:
    async def test_returns_200(self, client):
        response = await client.get("/api/health")
        assert response.status_code == 200

    async def test_returns_service_info(self, client):
        data = (await client.get("/api/health")).json()
        assert data["status"] == "healthy"
        assert data["service"] == "QuestForge: The Upside Down"
        assert "version" in data
        assert "features" in data
        assert "uptime_seconds" in data

    async def test_features_include_all_services(self, client):
        data = (await client.get("/api/health")).json()
        features = data["features"]
        assert "gemini" in features
        assert "translate" in features
        assert "storage" in features
        assert "imagen" in features
        assert "firestore" in features
        assert "tts" in features


class TestStartGame:
    async def test_creates_game(self, client, mock_gemini_response):
        resp = await client.post("/api/game/start", json={"player_name": "Hero", "adventure": "hawkins-investigation"})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert data["narrative"] == mock_gemini_response["narrative"]
        assert data["health"] == 100
        assert data["turn_count"] == 1
        assert data["is_alive"] is True

    async def test_response_has_new_fields(self, client):
        resp = await client.post("/api/game/start", json={"player_name": "Eleven", "adventure": "upside-down"})
        data = resp.json()
        assert "choice_icons" in data
        assert "scene_visual" in data
        assert "map_nodes" in data
        assert "current_node_id" in data
        assert "achievements" in data
        assert "xp" in data

    async def test_invalid_adventure_returns_422(self, client):
        resp = await client.post("/api/game/start", json={"player_name": "Hero", "adventure": "romance"})
        assert resp.status_code == 422

    async def test_empty_name_returns_422(self, client):
        resp = await client.post("/api/game/start", json={"player_name": "", "adventure": "upside-down"})
        assert resp.status_code == 422

    async def test_all_adventures_work(self, client):
        for adv in Adventure:
            resp = await client.post(
                "/api/game/start",
                json={"player_name": "Hero", "adventure": adv.value},
            )
            assert resp.status_code == 200, f"Adventure {adv.value} failed"
            data = resp.json()
            assert data["is_alive"] is True
            assert "game_id" in data


class TestTakeAction:
    async def test_processes_action(self, client, mock_gemini_response):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "adventure": "hawkins-investigation"})
        game_id = start.json()["game_id"]
        resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Follow the path"})
        assert resp.status_code == 200
        assert resp.json()["turn_count"] == 2

    async def test_invalid_game_id_returns_404(self, client):
        resp = await client.post("/api/game/action", json={"game_id": "nonexistent", "action": "test"})
        assert resp.status_code == 404

    async def test_action_with_health_delta(self, client, mock_gemini_service, mock_gemini_response):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "adventure": "hawkins-investigation"})
        game_id = start.json()["game_id"]
        mock_gemini_service.generate_response.return_value = {
            **mock_gemini_response, "health_delta": -15,
        }
        resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Fight"})
        assert resp.json()["health"] == 85

    async def test_dead_game_returns_400(self, client, mock_gemini_service, mock_gemini_response):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "adventure": "hawkins-investigation"})
        game_id = start.json()["game_id"]
        mock_gemini_service.generate_response.return_value = {
            **mock_gemini_response,
            "health_delta": -200,
            "is_complete": False,
        }
        death_resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Walk into trap"})
        assert death_resp.json()["health"] == 0
        assert death_resp.json()["is_alive"] is False
        resp = await client.post("/api/game/action", json={"game_id": game_id, "action": "Try again"})
        assert resp.status_code == 400


class TestGetGame:
    async def test_returns_game_state(self, client):
        start = await client.post("/api/game/start", json={"player_name": "Hero", "adventure": "hawkins-investigation"})
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


class TestTranslate:
    async def test_translate_disabled_returns_503(self, client):
        resp = await client.post("/api/game/translate", json={"text": "Hello", "target_language": "es"})
        assert resp.status_code == 503

    async def test_translate_empty_text_returns_422(self, client):
        resp = await client.post("/api/game/translate", json={"text": "", "target_language": "es"})
        assert resp.status_code == 422

    async def test_translate_text_too_long_returns_422(self, client):
        resp = await client.post("/api/game/translate", json={"text": "A" * 5001, "target_language": "es"})
        assert resp.status_code == 422


class TestImage:
    async def test_image_disabled_returns_503(self, client):
        resp = await client.post("/api/game/image", json={"prompt": "A dark forest"})
        assert resp.status_code == 503

    async def test_image_empty_prompt_returns_422(self, client):
        resp = await client.post("/api/game/image", json={"prompt": ""})
        assert resp.status_code == 422

    async def test_image_prompt_too_long_returns_422(self, client):
        resp = await client.post("/api/game/image", json={"prompt": "A" * 501})
        assert resp.status_code == 422
