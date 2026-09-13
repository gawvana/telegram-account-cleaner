from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from features.edited_messages.models import EditedMessageDTO, EditVersionDTO, EditStatsDTO
from features.edited_messages.service import edited_messages_service
from webapp.api.auth import get_current_user_id

router = APIRouter(prefix="/api/features/edited-messages", tags=["edited-messages"])

@router.get("/", response_model=List[EditedMessageDTO])
async def list_messages(
    chat_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id)
):
    return await edited_messages_service.get_messages(user_id, chat_id, limit, offset)

@router.get("/{chat_id}/{message_id}/history", response_model=List[EditVersionDTO])
async def get_history(
    chat_id: int,
    message_id: int,
    user_id: int = Depends(get_current_user_id)
):
    return await edited_messages_service.get_history(user_id, chat_id, message_id)

@router.get("/stats", response_model=EditStatsDTO)
async def get_stats(user_id: int = Depends(get_current_user_id)):
    return await edited_messages_service.get_stats(user_id)
