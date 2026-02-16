import pytest
from pydantic import ValidationError

from app.models.schemas import (
    GameStartRequest, ActionRequest, GameState, GameResponse,
    TTSRequest, TTSResponse, Genre,
)


class TestGameStartRequest:
    def test_valid_fantasy_genre(self):
        req = GameStartRequest(player_name="Aldric", genre="fantasy")
        assert req.player_name == "Aldric"
        assert req.genre == Genre.FANTASY

    def test_valid_scifi_genre(self):
        req = GameStartRequest(player_name="Nova", genre="sci-fi")
        assert req.genre == Genre.SCI_FI

    def test_all_genres_valid(self):
        for genre in Genre:
            req = GameStartRequest(player_name="Test", genre=genre.value)
            assert req.genre == genre

    def test_invalid_genre_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="Test", genre="romance")

    def test_empty_player_name_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="", genre="fantasy")

    def test_player_name_too_long_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="A" * 51, genre="fantasy")

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
        state = GameState(game_id="id", player_name="Hero", genre="fantasy")
        assert state.health == 100
        assert state.inventory == []
        assert state.turn_count == 0
        assert state.is_alive is True
        assert state.is_complete is False

    def test_custom_values(self):
        state = GameState(
            game_id="id", player_name="Hero", genre="sci-fi",
            health=75, inventory=["laser", "medkit"], turn_count=5,
            narrative="Space.", choices=["Go", "Stay"],
        )
        assert state.health == 75
        assert len(state.inventory) == 2


class TestGameResponse:
    def test_serialization(self):
        resp = GameResponse(
            game_id="id", narrative="Dragon!", choices=["Fight", "Flee"],
            health=85, inventory=["sword"], turn_count=3,
            is_alive=True, is_complete=False,
        )
        data = resp.model_dump()
        assert data["game_id"] == "id"
        assert len(data["choices"]) == 2

    def test_json_serialization(self):
        resp = GameResponse(
            game_id="id", narrative="Win!", choices=[],
            health=100, inventory=[], turn_count=10,
            is_alive=True, is_complete=True,
        )
        json_str = resp.model_dump_json()
        assert "id" in json_str
