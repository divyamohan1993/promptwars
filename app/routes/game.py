from fastapi import APIRouter, HTTPException

from app.models.schemas import ActionRequest, GameResponse, GameStartRequest
from app.services.game_engine import GameEngine, GameNotFoundError, GameOverError

router = APIRouter(prefix="/api/game", tags=["game"])

_engine: GameEngine | None = None


def get_game_engine() -> GameEngine:
    global _engine
    if _engine is None:
        _engine = GameEngine()
    return _engine


def set_game_engine(engine: GameEngine) -> None:
    global _engine
    _engine = engine


@router.post("/start", response_model=GameResponse)
async def start_game(request: GameStartRequest) -> GameResponse:
    try:
        return await get_game_engine().create_game(request.player_name, request.genre)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start game: {e}")


@router.post("/action", response_model=GameResponse)
async def take_action(request: ActionRequest) -> GameResponse:
    try:
        return await get_game_engine().process_action(request.game_id, request.action)
    except GameNotFoundError:
        raise HTTPException(status_code=404, detail="Game not found")
    except GameOverError:
        raise HTTPException(status_code=400, detail="Game is already over")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process action: {e}")


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: str) -> GameResponse:
    engine = get_game_engine()
    state = engine.get_game(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return engine._to_response(state)
