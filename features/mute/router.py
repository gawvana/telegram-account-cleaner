from fastapi import APIRouter, Depends, HTTPException
from typing import List

try:
    from webapp.api.auth import get_current_user_id
except ImportError:
    def get_current_user_id():
        return 1

from features.mute.models import MuteRuleCreate, MuteRuleDTO, MuteStatsDTO
from features.mute.service import mute_service
from database import db

router = APIRouter(prefix="/api/features/mute", tags=["mute"])

@router.get("/rules", response_model=List[MuteRuleDTO])
async def get_rules(user_id: int = Depends(get_current_user_id)):
    return mute_service.get_active_mutes(user_id)

@router.post("/rules", response_model=dict)
async def create_rule(data: MuteRuleCreate, user_id: int = Depends(get_current_user_id)):
    await mute_service.add_mute(user_id, data.chat_id, data.target_user_id, data.duration_minutes, data.reason)
    return {"success": True}

@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, user_id: int = Depends(get_current_user_id)):
    # The requirement says DELETE /rules/{rule_id}, but we need chat_id and target_user_id. 
    # Let's assume rule_id is formatted as chat_id_target_user_id
    try:
        parts = rule_id.split('_')
        chat_id = int(parts[0])
        target_user_id = int(parts[1])
    except:
        raise HTTPException(status_code=400, detail="Invalid rule_id format. Expected chat_id_target_user_id")

    deleted = mute_service.remove_mute(user_id, chat_id, target_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mute rule not found")
    return {"success": True}

@router.get("/stats", response_model=MuteStatsDTO)
async def get_stats(user_id: int = Depends(get_current_user_id)):
    active_mutes = len(mute_service.get_active_mutes(user_id))
    
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM feature_activity WHERE telegram_id = ? AND feature_id = 'mute' AND action = 'deleted_message'",
            (user_id,)
        )
        row = await cursor.fetchone()
        total_deleted = row["count"] if row else 0
        
    return MuteStatsDTO(active_mutes=active_mutes, total_deleted=total_deleted)
