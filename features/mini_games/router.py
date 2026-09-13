from fastapi import APIRouter, Depends
from webapp.api.auth import get_current_user_id
from .models import GameScoreSubmit
from .service import game_service

router = APIRouter(prefix="/api/features/mini-games", tags=["mini-games"])

@router.get("/games")
async def get_games(user_id: int = Depends(get_current_user_id)):
    return game_service.get_available_games()

@router.post("/score")
async def submit_score(req: GameScoreSubmit, user_id: int = Depends(get_current_user_id)):
    game_service.submit_score(user_id, req.game_id, req.score)
    return {"status": "success"}

@router.get("/scores")
async def get_scores(user_id: int = Depends(get_current_user_id)):
    return game_service.get_high_scores(user_id)
