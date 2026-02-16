import uuid

from app.models.schemas import GameResponse, GameState, Genre
from app.services.gemini_service import GeminiService


class GameEngine:
    def __init__(self, gemini_service: GeminiService | None = None) -> None:
        self.games: dict[str, GameState] = {}
        self.gemini = gemini_service or GeminiService()

    async def create_game(self, player_name: str, genre: str | Genre) -> GameResponse:
        game_id = str(uuid.uuid4())
        genre_str = genre.value if isinstance(genre, Genre) else str(genre)

        ai_response = await self.gemini.generate_opening(genre_str, player_name)

        state = GameState(
            game_id=game_id,
            player_name=player_name,
            genre=genre,
            health=self._clamp_health(100 + ai_response.get("health_delta", 0)),
            inventory=ai_response.get("new_items", []),
            turn_count=1,
            narrative=ai_response["narrative"],
            choices=ai_response["choices"],
            is_alive=True,
            is_complete=False,
            story_history=[
                {
                    "turn": 1,
                    "narrative": ai_response["narrative"],
                    "action": None,
                }
            ],
        )

        self.games[game_id] = state
        return self._to_response(state)

    async def process_action(self, game_id: str, action: str) -> GameResponse:
        state = self.games.get(game_id)
        if state is None:
            raise GameNotFoundError(game_id)

        if not state.is_alive or state.is_complete:
            raise GameOverError(game_id)

        ai_response = await self.gemini.generate_response(
            state.model_dump(), action
        )

        new_health = self._clamp_health(state.health + ai_response.get("health_delta", 0))
        is_alive = new_health > 0
        is_complete = ai_response.get("is_complete", False) or not is_alive

        inventory = list(state.inventory)
        for item in ai_response.get("new_items", []):
            if item not in inventory:
                inventory.append(item)
        for item in ai_response.get("removed_items", []):
            if item in inventory:
                inventory.remove(item)

        new_turn = state.turn_count + 1

        state.health = new_health
        state.inventory = inventory
        state.turn_count = new_turn
        state.narrative = ai_response["narrative"]
        state.choices = ai_response["choices"] if is_alive and not is_complete else []
        state.is_alive = is_alive
        state.is_complete = is_complete
        state.story_history.append(
            {
                "turn": new_turn,
                "narrative": ai_response["narrative"],
                "action": action,
            }
        )

        self.games[game_id] = state
        return self._to_response(state)

    def get_game(self, game_id: str) -> GameState | None:
        return self.games.get(game_id)

    @staticmethod
    def _clamp_health(value: int) -> int:
        return max(0, min(100, value))

    @staticmethod
    def _to_response(state: GameState) -> GameResponse:
        return GameResponse(
            game_id=state.game_id,
            narrative=state.narrative,
            choices=state.choices,
            health=state.health,
            inventory=state.inventory,
            turn_count=state.turn_count,
            is_alive=state.is_alive,
            is_complete=state.is_complete,
        )


class GameNotFoundError(Exception):
    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        super().__init__(f"Game not found: {game_id}")


class GameOverError(Exception):
    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        super().__init__(f"Game is already over: {game_id}")
