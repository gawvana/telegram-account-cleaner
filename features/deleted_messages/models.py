from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DeletedMessageDTO(BaseModel):
    id: int
    telegram_id: int
    chat_id: int
    message_id: int
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    chat_title: Optional[str] = None
    message_type: str = "text"
    text_content: Optional[str] = None
    media_metadata: Optional[str] = None
    deleted_at: datetime
    original_date: Optional[datetime] = None

class ArchiveStatsDTO(BaseModel):
    total_messages: int
    total_chats: int
    oldest_message_date: Optional[datetime] = None
    newest_message_date: Optional[datetime] = None

class DeletedMessageCleanupResponse(BaseModel):
    deleted_count: int
