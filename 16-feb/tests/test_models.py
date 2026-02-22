import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ActionRequest, Adventure, GameStartRequest, GameState, GameResponse,
    ImageRequest, ImageResponse, MapNode, SceneVisual,
    TTSRequest, TTSResponse, TranslateRequest, TranslateResponse,
)


class TestAdventure:
    def test_all_adventures_valid(self):
        for adv in Adventure:
            req = GameStartRequest(player_name="Test", adventure=adv.value)
            assert req.adventure == adv

    def test_invalid_adventure_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="Test", adventure="romance")

    def test_adventure_values(self):
        assert Adventure.HAWKINS_INVESTIGATION.value == "hawkins-investigation"
        assert Adventure.UPSIDE_DOWN.value == "upside-down"
        assert Adventure.HAWKINS_LAB.value == "hawkins-lab"
        assert Adventure.DND_CAMPAIGN.value == "dnd-campaign"


class TestGameStartRequest:
    def test_valid_request(self):
        req = GameStartRequest(player_name="Eleven", adventure="upside-down")
        assert req.player_name == "Eleven"
        assert req.adventure == Adventure.UPSIDE_DOWN

    def test_default_language(self):
        req = GameStartRequest(player_name="Mike", adventure="hawkins-investigation")
        assert req.language == "en"

    def test_custom_language(self):
        req = GameStartRequest(player_name="Mike", adventure="hawkins-investigation", language="es")
        assert req.language == "es"

    def test_empty_player_name_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="", adventure="upside-down")

    def test_player_name_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="A" * 51, adventure="upside-down")

    def test_missing_fields_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest()


class TestActionRequest:
    def test_valid_action(self):
        req = ActionRequest(game_id="abc-123", action="Open the door")
        assert req.game_id == "abc-123"
        assert req.action == "Open the door"

    def test_empty_action_raises_error(self):
        with pytest.raises(ValidationError):
            ActionRequest(game_id="abc", action="")

    def test_action_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            ActionRequest(game_id="abc", action="A" * 501)

    def test_empty_game_id_raises_error(self):
        with pytest.raises(ValidationError):
            ActionRequest(game_id="", action="test")

    def test_action_stripped(self):
        req = ActionRequest(game_id="abc", action="  hello  ")
        assert req.action == "hello"

    def test_control_chars_rejected(self):
        with pytest.raises(ValidationError):
            ActionRequest(game_id="abc", action="hello\x00world")


class TestGameStartRequestSanitisation:
    def test_player_name_stripped(self):
        req = GameStartRequest(player_name="  Hero  ", adventure="upside-down")
        assert req.player_name == "Hero"

    def test_control_chars_in_name_rejected(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="Hero\x00", adventure="upside-down")


class TestSceneVisual:
    def test_defaults(self):
        sv = SceneVisual()
        assert sv.scene_type == "exploration"
        assert sv.mood == "neutral"
        assert sv.location_name == ""
        assert sv.npc_name is None
        assert sv.weather == "clear"

    def test_custom_values(self):
        sv = SceneVisual(
            scene_type="combat", mood="tense",
            location_name="Hawkins Lab", location_icon="lab",
            npc_name="Demogorgon", npc_type="monster",
            item_found="flashlight", weather="stormy",
        )
        assert sv.scene_type == "combat"
        assert sv.npc_name == "Demogorgon"
        assert sv.item_found == "flashlight"


class TestMapNode:
    def test_defaults(self):
        node = MapNode(node_id="n1", name="Forest")
        assert node.visited is False
        assert node.connected_to == []
        assert node.icon == "location"
        assert node.x == 0
        assert node.y == 0

    def test_connections(self):
        node = MapNode(node_id="n2", name="Lab", connected_to=["n1"], visited=True, x=1, y=0)
        assert "n1" in node.connected_to
        assert node.visited is True


class TestTranslateRequest:
    def test_valid_request(self):
        req = TranslateRequest(text="Hello world", target_language="es")
        assert req.text == "Hello world"
        assert req.target_language == "es"

    def test_empty_text_raises_error(self):
        with pytest.raises(ValidationError):
            TranslateRequest(text="", target_language="es")

    def test_text_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            TranslateRequest(text="A" * 5001, target_language="es")


class TestTranslateResponse:
    def test_valid_response(self):
        resp = TranslateResponse(translated_text="Hola mundo", source_language="en")
        assert resp.translated_text == "Hola mundo"


class TestImageRequest:
    def test_valid_request(self):
        req = ImageRequest(prompt="A dark forest with glowing mushrooms")
        assert req.prompt == "A dark forest with glowing mushrooms"

    def test_empty_prompt_raises_error(self):
        with pytest.raises(ValidationError):
            ImageRequest(prompt="")

    def test_prompt_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            ImageRequest(prompt="A" * 501)


class TestImageResponse:
    def test_valid_response(self):
        resp = ImageResponse(image_url="data:image/png;base64,abc")
        assert resp.image_url == "data:image/png;base64,abc"


class TestTTSRequest:
    def test_valid_tts_request(self):
        req = TTSRequest(text="Hello world")
        assert req.text == "Hello world"

    def test_empty_text_raises_error(self):
        with pytest.raises(ValidationError):
            TTSRequest(text="")

    def test_text_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            TTSRequest(text="A" * 2001)


class TestTTSResponse:
    def test_valid_response(self):
        resp = TTSResponse(audio="base64data")
        assert resp.audio == "base64data"


class TestGameState:
    def test_defaults(self):
        state = GameState(game_id="id", player_name="Hero", adventure="hawkins-investigation")
        assert state.health == 100
        assert state.inventory == []
        assert state.turn_count == 0
        assert state.is_alive is True
        assert state.is_complete is False
        assert state.xp == 0
        assert state.achievements == []
        assert state.map_nodes == []
        assert state.current_node_id == ""
        assert state.language == "en"
        assert isinstance(state.scene_visual, SceneVisual)
        assert state.choice_icons == []

    def test_custom_values(self):
        state = GameState(
            game_id="id", player_name="Hero", adventure="upside-down",
            health=75, inventory=["flashlight", "walkie-talkie"], turn_count=5,
            narrative="Spooky.", choices=["Go", "Stay"],
            xp=50, achievements=["First Steps"],
        )
        assert state.health == 75
        assert len(state.inventory) == 2
        assert state.xp == 50
        assert "First Steps" in state.achievements


class TestGameResponse:
    def test_serialization(self):
        resp = GameResponse(
            game_id="id", narrative="Demogorgon!", choices=["Fight", "Flee", "Hide"],
            choice_icons=["sword", "run", "hide"],
            health=85, inventory=["flashlight"], turn_count=3,
            is_alive=True, is_complete=False,
            scene_visual=SceneVisual(mood="tense"),
            map_nodes=[MapNode(node_id="n1", name="Forest")],
            current_node_id="n1", achievements=["First Steps"], xp=35,
        )
        data = resp.model_dump()
        assert data["game_id"] == "id"
        assert len(data["choices"]) == 3
        assert len(data["choice_icons"]) == 3
        assert data["xp"] == 35
        assert data["scene_visual"]["mood"] == "tense"
        assert len(data["map_nodes"]) == 1

    def test_json_serialization(self):
        resp = GameResponse(
            game_id="id", narrative="Victory!", choices=[],
            choice_icons=[],
            health=100, inventory=[], turn_count=10,
            is_alive=True, is_complete=True,
            scene_visual=SceneVisual(),
            map_nodes=[], current_node_id="", achievements=[], xp=100,
        )
        json_str = resp.model_dump_json()
        assert "id" in json_str
        assert "scene_visual" in json_str
