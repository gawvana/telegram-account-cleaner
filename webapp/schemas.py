from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuthVerificationRequest(BaseModel):
    init_data: str


class LoginCodeRequest(BaseModel):
    phone: str


class LoginCodeSubmit(BaseModel):
    code: str


class Login2FASubmit(BaseModel):
    password: str


class WhitelistItemCreate(BaseModel):
    chat_id: int
    title: str = ""
    username: Optional[str] = None
    rule_pattern: Optional[str] = None


class WhitelistImportRequest(BaseModel):
    items: List[Dict[str, Any]]


class CleanupStartRequest(BaseModel):
    is_max_clean: bool = False
    is_smart_clean: bool = False
    target_types: List[str] = Field(default_factory=list)
    target_chat_ids: List[int] = Field(default_factory=list)
    dry_run: bool = False


class SettingsUpdateRequest(BaseModel):
    auto_clean_enabled: Optional[int] = None
    auto_clean_frequency: Optional[str] = None
    auto_clean_scope: Optional[str] = None
    auto_clean_mode: Optional[str] = None
    dead_channel_days: Optional[int] = None
    notifications_enabled: Optional[int] = None
