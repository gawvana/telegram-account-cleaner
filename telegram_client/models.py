import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatType(str, Enum):
    PRIVATE = "PRIVATE"
    BOT = "BOT"
    GROUP = "GROUP"
    SUPERGROUP = "SUPERGROUP"
    CHANNEL = "CHANNEL"
    OTHER = "OTHER"


class HeuristicTags(BaseModel):
    inactive_days: int = 0
    likely_dead_channel: bool = False
    likely_spam_bot: bool = False
    zero_interaction: bool = False
    recommended_for_cleanup: bool = False
    tags: List[str] = Field(default_factory=list)


class DialogItem(BaseModel):
    chat_id: int
    title: str
    username: Optional[str] = None
    chat_type: ChatType
    unread_count: int = 0
    is_pinned: bool = False
    is_archived: bool = False
    is_creator: bool = False
    is_admin: bool = False
    is_whitelisted: bool = False
    can_leave: bool = True
    can_delete: bool = True
    requires_special_rights: bool = False
    last_message_date: Optional[datetime.datetime] = None
    heuristics: HeuristicTags = Field(default_factory=HeuristicTags)


class ScanResult(BaseModel):
    total_dialogs: int = 0
    private_chats: int = 0
    bot_chats: int = 0
    group_chats: int = 0
    channel_chats: int = 0
    whitelisted_count: int = 0
    recommended_count: int = 0
    actionable_count: int = 0
    special_rights_count: int = 0
    inaccessible_count: int = 0
    items: List[DialogItem] = Field(default_factory=list)


class CleanupPlan(BaseModel):
    target_types: List[ChatType] = Field(default_factory=list)
    target_chat_ids: List[int] = Field(default_factory=list)
    is_smart_clean: bool = False
    is_max_clean: bool = False
    dry_run: bool = False


class CleanupItemResult(BaseModel):
    chat_id: int
    title: str
    chat_type: ChatType
    action: str
    status: str  # "SUCCESS", "SKIPPED", "ERROR"
    error_message: Optional[str] = None
    rejoin_data: Optional[Dict[str, Any]] = None


class AuthState(BaseModel):
    is_authorized: bool = False
    phone: Optional[str] = None
    phone_code_hash: Optional[str] = None
    step: str = "PHONE"  # "PHONE", "CODE", "2FA", "AUTHORIZED"
    error_message: Optional[str] = None
