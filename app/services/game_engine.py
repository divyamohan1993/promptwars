"""Core game engine managing state, Gemini interaction, and persistence."""

import logging
import uuid

from app.models.schemas import GameResponse, GameState, Genre
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class GameEngine:
    def __init__(
        self,
        gemini_service: GeminiService | None = None,
        firestore_service=None,
    ) -> None:
        self._games: dict[str, GameState] = {}
        self._gemini = gemini_service or GeminiService()
        self._firestore = firestore_service

    async def create_game(self, player_name: str, genre: str | Genre) -> GameResponse:
        """Create a new game and generate the opening narrative via Gemini."""
        game_id = str(uuid.uuid4())
        genre_str = genre.value if isinstance(genre, Genre) else str(genre)

        ai_response = await self._gemini.generate_opening(genre_str, player_name)

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
                {"turn": 1, "narrative": ai_response["narrative"], "action": None}
            ],
        )

        await self._save_state(game_id, state)
        logger.info("Created game %s for player '%s' (%s)", game_id, player_name, genre_str)
        return self._to_response(state)

    async def process_action(self, game_id: str, action: str) -> GameResponse:
        """Process a player action, update state, and generate the next narrative."""
        state = await self._load_state(game_id)
        if state is None:
            raise GameNotFoundError(game_id)

        if not state.is_alive or state.is_complete:
            raise GameOverError(game_id)

        ai_response = await self._gemini.generate_response(state.model_dump(), action)

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
            {"turn": new_turn, "narrative": ai_response["narrative"], "action": action}
        )

        await self._save_state(game_id, state)
        logger.info("Game %s turn %d (health=%d, alive=%s)", game_id, new_turn, new_health, is_alive)
        return self._to_response(state)

    async def get_game(self, game_id: str) -> GameState | None:
        """Retrieve game state by ID, checking Firestore if not in memory."""
        return await self._load_state(game_id)

    async def _save_state(self, game_id: str, state: GameState) -> None:
        self._games[game_id] = state
        if self._firestore:
            try:
                await self._firestore.save_game(game_id, state.model_dump(mode="json"))
            except Exception as e:
                logger.warning("Firestore save failed for %s: %s", game_id, e)

    async def _load_state(self, game_id: str) -> GameState | None:
        if game_id in self._games:
            return self._games[game_id]
        if self._firestore:
            try:
                data = await self._firestore.load_game(game_id)
                if data:
                    state = GameState(**data)
                    self._games[game_id] = state
                    return state
            except Exception as e:
                logger.warning("Firestore load failed for %s: %s", game_id, e)
        return None

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
