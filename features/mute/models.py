from pydantic import BaseModel, Field
from typing import Optional

class MuteRuleCreate(BaseModel):
    chat_id: int
    target_user_id: int
    target_username: Optional[str] = None
    duration_minutes: int = Field(default=60)
    reason: Optional[str] = None

class MuteRuleDTO(BaseModel):
    chat_id: int
    target_user_id: int
    target_username: Optional[str] = None
    duration_minutes: int
    reason: Optional[str] = None
    expires_at: float

class MuteStatsDTO(BaseModel):
    active_mutes: int
    total_deleted: int
