import pytest
from unittest.mock import AsyncMock

from app.models.schemas import GameResponse, GameState
from app.services.game_engine import GameEngine, GameNotFoundError, GameOverError
from app.services.gemini_service import GeminiService


@pytest.fixture
def mock_gemini_service():
    service = AsyncMock(spec=GeminiService)
    service.generate_opening.return_value = {
        "narrative": "You awaken in a dungeon.",
        "choices": ["Search", "Call for help", "Try door"],
        "choice_icons": ["magnifying-glass", "talk", "door"],
        "health_delta": 0,
        "new_items": ["rusty key"],
        "removed_items": [],
        "is_complete": False,
        "scene_visual": {
            "scene_type": "exploration",
            "mood": "mysterious",
            "location_name": "The Dungeon",
            "location_icon": "cave",
        },
        "map_update": {
            "new_location": "The Dungeon",
            "location_icon": "cave",
        },
    }
    service.generate_response.return_value = {
        "narrative": "You find a hidden passage.",
        "choices": ["Enter", "Keep searching", "Go back"],
        "choice_icons": ["door", "magnifying-glass", "run"],
        "health_delta": -5,
        "new_items": ["map"],
        "removed_items": [],
        "is_complete": False,
        "scene_visual": {
            "scene_type": "discovery",
            "mood": "exciting",
            "location_name": "Hidden Passage",
            "location_icon": "cave",
        },
        "map_update": {
            "new_location": "Hidden Passage",
            "location_icon": "cave",
        },
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
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert isinstance(resp, GameResponse)

    async def test_sets_initial_state(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert resp.health == 100
        assert resp.turn_count == 1
        assert resp.is_alive is True
        assert resp.is_complete is False

    async def test_includes_narrative_and_choices(self, engine):
        resp = await engine.create_game("Hero", "upside-down")
        assert resp.narrative == "You awaken in a dungeon."
        assert len(resp.choices) == 3

    async def test_includes_starting_items(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert "rusty key" in resp.inventory

    async def test_calls_gemini(self, engine, mock_gemini_service):
        await engine.create_game("Hero", "hawkins-investigation")
        mock_gemini_service.generate_opening.assert_called_once_with("hawkins-investigation", "Hero")

    async def test_stores_state(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        state = await engine.get_game(resp.game_id)
        assert isinstance(state, GameState)
        assert state.player_name == "Hero"

    async def test_saves_to_firestore(self, engine_with_firestore, mock_firestore):
        resp = await engine_with_firestore.create_game("Hero", "hawkins-investigation")
        mock_firestore.save_game.assert_called_once()
        call_args = mock_firestore.save_game.call_args
        assert call_args[0][0] == resp.game_id

    async def test_initial_xp(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert resp.xp >= 10

    async def test_initial_achievement_first_steps(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert "First Steps" in resp.achievements

    async def test_choice_icons_returned(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert len(resp.choice_icons) == 3

    async def test_scene_visual_returned(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert resp.scene_visual.scene_type == "exploration"
        assert resp.scene_visual.mood == "mysterious"


class TestProcessAction:
    async def test_updates_state(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Search")
        assert resp.turn_count == 2
        assert resp.narrative == "You find a hidden passage."

    async def test_applies_health_delta(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Search")
        assert resp.health == 95

    async def test_adds_items(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Search")
        assert "map" in resp.inventory
        assert "rusty key" in resp.inventory

    async def test_removes_items(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Key breaks.", "choices": ["Continue"],
            "choice_icons": ["door"],
            "health_delta": 0, "new_items": [], "removed_items": ["rusty key"],
            "is_complete": False,
            "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Use key")
        assert "rusty key" not in resp.inventory

    async def test_invalid_id_raises(self, engine):
        with pytest.raises(GameNotFoundError):
            await engine.process_action("nonexistent", "test")

    async def test_xp_increases_on_action(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        initial_xp = create.xp
        resp = await engine.process_action(create.game_id, "Search")
        assert resp.xp > initial_xp

    async def test_map_grows_on_action(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        initial_nodes = len(create.map_nodes)
        resp = await engine.process_action(create.game_id, "Search")
        assert len(resp.map_nodes) > initial_nodes


class TestMapGeneration:
    async def test_initial_map_node(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert len(resp.map_nodes) >= 1
        assert resp.current_node_id != ""

    async def test_map_nodes_have_names(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        for node in resp.map_nodes:
            assert node.name != ""

    async def test_map_connections(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        await engine.process_action(create.game_id, "Search")
        state = await engine.get_game(create.game_id)
        if len(state.map_nodes) >= 2:
            second_node = state.map_nodes[1]
            assert len(second_node.connected_to) >= 1

    async def test_no_map_update_when_empty(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Nothing happens.", "choices": ["Wait"],
            "choice_icons": ["hide"],
            "health_delta": 0, "new_items": [], "removed_items": [],
            "is_complete": False, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        initial_count = len(create.map_nodes)
        resp = await engine.process_action(create.game_id, "Wait")
        assert len(resp.map_nodes) == initial_count


class TestAchievements:
    async def test_first_steps_on_create(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert "First Steps" in resp.achievements

    async def test_collector_achievement(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Found items!", "choices": ["Continue"],
            "choice_icons": ["magnifying-glass"],
            "health_delta": 0, "new_items": ["item1", "item2"],
            "removed_items": [], "is_complete": False,
            "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Search")
        assert "Collector" in resp.achievements

    async def test_brave_heart_achievement(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Ouch!", "choices": ["Continue"],
            "choice_icons": ["shield"],
            "health_delta": -75, "new_items": [], "removed_items": [],
            "is_complete": False, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Fight")
        assert "Brave Heart" in resp.achievements

    async def test_achievement_awards_xp(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert resp.xp >= 35


class TestHealthClamping:
    async def test_floors_at_zero(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Crushed.", "choices": [],
            "choice_icons": [],
            "health_delta": -200, "new_items": [], "removed_items": [],
            "is_complete": False, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Walk into trap")
        assert resp.health == 0
        assert resp.is_alive is False
        assert resp.is_complete is True

    async def test_caps_at_100(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Healed.", "choices": ["Continue"],
            "choice_icons": ["potion"],
            "health_delta": 50, "new_items": [], "removed_items": [],
            "is_complete": False, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Heal")
        assert resp.health == 100


class TestGameCompletion:
    async def test_game_completes(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Victory!", "choices": [],
            "choice_icons": [],
            "health_delta": 0, "new_items": [], "removed_items": [],
            "is_complete": True, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Win")
        assert resp.is_complete is True
        assert resp.choices == []

    async def test_completed_game_rejects_actions(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Victory!", "choices": [],
            "choice_icons": [],
            "health_delta": 0, "new_items": [], "removed_items": [],
            "is_complete": True, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        await engine.process_action(create.game_id, "Win")
        with pytest.raises(GameOverError):
            await engine.process_action(create.game_id, "Try again")


class TestSceneVisual:
    async def test_scene_visual_from_ai(self, engine):
        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert resp.scene_visual.scene_type == "exploration"
        assert resp.scene_visual.location_name == "The Dungeon"

    async def test_empty_scene_visual_defaults(self, engine, mock_gemini_service):
        mock_gemini_service.generate_response.return_value = {
            "narrative": "Simple.", "choices": ["Go"],
            "choice_icons": ["door"],
            "health_delta": 0, "new_items": [], "removed_items": [],
            "is_complete": False, "scene_visual": {}, "map_update": {},
        }
        create = await engine.create_game("Hero", "hawkins-investigation")
        resp = await engine.process_action(create.game_id, "Go")
        assert resp.scene_visual.scene_type == "exploration"
        assert resp.scene_visual.mood == "neutral"


class TestGetGame:
    async def test_returns_none_for_missing(self, engine):
        result = await engine.get_game("nonexistent")
        assert result is None

    async def test_returns_state(self, engine):
        create = await engine.create_game("Hero", "hawkins-investigation")
        state = await engine.get_game(create.game_id)
        assert state is not None
        assert state.player_name == "Hero"


class TestFirestoreIntegration:
    async def test_saves_and_loads_from_firestore(self, engine_with_firestore, mock_firestore):
        resp = await engine_with_firestore.create_game("Hero", "hawkins-investigation")
        mock_firestore.save_game.assert_called_once()
        call_args = mock_firestore.save_game.call_args
        assert call_args[0][0] == resp.game_id

    async def test_firestore_failure_graceful(self, mock_gemini_service):
        failing_firestore = AsyncMock()
        failing_firestore.save_game = AsyncMock(side_effect=Exception("Firestore down"))
        failing_firestore.load_game = AsyncMock(return_value=None)

        engine = GameEngine(
            gemini_service=mock_gemini_service,
            firestore_service=failing_firestore,
        )

        resp = await engine.create_game("Hero", "hawkins-investigation")
        assert resp.game_id is not None
        assert resp.health == 100

        state = await engine.get_game(resp.game_id)
        assert state is not None
        assert state.player_name == "Hero"
