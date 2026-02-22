"""Pydantic models for request / response validation and serialization.

Every external-facing field is constrained with ``min_length`` /
``max_length`` / ``ge`` / ``le`` to reject invalid data at the boundary
before it reaches business logic or Google Cloud APIs.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator

# Pattern: only printable characters, no control chars / null bytes.
_SAFE_TEXT_RE = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]*$")


class Adventure(str, Enum):
    """Available adventure themes."""

    HAWKINS_INVESTIGATION = "hawkins-investigation"
    UPSIDE_DOWN = "upside-down"
    HAWKINS_LAB = "hawkins-lab"
    DND_CAMPAIGN = "dnd-campaign"


class SceneVisual(BaseModel):
    """Visual metadata returned by Gemini for rendering scene cards."""

    scene_type: str = "exploration"
    mood: str = "neutral"
    location_name: str = ""
    location_icon: str = ""
    npc_name: str | None = None
    npc_type: str | None = None
    item_found: str | None = None
    weather: str = "clear"


class MapNode(BaseModel):
    """A node on the procedural adventure map."""

    node_id: str
    name: str
    visited: bool = False
    connected_to: list[str] = Field(default_factory=list)
    icon: str = "location"
    x: int = Field(default=0, ge=0)
    y: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Request models — validated at the API boundary
# ---------------------------------------------------------------------------

class GameStartRequest(BaseModel):
    """Payload for starting a new adventure."""

    player_name: str = Field(..., min_length=1, max_length=50)
    adventure: Adventure
    language: str = Field(default="en", min_length=2, max_length=10)

    @field_validator("player_name")
    @classmethod
    def _sanitise_player_name(cls, v: str) -> str:
        v = v.strip()
        if not _SAFE_TEXT_RE.match(v):
            raise ValueError("Player name contains invalid characters")
        return v


class ActionRequest(BaseModel):
    """Payload for a player action."""

    game_id: str = Field(..., min_length=1, max_length=128)
    action: str = Field(..., min_length=1, max_length=500)

    @field_validator("action")
    @classmethod
    def _sanitise_action(cls, v: str) -> str:
        v = v.strip()
        if not _SAFE_TEXT_RE.match(v):
            raise ValueError("Action contains invalid characters")
        return v


class TTSRequest(BaseModel):
    """Payload for text-to-speech synthesis."""

    text: str = Field(..., min_length=1, max_length=2000)


class TranslateRequest(BaseModel):
    """Payload for narrative translation."""

    text: str = Field(..., min_length=1, max_length=5000)
    target_language: str = Field(..., min_length=2, max_length=10)


class ImageRequest(BaseModel):
    """Payload for scene image generation."""

    prompt: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Internal / persistence models
# ---------------------------------------------------------------------------

class GameState(BaseModel):
    """Full in-memory / Firestore representation of a game session."""

    game_id: str
    player_name: str
    adventure: Adventure
    health: int = Field(default=100, ge=0, le=100)
    inventory: list[str] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)
    narrative: str = ""
    choices: list[str] = Field(default_factory=list)
    choice_icons: list[str] = Field(default_factory=list)
    is_alive: bool = True
    is_complete: bool = False
    story_history: list[dict] = Field(default_factory=list)
    scene_visual: SceneVisual = Field(default_factory=SceneVisual)
    map_nodes: list[MapNode] = Field(default_factory=list)
    current_node_id: str = ""
    achievements: list[str] = Field(default_factory=list)
    xp: int = Field(default=0, ge=0)
    language: str = "en"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class GameResponse(BaseModel):
    """Public game state returned to the client after each turn."""

    game_id: str
    narrative: str
    choices: list[str]
    choice_icons: list[str]
    health: int
    inventory: list[str]
    turn_count: int
    is_alive: bool
    is_complete: bool
    scene_visual: SceneVisual
    map_nodes: list[MapNode]
    current_node_id: str
    achievements: list[str]
    xp: int


class TTSResponse(BaseModel):
    audio: str


class TranslateResponse(BaseModel):
    translated_text: str
    source_language: str


class ImageResponse(BaseModel):
    image_url: str
