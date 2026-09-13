from fastapi import APIRouter, Depends, HTTPException
from typing import List
from auth.dependencies import get_current_user_id
from features.repeater.models import RepeaterConfig, RepeaterStatsDTO
from features.repeater.service import repeater_service

router = APIRouter(prefix="/api/features/repeater", tags=["repeater"])

@router.get("/targets", response_model=List[RepeaterConfig])
async def get_targets(user_id: int = Depends(get_current_user_id)):
    targets = repeater_service.get_targets(user_id)
    return [RepeaterConfig(**t, is_active=True) for t in targets]

@router.post("/targets", response_model=RepeaterConfig)
async def add_target(config: RepeaterConfig, user_id: int = Depends(get_current_user_id)):
    repeater_service.set_target(
        user_id, 
        config.chat_id, 
        config.target_user_id, 
        config.cooldown_seconds, 
        config.max_messages
    )
    return config

@router.delete("/targets", response_model=dict)
async def remove_target(chat_id: int, target_user_id: int, user_id: int = Depends(get_current_user_id)):
    repeater_service.remove_target(user_id, chat_id, target_user_id)
    return {"status": "success"}

@router.get("/stats", response_model=RepeaterStatsDTO)
async def get_stats(user_id: int = Depends(get_current_user_id)):
    stats = repeater_service.get_stats(user_id)
    return RepeaterStatsDTO(**stats)
