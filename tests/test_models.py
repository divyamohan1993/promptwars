import pytest
from pydantic import ValidationError

from app.models.schemas import GameStartRequest, ActionRequest, GameState, GameResponse


class TestGameStartRequest:
    """Tests for GameStartRequest validation."""

    def test_valid_fantasy_genre(self):
        request = GameStartRequest(player_name="Aldric", genre="fantasy")
        assert request.player_name == "Aldric"
        assert request.genre == "fantasy"

    def test_valid_scifi_genre(self):
        request = GameStartRequest(player_name="Nova", genre="sci-fi")
        assert request.genre == "sci-fi"

    def test_valid_mystery_genre(self):
        request = GameStartRequest(player_name="Holmes", genre="mystery")
        assert request.genre == "mystery"

    def test_valid_horror_genre(self):
        request = GameStartRequest(player_name="Ash", genre="horror")
        assert request.genre == "horror"

    def test_valid_pirate_genre(self):
        request = GameStartRequest(player_name="Blackbeard", genre="pirate")
        assert request.genre == "pirate"

    def test_invalid_genre_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="Test", genre="romance")

    def test_empty_player_name_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest(player_name="", genre="fantasy")

    def test_missing_fields_raises_error(self):
        with pytest.raises(ValidationError):
            GameStartRequest()


class TestActionRequest:
    """Tests for ActionRequest validation."""

    def test_valid_action_request(self):
        request = ActionRequest(game_id="abc-123", action="Open the door")
        assert request.game_id == "abc-123"
        assert request.action == "Open the door"

    def test_missing_game_id_raises_error(self):
        with pytest.raises(ValidationError):
            ActionRequest(action="Open the door")

    def test_missing_action_raises_error(self):
        with pytest.raises(ValidationError):
            ActionRequest(game_id="abc-123")


class TestGameState:
    """Tests for GameState defaults."""

    def test_defaults(self):
        state = GameState(game_id="test-id", player_name="Hero", genre="fantasy")
        assert state.game_id == "test-id"
        assert state.player_name == "Hero"
        assert state.genre == "fantasy"
        assert state.health == 100
        assert state.inventory == []
        assert state.turn_count == 0
        assert state.narrative == ""
        assert state.choices == []
        assert state.is_alive is True
        assert state.is_complete is False
        assert state.story_history == []

    def test_custom_values(self):
        state = GameState(
            game_id="test-id",
            player_name="Hero",
            genre="sci-fi",
            health=75,
            inventory=["laser gun", "medkit"],
            turn_count=5,
            narrative="You are on a spaceship.",
            choices=["Go left", "Go right"],
            is_alive=True,
            is_complete=False,
            story_history=[{"turn": 1, "action": "look around"}],
        )
        assert state.health == 75
        assert len(state.inventory) == 2
        assert state.turn_count == 5
        assert state.narrative == "You are on a spaceship."
        assert len(state.choices) == 2
        assert len(state.story_history) == 1


class TestGameResponse:
    """Tests for GameResponse serialization."""

    def test_serialization(self):
        response = GameResponse(
            game_id="resp-id",
            narrative="A dragon appears!",
            choices=["Fight", "Flee", "Negotiate"],
            health=85,
            inventory=["sword", "shield"],
            turn_count=3,
            is_alive=True,
            is_complete=False,
        )
        data = response.model_dump()
        assert data["game_id"] == "resp-id"
        assert data["narrative"] == "A dragon appears!"
        assert len(data["choices"]) == 3
        assert data["health"] == 85
        assert data["inventory"] == ["sword", "shield"]
        assert data["turn_count"] == 3
        assert data["is_alive"] is True
        assert data["is_complete"] is False

    def test_json_serialization(self):
        response = GameResponse(
            game_id="json-id",
            narrative="You win!",
            choices=[],
            health=100,
            inventory=[],
            turn_count=10,
            is_alive=True,
            is_complete=True,
        )
        json_str = response.model_dump_json()
        assert "json-id" in json_str
        assert "You win!" in json_str
        assert '"is_complete":true' in json_str or '"is_complete": true' in json_str
