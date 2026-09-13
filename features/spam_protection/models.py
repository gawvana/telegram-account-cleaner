from pydantic import BaseModel
from typing import List

class SpamRuleCreate(BaseModel):
    chat_id: int
    block_keywords: List[str] = []
    max_messages_per_minute: int = 10
    delete_links: bool = False
    delete_forwards: bool = False
    is_active: bool = True

class SpamRuleDTO(BaseModel):
    chat_id: int
    block_keywords: List[str]
    max_messages_per_minute: int
    delete_links: bool
    delete_forwards: bool
    is_active: bool

class SpamStatsDTO(BaseModel):
    actions_taken: int
    messages_inspected: int
    spam_detected: int
