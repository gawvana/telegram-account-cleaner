from fastapi import APIRouter, Depends, HTTPException
from typing import List
import importlib

# Attempt to load from webapp.api.auth, if not assume a basic mock or it will be injected later
try:
    from webapp.api.auth import get_current_user_id
except ImportError:
    def get_current_user_id():
        return 1

from features.auto_responder.models import AutoResponderRuleCreate, AutoResponderRuleUpdate, AutoResponderRuleDTO, RuleTestRequest, RuleTestResponse
from features.auto_responder.service import auto_responder_service
from database import db

router = APIRouter(prefix="/api/features/auto-responder", tags=["auto-responder"])

@router.get("/rules", response_model=List[AutoResponderRuleDTO])
async def get_rules(user_id: int = Depends(get_current_user_id)):
    return await auto_responder_service.get_rules(user_id)

@router.post("/rules", response_model=AutoResponderRuleDTO)
async def create_rule(data: AutoResponderRuleCreate, user_id: int = Depends(get_current_user_id)):
    return await auto_responder_service.create_rule(user_id, data)

@router.put("/rules/{rule_id}", response_model=AutoResponderRuleDTO)
async def update_rule(rule_id: int, data: AutoResponderRuleUpdate, user_id: int = Depends(get_current_user_id)):
    updated = await auto_responder_service.update_rule(rule_id, user_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated

@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int, user_id: int = Depends(get_current_user_id)):
    deleted = await auto_responder_service.delete_rule(rule_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}

@router.post("/test", response_model=RuleTestResponse)
async def test_rule(data: RuleTestRequest, user_id: int = Depends(get_current_user_id)):
    is_match = auto_responder_service.test_rule(data.pattern, data.match_type, data.test_message)
    return RuleTestResponse(matched=is_match, response="Matched" if is_match else None)

@router.get("/stats")
async def get_stats(user_id: int = Depends(get_current_user_id)):
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) as rule_count, SUM(daily_count) as total_replies FROM auto_responder_rules WHERE telegram_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
    return {
        "rule_count": row["rule_count"] if row else 0,
        "total_replies_today": row["total_replies"] if row and row["total_replies"] else 0
    }
