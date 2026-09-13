from pydantic import BaseModel
from typing import Dict, Any

class GameScoreSubmit(BaseModel):
    game_id: str
    score: int
    metrics: Dict[str, Any] = {}

class GameLeaderboardDTO(BaseModel):
    user_id: int
    game_id: str
    score: int
