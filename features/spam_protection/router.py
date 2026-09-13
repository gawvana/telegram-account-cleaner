from fastapi import APIRouter, Depends
from typing import Dict, List
from webapp.api.auth import get_current_user_id
from features.spam_protection.models import SpamRuleCreate, SpamRuleDTO, SpamStatsDTO
from features.spam_protection.service import spam_protection_service

router = APIRouter(prefix="/api/features/spam-protection", tags=["spam-protection"])

@router.get("/rules", response_model=Dict[int, SpamRuleDTO])
async def get_rules(user_id: int = Depends(get_current_user_id)):
    rules = await spam_protection_service.get_rules(user_id)
    return rules

@router.post("/rules")
async def create_rule(rule: SpamRuleCreate, user_id: int = Depends(get_current_user_id)):
    await spam_protection_service.set_rule(user_id, rule.chat_id, rule.model_dump())
    return {"status": "success"}

@router.delete("/rules/{chat_id}")
async def delete_rule(chat_id: int, user_id: int = Depends(get_current_user_id)):
    success = await spam_protection_service.delete_rule(user_id, chat_id)
    return {"success": success}

@router.get("/stats", response_model=SpamStatsDTO)
async def get_stats(user_id: int = Depends(get_current_user_id)):
    stats = await spam_protection_service.get_stats(user_id)
    return SpamStatsDTO(**stats)
