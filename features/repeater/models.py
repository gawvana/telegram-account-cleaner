from pydantic import BaseModel

class RepeaterConfig(BaseModel):
    chat_id: int
    target_user_id: int
    cooldown_seconds: int = 3
    max_messages: int = 10
    is_active: bool = True

class RepeaterStatsDTO(BaseModel):
    repeated_count: int
    active_chats: int
