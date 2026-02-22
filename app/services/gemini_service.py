"""Google Gemini AI integration for dynamic story generation.

Uses the ``gemini-3-flash-preview`` model with structured JSON output to drive
the narrative engine.  All responses are parsed and validated before being
returned to the game engine, with a safe fallback when the API is
unreachable or returns malformed data.
"""

import json
import logging
from typing import Any

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

# Maximum health swing per turn — clamps Gemini output to prevent
# one-hit kills that aren't story-driven.
_MAX_HEALTH_DELTA = 20

SYSTEM_PROMPT = """You are the Dungeon Master for QuestForge: The Upside Down, an interactive adventure game
inspired by Stranger Things set in the 1980s. The game is designed for young children (ages 4-8),
so the tone must be exciting but never truly scary -- spooky-fun, not terrifying. Think of the
show's sense of wonder, friendship, and bravery rather than its horror elements.

RULES:
- Write in second person ("You tiptoe through the dark corridor...")
- Keep narratives SHORT: 1-2 paragraphs maximum (children have shorter attention spans)
- Use simple vocabulary suitable for young children being read to
- Always provide exactly 3 distinct choices for the player
- Each choice should be SHORT (under 10 words) and clear
- Choices should be clearly different in approach (brave, careful, clever)
- Health changes must make narrative sense (minor bumps -5 to -10, helping others +5 to +15)
- NEVER let the narrative be genuinely frightening -- keep it fun and empowering
- Items gained or lost must be narratively justified
- The player is always the HERO, never helpless
- Set is_complete to true only for a natural happy ending or gentle conclusion after 8+ turns

You MUST respond with valid JSON in exactly this format:
{
  "narrative": "Short, vivid story text...",
  "choices": ["Brave choice", "Careful choice", "Clever choice"],
  "choice_icons": ["sword", "shield", "magnifying-glass"],
  "health_delta": 0,
  "new_items": [],
  "removed_items": [],
  "is_complete": false,
  "scene_visual": {
    "scene_type": "exploration",
    "mood": "mysterious",
    "location_name": "Hawkins Forest",
    "location_icon": "forest",
    "npc_name": null,
    "npc_type": null,
    "item_found": null,
    "weather": "clear"
  },
  "map_update": {
    "new_location": "Hawkins Forest",
    "location_icon": "forest",
    "connects_to_previous": true
  }
}

scene_type options: exploration, combat, discovery, puzzle, dialogue, escape
mood options: tense, cheerful, scary, mysterious, victorious, calm, exciting
location_icon options: forest, lab, school, house, cave, town, library, arcade, field, portal, bike-trail, basement
choice_icons options: sword, shield, magnifying-glass, flashlight, run, talk, key, bike, walkie-talkie, book, potion, friend, sneak, climb, door, puzzle, magic, hide

health_delta: integer, 0 for no change, negative for damage, positive for healing (range -15 to +15)
new_items: list of item name strings the player acquires this turn
removed_items: list of item name strings the player loses or uses this turn
is_complete: boolean, true only when the adventure reaches a definitive happy ending"""

ADVENTURE_THEMES: dict[str, str] = {
    "hawkins-investigation": (
        "a mysterious investigation in the small town of Hawkins, Indiana in the 1980s. "
        "Strange things are happening: flickering lights, mysterious sounds, and "
        "odd signals on walkie-talkies. You and your friends must investigate using bikes, "
        "flashlights, and courage. Think Stranger Things Season 1 but fun and child-safe."
    ),
    "upside-down": (
        "a spooky-fun adventure through the Upside Down, a mirror world covered in vines "
        "and floating glowing particles. It is dark and strange, but you are brave! You must find "
        "your way through while helping lost creatures and solving glowing puzzles. "
        "Everything glows with mysterious blue and red light."
    ),
    "hawkins-lab": (
        "an exciting escape from a mysterious laboratory full of blinking machines and long corridors. "
        "You have discovered you have special powers like telekinesis! Navigate through the lab, "
        "solve puzzles with your mind powers, and help your friends escape. "
        "Think Eleven's story but empowering and fun."
    ),
    "dnd-campaign": (
        "an epic Dungeons & Dragons campaign being played by friends in a cozy basement. "
        "You are the brave adventurer in the story! Fight pretend monsters, find treasure, cast "
        "magic spells, and be the hero. Roll dice for exciting moments! "
        "Think of Mike, Dustin, Lucas, and Will playing D&D in the basement."
    ),
}


class GeminiService:
    """Wraps the Google Generative AI SDK for structured story generation."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.9,
            ),
        )

    async def generate_opening(self, adventure: str, player_name: str) -> dict[str, Any]:
        """Generate the opening narrative for a new adventure."""
        theme = ADVENTURE_THEMES.get(adventure, ADVENTURE_THEMES["hawkins-investigation"])
        prompt = (
            f"Begin a new adventure set in {theme}. "
            f"The player's name is {player_name}. "
            f"Create an exciting opening scene that establishes the setting, "
            f"introduces a compelling hook, and gives the player their first meaningful choice. "
            f"The player starts with full health (100). Give them one fun starting item. "
            f"Remember: this is for young children, keep it fun and empowering!"
        )
        return await self._generate(prompt)

    async def generate_response(self, game_state: dict, player_action: str) -> dict[str, Any]:
        """Generate the next narrative based on current state and player action."""
        history_summary = self._build_history_context(game_state)
        # Truncate action to prevent prompt injection via very long inputs.
        safe_action = player_action[:500]
        prompt = (
            f"Continue the adventure for player {game_state['player_name']}.\n\n"
            f"CURRENT STATE:\n"
            f"- Health: {game_state['health']}/100\n"
            f"- Inventory: {', '.join(game_state['inventory']) or 'empty'}\n"
            f"- Turn: {game_state['turn_count']}\n\n"
            f"STORY SO FAR:\n{history_summary}\n\n"
            f"PLAYER ACTION: {safe_action}\n\n"
            f"Narrate what happens next based on the player's action. "
            f"Move to a NEW LOCATION (provide map_update with new_location). "
            f"Make the consequences feel natural and fun. Keep it child-friendly!"
        )
        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> dict[str, Any]:
        """Call the Gemini API and return a parsed response dict."""
        try:
            response = await self.model.generate_content_async(prompt)
            return self._parse_response(response.text)
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            return self._fallback_response()

    def _parse_response(self, text: str) -> dict[str, Any]:
        """Parse and validate the structured JSON returned by Gemini."""
        try:
            data = json.loads(text)
            # Clamp health_delta to a safe range.
            raw_delta = int(data.get("health_delta", 0))
            health_delta = max(-_MAX_HEALTH_DELTA, min(_MAX_HEALTH_DELTA, raw_delta))

            choices = [str(c) for c in data.get("choices", [])]
            choice_icons = [str(i) for i in data.get("choice_icons", [])]
            # Ensure icons list matches choices length.
            if len(choice_icons) < len(choices):
                choice_icons.extend(["flashlight"] * (len(choices) - len(choice_icons)))

            return {
                "narrative": str(data.get("narrative", "")),
                "choices": choices[:4],
                "choice_icons": choice_icons[:4],
                "health_delta": health_delta,
                "new_items": [str(i) for i in data.get("new_items", [])][:5],
                "removed_items": [str(i) for i in data.get("removed_items", [])][:5],
                "is_complete": bool(data.get("is_complete", False)),
                "scene_visual": data.get("scene_visual", {}),
                "map_update": data.get("map_update", {}),
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Failed to parse Gemini response: %s", e)
            return self._fallback_response()

    @staticmethod
    def _build_history_context(game_state: dict) -> str:
        """Build a condensed summary of recent story events for context."""
        history = game_state.get("story_history", [])
        if not history:
            return "No previous events."
        recent = history[-6:]
        parts: list[str] = []
        for entry in recent:
            parts.append(f"- {entry.get('narrative', '')[:200]}")
            if entry.get("action"):
                parts.append(f"  Player chose: {entry['action']}")
        return "\n".join(parts)

    @staticmethod
    def _fallback_response() -> dict[str, Any]:
        """Return a safe, generic response when Gemini is unavailable."""
        return {
            "narrative": (
                "The lights flicker around you and a strange breeze blows through. "
                "When things settle down, you find yourself at a crossroads. "
                "Three paths stretch out before you, each glowing with a different color."
            ),
            "choices": [
                "Follow the red glow bravely",
                "Sneak down the blue path",
                "Investigate the green light",
            ],
            "choice_icons": ["flashlight", "sneak", "magnifying-glass"],
            "health_delta": 0,
            "new_items": [],
            "removed_items": [],
            "is_complete": False,
            "scene_visual": {
                "scene_type": "exploration",
                "mood": "mysterious",
                "location_name": "The Crossroads",
                "location_icon": "field",
                "npc_name": None,
                "npc_type": None,
                "item_found": None,
                "weather": "foggy",
            },
            "map_update": {
                "new_location": "The Crossroads",
                "location_icon": "field",
                "connects_to_previous": True,
            },
        }
