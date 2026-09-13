from fastapi import APIRouter, Depends
from webapp.api.auth import get_current_user_id
from telegram_client.manager import client_manager
from features.one_time_messages.models import OneTimeMessageCreate, OneTimeMessageResponse, OneTimeStatsDTO
from features.one_time_messages.service import one_time_message_service

router = APIRouter(prefix="/api/features/one-time-messages", tags=["one-time-messages"])

@router.post("/send", response_model=OneTimeMessageResponse)
async def send_message(data: OneTimeMessageCreate, user_id: int = Depends(get_current_user_id)):
    client = client_manager.get_client(user_id)
    if not client:
        raise ValueError("Client not active")
    result = await one_time_message_service.send_temporary_message(
        user_id, client, data.chat_id, data.text, data.auto_delete_seconds
    )
    return result

@router.get("/stats", response_model=OneTimeStatsDTO)
async def get_stats(user_id: int = Depends(get_current_user_id)):
    stats = await one_time_message_service.get_stats(user_id)
    return OneTimeStatsDTO(**stats)
