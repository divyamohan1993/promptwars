"""Game API routes for starting adventures, taking actions, and narration."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_game_engine, get_tts_service
from app.models.schemas import ActionRequest, GameResponse, GameStartRequest, TTSRequest, TTSResponse
from app.services.game_engine import GameEngine, GameNotFoundError, GameOverError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/game", tags=["game"])


@router.post("/start", response_model=GameResponse)
async def start_game(
    request: GameStartRequest,
    engine: GameEngine = Depends(get_game_engine),
) -> GameResponse:
    """Start a new game session with the specified genre and player name."""
    try:
        return await engine.create_game(request.player_name, request.genre)
    except Exception as e:
        logger.error("Failed to start game: %s", e)
        raise HTTPException(status_code=500, detail="Failed to start game")


@router.post("/action", response_model=GameResponse)
async def take_action(
    request: ActionRequest,
    engine: GameEngine = Depends(get_game_engine),
) -> GameResponse:
    """Process a player action and return the updated game state."""
    try:
        return await engine.process_action(request.game_id, request.action)
    except GameNotFoundError:
        raise HTTPException(status_code=404, detail="Game not found")
    except GameOverError:
        raise HTTPException(status_code=400, detail="Game is already over")
    except Exception as e:
        logger.error("Failed to process action: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process action")


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(
    game_id: str,
    engine: GameEngine = Depends(get_game_engine),
) -> GameResponse:
    """Retrieve the current state of an existing game."""
    state = await engine.get_game(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return engine._to_response(state)


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(request: TTSRequest) -> TTSResponse:
    """Convert narrative text to speech audio using Google Cloud TTS."""
    tts = get_tts_service()
    if tts is None:
        raise HTTPException(status_code=503, detail="Text-to-Speech service is not enabled")
    try:
        audio_b64 = await tts.synthesize(request.text)
        return TTSResponse(audio=audio_b64)
    except Exception as e:
        logger.error("TTS failed: %s", e)
        raise HTTPException(status_code=500, detail="Text-to-Speech synthesis failed")
