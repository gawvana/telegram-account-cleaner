from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from features.deleted_messages.models import DeletedMessageDTO, ArchiveStatsDTO, DeletedMessageCleanupResponse
from features.deleted_messages.service import deleted_messages_service
from webapp.api.auth import get_current_user_id

router = APIRouter(prefix="/api/features/deleted-messages", tags=["deleted-messages"])

@router.get("/", response_model=List[DeletedMessageDTO])
async def list_messages(
    chat_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id)
):
    return await deleted_messages_service.get_messages(user_id, chat_id, limit, offset)

@router.get("/stats", response_model=ArchiveStatsDTO)
async def get_stats(user_id: int = Depends(get_current_user_id)):
    return await deleted_messages_service.get_stats(user_id)

@router.post("/cleanup", response_model=DeletedMessageCleanupResponse)
async def cleanup(
    retention_days: int = Query(..., ge=1),
    user_id: int = Depends(get_current_user_id)
):
    deleted_count = await deleted_messages_service.cleanup(user_id, retention_days)
    return DeletedMessageCleanupResponse(deleted_count=deleted_count)

@router.get("/search", response_model=List[DeletedMessageDTO])
async def search_messages(
    query: str,
    limit: int = Query(50, ge=1, le=100),
    user_id: int = Depends(get_current_user_id)
):
    return await deleted_messages_service.search(user_id, query, limit)
