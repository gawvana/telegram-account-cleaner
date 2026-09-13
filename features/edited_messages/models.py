from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class EditVersionDTO(BaseModel):
    old_text: Optional[str]
    new_text: Optional[str]
    edit_version: int
    edited_at: datetime

class EditedMessageDTO(BaseModel):
    id: int
    telegram_id: int
    chat_id: int
    message_id: int
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    chat_title: Optional[str] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    edit_version: int
    edited_at: datetime

class EditStatsDTO(BaseModel):
    total_edits: int
    unique_messages_edited: int
