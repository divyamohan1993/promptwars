import pytest
from unittest.mock import AsyncMock

from app.models.schemas import GameState, GameResponse
from app.services.game_engine import GameEngine, GameNotFoundError
from app.services.gemini_service import GeminiService


@pytest.fixture
def mock_gemini_service():
    service = AsyncMock(spec=GeminiService)
    service.generate_opening.return_value = {
        "narrative": "You awaken in a mysterious dungeon.",
        "choices": ["Search the room", "Call for help", "Try the door"],
        "health_delta": 0,
        "new_items": ["rusty key"],
        "removed_items": [],
        "is_complete": False,
    }
    service.generate_response.return_value = {
        "narrative": "You search the room and find a hidden passage.",
        "choices": ["Enter the passage", "Keep searching", "Go back"],
        "health_delta": -5,
        "new_items": ["map"],
        "removed_items": [],
        "is_complete": False,
    }
    return service


@pytest.fixture
def game_engine(mock_gemini_service):
    return GameEngine(mock_gemini_service)


class TestCreateGame:
    @pytest.mark.asyncio
    async def test_create_game_returns_game_response(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert isinstance(response, GameResponse)

    @pytest.mark.asyncio
    async def test_create_game_has_valid_game_id(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert response.game_id is not None
        assert len(response.game_id) > 0

    @pytest.mark.asyncio
    async def test_create_game_sets_narrative(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert response.narrative == "You awaken in a mysterious dungeon."

    @pytest.mark.asyncio
    async def test_create_game_sets_choices(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert len(response.choices) == 3
        assert "Search the room" in response.choices

    @pytest.mark.asyncio
    async def test_create_game_initial_health(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert response.health == 100

    @pytest.mark.asyncio
    async def test_create_game_initial_inventory(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert "rusty key" in response.inventory

    @pytest.mark.asyncio
    async def test_create_game_turn_count_is_one(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert response.turn_count == 1

    @pytest.mark.asyncio
    async def test_create_game_is_alive(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert response.is_alive is True

    @pytest.mark.asyncio
    async def test_create_game_not_complete(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        assert response.is_complete is False

    @pytest.mark.asyncio
    async def test_create_game_calls_generate_opening(self, game_engine, mock_gemini_service):
        await game_engine.create_game("Hero", "fantasy")
        mock_gemini_service.generate_opening.assert_called_once_with("fantasy", "Hero")

    @pytest.mark.asyncio
    async def test_create_game_stores_state(self, game_engine):
        response = await game_engine.create_game("Hero", "fantasy")
        state = game_engine.get_game(response.game_id)
        assert isinstance(state, GameState)
        assert state.player_name == "Hero"


class TestProcessAction:
    @pytest.mark.asyncio
    async def test_process_action_returns_game_response(self, game_engine):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search the room")
        assert isinstance(response, GameResponse)

    @pytest.mark.asyncio
    async def test_process_action_updates_narrative(self, game_engine):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search the room")
        assert response.narrative == "You search the room and find a hidden passage."

    @pytest.mark.asyncio
    async def test_process_action_updates_choices(self, game_engine):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search the room")
        assert "Enter the passage" in response.choices

    @pytest.mark.asyncio
    async def test_process_action_increments_turn(self, game_engine):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search the room")
        assert response.turn_count == 2

    @pytest.mark.asyncio
    async def test_process_action_applies_health_delta(self, game_engine):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search the room")
        assert response.health == 95

    @pytest.mark.asyncio
    async def test_process_action_adds_items(self, game_engine):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search the room")
        assert "map" in response.inventory
        assert "rusty key" in response.inventory

    @pytest.mark.asyncio
    async def test_process_action_calls_generate_response(self, game_engine, mock_gemini_service):
        create_resp = await game_engine.create_game("Hero", "fantasy")
        await game_engine.process_action(create_resp.game_id, "Search the room")
        mock_gemini_service.generate_response.assert_called_once()


class TestHealthClamping:
    @pytest.mark.asyncio
    async def test_health_does_not_go_below_zero(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "A boulder crushes you.",
            "choices": ["Accept your fate"],
            "health_delta": -200,
            "new_items": [],
            "removed_items": [],
            "is_complete": False,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Walk into trap")
        assert response.health == 0
        assert response.is_alive is False

    @pytest.mark.asyncio
    async def test_health_does_not_exceed_100(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "A healing spring restores you.",
            "choices": ["Continue onward"],
            "health_delta": 50,
            "new_items": [],
            "removed_items": [],
            "is_complete": False,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Drink from spring")
        assert response.health == 100


class TestInventoryManagement:
    @pytest.mark.asyncio
    async def test_items_added_to_inventory(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "You find a sword and a shield.",
            "choices": ["Equip them", "Leave them"],
            "health_delta": 0,
            "new_items": ["sword", "shield"],
            "removed_items": [],
            "is_complete": False,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Search chest")
        assert "sword" in response.inventory
        assert "shield" in response.inventory

    @pytest.mark.asyncio
    async def test_items_removed_from_inventory(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "You use the rusty key to open the gate. The key breaks.",
            "choices": ["Go through the gate"],
            "health_delta": 0,
            "new_items": [],
            "removed_items": ["rusty key"],
            "is_complete": False,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        state = game_engine.get_game(create_resp.game_id)
        assert "rusty key" in state.inventory

        response = await game_engine.process_action(create_resp.game_id, "Use key on gate")
        assert "rusty key" not in response.inventory

    @pytest.mark.asyncio
    async def test_removing_nonexistent_item_is_safe(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Nothing happens.",
            "choices": ["Try again"],
            "health_delta": 0,
            "new_items": [],
            "removed_items": ["nonexistent_item"],
            "is_complete": False,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Use phantom item")
        assert isinstance(response, GameResponse)


class TestGameCompletion:
    @pytest.mark.asyncio
    async def test_game_marked_complete(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "You have defeated the dragon and saved the kingdom!",
            "choices": [],
            "health_delta": 0,
            "new_items": ["dragon trophy"],
            "removed_items": [],
            "is_complete": True,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        response = await game_engine.process_action(create_resp.game_id, "Slay the dragon")
        assert response.is_complete is True

    @pytest.mark.asyncio
    async def test_completed_game_state_is_stored(self, game_engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Victory!",
            "choices": [],
            "health_delta": 0,
            "new_items": [],
            "removed_items": [],
            "is_complete": True,
        }
        create_resp = await game_engine.create_game("Hero", "fantasy")
        await game_engine.process_action(create_resp.game_id, "Win the game")
        state = game_engine.get_game(create_resp.game_id)
        assert state.is_complete is True


class TestInvalidGameId:
    def test_get_game_invalid_id_returns_none(self, game_engine):
        result = game_engine.get_game("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_action_invalid_id_raises_error(self, game_engine):
        with pytest.raises(GameNotFoundError):
            await game_engine.process_action("nonexistent-id", "Do something")
