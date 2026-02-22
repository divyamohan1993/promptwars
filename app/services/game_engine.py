"""Core game engine managing state, Gemini interaction, and persistence.

Orchestrates the gameplay loop: receives player actions, delegates to
the Gemini AI service for narrative generation, updates the internal
game state (health, inventory, map, achievements), and optionally
persists to Cloud Firestore.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from app.models.schemas import Adventure, GameResponse, GameState, MapNode, SceneVisual

if TYPE_CHECKING:
    from app.services.firestore_service import FirestoreService
    from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

ACHIEVEMENT_XP = 25
TURN_XP = 10

# Maximum number of in-memory game sessions before oldest are evicted.
_MAX_CACHED_GAMES = 5_000


class GameEngine:
    """Central game-loop controller backed by Gemini AI and Firestore."""

    def __init__(
        self,
        gemini_service: GeminiService | None = None,
        firestore_service: FirestoreService | None = None,
    ) -> None:
        self._games: dict[str, GameState] = {}
        if gemini_service is None:
            from app.services.gemini_service import GeminiService
            gemini_service = GeminiService()
        self._gemini = gemini_service
        self._firestore = firestore_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_game(
        self,
        player_name: str,
        adventure: str | Adventure,
        *,
        language: str = "en",
    ) -> GameResponse:
        """Create a new game and generate the opening narrative via Gemini."""
        game_id = str(uuid.uuid4())
        adventure_str = adventure.value if isinstance(adventure, Adventure) else str(adventure)

        ai_response = await self._gemini.generate_opening(adventure_str, player_name)

        state = GameState(
            game_id=game_id,
            player_name=player_name,
            adventure=adventure,
            health=self._clamp_health(100 + ai_response.get("health_delta", 0)),
            inventory=ai_response.get("new_items", []),
            turn_count=1,
            narrative=ai_response["narrative"],
            choices=ai_response["choices"],
            choice_icons=ai_response.get("choice_icons", []),
            is_alive=True,
            is_complete=False,
            story_history=[
                {"turn": 1, "narrative": ai_response["narrative"], "action": None}
            ],
            scene_visual=self._build_scene_visual(ai_response.get("scene_visual", {})),
            xp=TURN_XP,
            language=language,
        )

        self._update_map(state, ai_response.get("map_update", {}))
        new_achievements = self._check_achievements(state)
        state.xp += len(new_achievements) * ACHIEVEMENT_XP

        await self._save_state(game_id, state)
        logger.info("Created game %s for player '%s' (%s)", game_id, player_name, adventure_str)
        return self.to_response(state)

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

        # Update inventory — order-preserving, no duplicates.
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
        state.choice_icons = (
            ai_response.get("choice_icons", []) if is_alive and not is_complete else []
        )
        state.is_alive = is_alive
        state.is_complete = is_complete
        state.story_history.append(
            {"turn": new_turn, "narrative": ai_response["narrative"], "action": action}
        )
        state.scene_visual = self._build_scene_visual(ai_response.get("scene_visual", {}))
        state.xp += TURN_XP

        self._update_map(state, ai_response.get("map_update", {}))
        new_achievements = self._check_achievements(state)
        state.xp += len(new_achievements) * ACHIEVEMENT_XP

        await self._save_state(game_id, state)
        logger.info("Game %s turn %d (health=%d, alive=%s)", game_id, new_turn, new_health, is_alive)
        return self.to_response(state)

    async def get_game(self, game_id: str) -> GameState | None:
        """Retrieve game state by ID, checking Firestore if not in memory."""
        return await self._load_state(game_id)

    # ------------------------------------------------------------------
    # Map generation
    # ------------------------------------------------------------------

    @staticmethod
    def _update_map(state: GameState, map_update: dict) -> None:
        """Add a new location node to the map if provided."""
        if not map_update or not map_update.get("new_location"):
            return
        node_id = f"node_{len(state.map_nodes)}"
        node = MapNode(
            node_id=node_id,
            name=str(map_update["new_location"])[:40],
            visited=True,
            icon=map_update.get("location_icon", "location"),
            connected_to=[state.current_node_id] if state.current_node_id else [],
            x=len(state.map_nodes) % 5,
            y=len(state.map_nodes) // 5,
        )
        # Bi-directional connection.
        if state.current_node_id:
            for existing in state.map_nodes:
                if existing.node_id == state.current_node_id:
                    if node_id not in existing.connected_to:
                        existing.connected_to.append(node_id)
        state.map_nodes.append(node)
        state.current_node_id = node_id

    # ------------------------------------------------------------------
    # Achievements
    # ------------------------------------------------------------------

    @staticmethod
    def _check_achievements(state: GameState) -> list[str]:
        """Check and award achievements based on game state."""
        new_achievements: list[str] = []
        triggers = {
            "First Steps": state.turn_count == 1,
            "Explorer": len(state.map_nodes) >= 5,
            "Collector": len(state.inventory) >= 3,
            "Survivor": state.turn_count >= 10,
            "Brave Heart": state.health <= 30 and state.is_alive,
            "Full Health": state.health == 100 and state.turn_count > 1,
        }
        for name, condition in triggers.items():
            if condition and name not in state.achievements:
                state.achievements.append(name)
                new_achievements.append(name)
        return new_achievements

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_scene_visual(data: dict) -> SceneVisual:
        """Build a SceneVisual from AI response data with safe defaults."""
        if not data:
            return SceneVisual()
        return SceneVisual(
            scene_type=str(data.get("scene_type", "exploration")),
            mood=str(data.get("mood", "neutral")),
            location_name=str(data.get("location_name", "")),
            location_icon=str(data.get("location_icon", "")),
            npc_name=data.get("npc_name"),
            npc_type=data.get("npc_type"),
            item_found=data.get("item_found"),
            weather=str(data.get("weather", "clear")),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_state(self, game_id: str, state: GameState) -> None:
        """Save to in-memory cache and optionally to Firestore."""
        self._games[game_id] = state
        # Evict oldest games if the cache grows too large.
        if len(self._games) > _MAX_CACHED_GAMES:
            oldest_key = next(iter(self._games))
            del self._games[oldest_key]
        if self._firestore:
            try:
                await self._firestore.save_game(game_id, state.model_dump(mode="json"))
            except Exception as e:
                logger.warning("Firestore save failed for %s: %s", game_id, e)

    async def _load_state(self, game_id: str) -> GameState | None:
        """Load from memory first, then fall back to Firestore."""
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
    def to_response(state: GameState) -> GameResponse:
        """Convert internal GameState to the public GameResponse."""
        return GameResponse(
            game_id=state.game_id,
            narrative=state.narrative,
            choices=state.choices,
            choice_icons=state.choice_icons,
            health=state.health,
            inventory=state.inventory,
            turn_count=state.turn_count,
            is_alive=state.is_alive,
            is_complete=state.is_complete,
            scene_visual=state.scene_visual,
            map_nodes=state.map_nodes,
            current_node_id=state.current_node_id,
            achievements=state.achievements,
            xp=state.xp,
        )


class GameNotFoundError(Exception):
    """Raised when a game ID is not found in memory or Firestore."""

    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        super().__init__(f"Game not found: {game_id}")


class GameOverError(Exception):
    """Raised when an action is attempted on a completed / dead game."""

    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        super().__init__(f"Game is already over: {game_id}")
