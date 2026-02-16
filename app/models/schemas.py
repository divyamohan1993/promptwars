from enum import Enum
from pydantic import BaseModel, Field


class Genre(str, Enum):
    FANTASY = "fantasy"
    SCI_FI = "sci-fi"
    MYSTERY = "mystery"
    HORROR = "horror"
    PIRATE = "pirate"


class GameStartRequest(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=50)
    genre: Genre


class ActionRequest(BaseModel):
    game_id: str
    action: str = Field(..., min_length=1, max_length=500)


class GameState(BaseModel):
    game_id: str
    player_name: str
    genre: Genre
    health: int = Field(default=100, ge=0, le=100)
    inventory: list[str] = Field(default_factory=list)
    turn_count: int = 0
    narrative: str = ""
    choices: list[str] = Field(default_factory=list)
    is_alive: bool = True
    is_complete: bool = False
    story_history: list[dict] = Field(default_factory=list)


class GameResponse(BaseModel):
    game_id: str
    narrative: str
    choices: list[str]
    health: int
    inventory: list[str]
    turn_count: int
    is_alive: bool
    is_complete: bool
