from pydantic import BaseModel
from typing import Literal

class OneTimeMessageCreate(BaseModel):
    chat_id: int
    text: str
    auto_delete_seconds: int = 30

class OneTimeMessageResponse(BaseModel):
    message_id: int
    chat_id: int
    expires_at: float

class OneTimeStatsDTO(BaseModel):
    sent_count: int
    deleted_count: int
