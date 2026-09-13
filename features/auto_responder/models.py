from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class MatchType(str, Enum):
    EXACT = "exact"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    REGEX = "regex"

class AutoResponderRuleCreate(BaseModel):
    match_type: MatchType
    pattern: str
    response: str
    chat_id: Optional[int] = None
    user_id_filter: Optional[int] = None
    cooldown_seconds: int = Field(default=60)
    max_daily: int = Field(default=50)

class AutoResponderRuleUpdate(BaseModel):
    match_type: Optional[MatchType] = None
    pattern: Optional[str] = None
    response: Optional[str] = None
    chat_id: Optional[int] = None
    user_id_filter: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    max_daily: Optional[int] = None
    is_active: Optional[bool] = None

class AutoResponderRuleDTO(BaseModel):
    id: int
    telegram_id: int
    match_type: MatchType
    pattern: str
    response: str
    chat_id: Optional[int] = None
    user_id_filter: Optional[int] = None
    cooldown_seconds: int
    max_daily: int
    daily_count: int
    is_active: bool

class RuleTestRequest(BaseModel):
    pattern: str
    match_type: MatchType
    test_message: str

class RuleTestResponse(BaseModel):
    matched: bool
    response: Optional[str] = None
