import pytest
from unittest.mock import AsyncMock

from app.models.schemas import GameState, GameResponse
from app.services.game_engine import GameEngine, GameNotFoundError, GameOverError
from app.services.gemini_service import GeminiService


@pytest.fixture
def mock_gemini_service():
    service = AsyncMock(spec=GeminiService)
    service.generate_opening.return_value = {
        "narrative": "You awaken in a dungeon.",
        "choices": ["Search", "Call for help", "Try door"],
        "health_delta": 0,
        "new_items": ["rusty key"],
        "removed_items": [],
        "is_complete": False,
    }
    service.generate_response.return_value = {
        "narrative": "You find a hidden passage.",
        "choices": ["Enter", "Keep searching", "Go back"],
        "health_delta": -5,
        "new_items": ["map"],
        "removed_items": [],
        "is_complete": False,
    }
    return service


@pytest.fixture
def mock_firestore():
    fs = AsyncMock()
    fs.save_game = AsyncMock()
    fs.load_game = AsyncMock(return_value=None)
    return fs


@pytest.fixture
def engine(mock_gemini_service):
    return GameEngine(gemini_service=mock_gemini_service)


@pytest.fixture
def engine_with_firestore(mock_gemini_service, mock_firestore):
    return GameEngine(gemini_service=mock_gemini_service, firestore_service=mock_firestore)


class TestCreateGame:
    async def test_returns_game_response(self, engine):
        resp = await engine.create_game("Hero", "fantasy")
        assert isinstance(resp, GameResponse)

    async def test_sets_initial_state(self, engine):
        resp = await engine.create_game("Hero", "fantasy")
        assert resp.health == 100
        assert resp.turn_count == 1
        assert resp.is_alive is True
        assert resp.is_complete is False

    async def test_includes_narrative_and_choices(self, engine):
        resp = await engine.create_game("Hero", "fantasy")
        assert resp.narrative == "You awaken in a dungeon."
        assert len(resp.choices) == 3

    async def test_includes_starting_items(self, engine):
        resp = await engine.create_game("Hero", "fantasy")
        assert "rusty key" in resp.inventory

    async def test_calls_gemini(self, engine, mock_gemini_service):
        await engine.create_game("Hero", "fantasy")
        mock_gemini_service.generate_opening.assert_called_once_with("fantasy", "Hero")

    async def test_stores_state(self, engine):
        resp = await engine.create_game("Hero", "fantasy")
        state = await engine.get_game(resp.game_id)
        assert isinstance(state, GameState)
        assert state.player_name == "Hero"

    async def test_saves_to_firestore(self, engine_with_firestore, mock_firestore):
        resp = await engine_with_firestore.create_game("Hero", "fantasy")
        mock_firestore.save_game.assert_called_once()
        call_args = mock_firestore.save_game.call_args
        assert call_args[0][0] == resp.game_id


class TestProcessAction:
    async def test_updates_state(self, engine):
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Search")
        assert resp.turn_count == 2
        assert resp.narrative == "You find a hidden passage."

    async def test_applies_health_delta(self, engine):
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Search")
        assert resp.health == 95

    async def test_adds_items(self, engine):
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Search")
        assert "map" in resp.inventory
        assert "rusty key" in resp.inventory

    async def test_removes_items(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Key breaks.", "choices": ["Continue"],
            "health_delta": 0, "new_items": [], "removed_items": ["rusty key"],
            "is_complete": False,
        }
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Use key")
        assert "rusty key" not in resp.inventory

    async def test_invalid_id_raises(self, engine):
        with pytest.raises(GameNotFoundError):
            await engine.process_action("nonexistent", "test")


class TestHealthClamping:
    async def test_floors_at_zero(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Crushed.", "choices": [],
            "health_delta": -200, "new_items": [], "removed_items": [],
            "is_complete": False,
        }
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Walk into trap")
        assert resp.health == 0
        assert resp.is_alive is False
        assert resp.is_complete is True

    async def test_caps_at_100(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Healed.", "choices": ["Continue"],
            "health_delta": 50, "new_items": [], "removed_items": [],
            "is_complete": False,
        }
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Heal")
        assert resp.health == 100


class TestGameCompletion:
    async def test_game_completes(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Victory!", "choices": [],
            "health_delta": 0, "new_items": [], "removed_items": [],
            "is_complete": True,
        }
        create = await engine.create_game("Hero", "fantasy")
        resp = await engine.process_action(create.game_id, "Win")
        assert resp.is_complete is True
        assert resp.choices == []

    async def test_completed_game_rejects_actions(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Victory!", "choices": [],
            "health_delta": 0, "new_items": [], "removed_items": [],
            "is_complete": True,
        }
        create = await engine.create_game("Hero", "fantasy")
        await engine.process_action(create.game_id, "Win")
        with pytest.raises(GameOverError):
            await engine.process_action(create.game_id, "Try again")


class TestGetGame:
    async def test_returns_none_for_missing(self, engine):
        result = await engine.get_game("nonexistent")
        assert result is None

    async def test_returns_state(self, engine):
        create = await engine.create_game("Hero", "fantasy")
        state = await engine.get_game(create.game_id)
        assert state is not None
        assert state.player_name == "Hero"
