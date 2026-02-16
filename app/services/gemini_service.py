"""Google Gemini AI integration for dynamic story generation."""

import json
import logging
from typing import Any

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert dungeon master and interactive fiction storyteller for a text adventure game called QuestForge. You craft vivid, immersive narratives that respond dynamically to player choices.

RULES:
- Write in second person ("You step into the dark corridor...")
- Keep each narrative segment to 2-4 paragraphs (concise but atmospheric)
- Always provide exactly 3 or 4 distinct, meaningful choices for the player
- Choices should have real consequences and vary in risk/reward
- Track logical story continuity based on the full story history
- Health changes should make narrative sense (combat deals -10 to -25, traps -5 to -15, healing +10 to +20)
- Only set is_complete to true when the story reaches a natural conclusion (victory, escape, or death)
- Items gained or lost must be narratively justified
- If the player's health would reach 0, narrate their demise and set is_complete to true
- Maintain the tone appropriate to the genre throughout

You MUST respond with valid JSON in exactly this format:
{
  "narrative": "The story text describing what happens...",
  "choices": ["Choice 1", "Choice 2", "Choice 3"],
  "health_delta": 0,
  "new_items": [],
  "removed_items": [],
  "is_complete": false
}

health_delta: integer, 0 for no change, negative for damage, positive for healing (range -25 to +20)
new_items: list of item name strings the player acquires this turn
removed_items: list of item name strings the player loses or uses this turn
is_complete: boolean, true only when the adventure reaches a definitive ending"""

GENRE_THEMES = {
    "fantasy": "a high-fantasy realm with magic, dragons, ancient ruins, and enchanted artifacts",
    "sci-fi": "a far-future space odyssey with alien civilizations, advanced technology, and cosmic mysteries",
    "mystery": "a noir-tinged detective story with shadowy suspects, hidden clues, and dangerous secrets",
    "horror": "a spine-chilling supernatural horror with creeping dread, dark forces, and desperate survival",
    "pirate": "a swashbuckling pirate adventure on the high seas with treasure maps, rival crews, and legendary plunder",
}


class GeminiService:
    def __init__(self) -> None:
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.9,
            ),
        )

    async def generate_opening(self, genre: str, player_name: str) -> dict[str, Any]:
        """Generate the opening narrative for a new adventure."""
        theme = GENRE_THEMES.get(genre, GENRE_THEMES["fantasy"])
        prompt = (
            f"Begin a new {genre} text adventure set in {theme}. "
            f"The player's name is {player_name}. "
            f"Create an exciting opening scene that establishes the setting, "
            f"introduces a compelling hook, and gives the player their first meaningful choice. "
            f"The player starts with full health and no items (though you may give them a starting item if it fits the narrative)."
        )
        return await self._generate(prompt)

    async def generate_response(self, game_state: dict, player_action: str) -> dict[str, Any]:
        """Generate the next narrative based on current state and player action."""
        history_summary = self._build_history_context(game_state)
        prompt = (
            f"Continue the {game_state['genre']} adventure for player {game_state['player_name']}.\n\n"
            f"CURRENT STATE:\n"
            f"- Health: {game_state['health']}/100\n"
            f"- Inventory: {', '.join(game_state['inventory']) or 'empty'}\n"
            f"- Turn: {game_state['turn_count']}\n\n"
            f"STORY SO FAR:\n{history_summary}\n\n"
            f"PLAYER ACTION: {player_action}\n\n"
            f"Narrate what happens next based on the player's action. "
            f"Make the consequences feel natural and meaningful."
        )
        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> dict[str, Any]:
        try:
            response = await self.model.generate_content_async(prompt)
            return self._parse_response(response.text)
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            return self._fallback_response()

    def _parse_response(self, text: str) -> dict[str, Any]:
        try:
            data = json.loads(text)
            return {
                "narrative": str(data.get("narrative", "")),
                "choices": [str(c) for c in data.get("choices", [])],
                "health_delta": int(data.get("health_delta", 0)),
                "new_items": [str(i) for i in data.get("new_items", [])],
                "removed_items": [str(i) for i in data.get("removed_items", [])],
                "is_complete": bool(data.get("is_complete", False)),
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Failed to parse Gemini response: %s", e)
            return self._fallback_response()

    def _build_history_context(self, game_state: dict) -> str:
        history = game_state.get("story_history", [])
        if not history:
            return "No previous events."
        recent = history[-6:]
        parts = []
        for entry in recent:
            parts.append(f"- {entry.get('narrative', '')[:200]}")
            if entry.get("action"):
                parts.append(f"  Player chose: {entry['action']}")
        return "\n".join(parts)

    @staticmethod
    def _fallback_response() -> dict[str, Any]:
        return {
            "narrative": (
                "A strange fog rolls in, obscuring your surroundings momentarily. "
                "As it clears, you find yourself at a crossroads. "
                "The adventure continues, but the path ahead is uncertain."
            ),
            "choices": [
                "Press forward cautiously",
                "Look around for clues",
                "Rest and gather your thoughts",
            ],
            "health_delta": 0,
            "new_items": [],
            "removed_items": [],
            "is_complete": False,
        }
