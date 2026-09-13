from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class AuthVerificationRequest(BaseModel):
    init_data: str


class LoginCodeRequest(BaseModel):
    phone: str
    api_id: Optional[int] = None
    api_hash: Optional[str] = None


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
    auto_clean_enabled: Optional[Union[int, bool]] = None
    auto_clean_frequency: Optional[str] = None
    auto_clean_scope: Optional[str] = None
    auto_clean_mode: Optional[str] = None
    dead_channel_days: Optional[int] = Field(None, ge=7, le=365)
    notifications_enabled: Optional[Union[int, bool]] = None


class UserCredentialsUpdateRequest(BaseModel):
    api_id: int = Field(..., gt=0, description="Telegram MTProto App API ID")
    api_hash: str = Field(..., min_length=8, max_length=128, description="Telegram MTProto App API Hash")


class BackendDiagnostics(BaseModel):
    status: str = "ok"
    app_name: str
    app_version: str
    uptime_seconds: float
    server_time: str
    python_version: str
    serverless_mode: bool


class DatabaseDiagnostics(BaseModel):
    status: str
    path: str
    journal_mode: str
    integrity_check: str
    current_migration_version: int
    latest_migration_version: int
    table_counts: Dict[str, int]
    latency_ms: float


class SessionStoreDiagnostics(BaseModel):
    status: str
    directory: str
    directory_exists: bool
    is_writable: bool
    active_sessions_count: int
    master_key_configured: bool


class SchedulerDiagnostics(BaseModel):
    status: str
    enabled: bool
    timezone: str
    registered_jobs_count: int


class StorageDiagnostics(BaseModel):
    status: str
    db_size_bytes: int
    backup_snapshots_count: int
    disk_total_bytes: int
    disk_free_bytes: int
    disk_used_percent: float


class DiagnosticsResponse(BaseModel):
    overall_status: str
    timestamp: str
    backend: BackendDiagnostics
    database: DatabaseDiagnostics
    sessions: SessionStoreDiagnostics
    scheduler: SchedulerDiagnostics
    storage: StorageDiagnostics


class ScoreDeduction(BaseModel):
    category: str
    count: int
    penalty_per_item: int
    total_deduction: int
    advice: str


class HygieneScoreBreakdownResponse(BaseModel):
    score: int
    total_dialogs: int
    whitelisted_count: int
    cleaned_count: int
    dead_channels_count: int
    suspicious_bots_count: int
    abandoned_chats_count: int
    deductions: List[ScoreDeduction]
    cleanliness_percentage: float
    grade: str


class CustomRuleDefinition(BaseModel):
    name: str = Field("Новое правило", min_length=2, max_length=64)
    target_action: str = Field("whitelist", pattern="^(whitelist|cleanup_candidate)$")
    chat_types: Optional[List[str]] = None
    min_inactive_days: Optional[int] = Field(None, ge=0)
    title_regex: Optional[str] = None
    username_regex: Optional[str] = None
    exclude_pinned: bool = True


class RuleSimulationRequest(BaseModel):
    rule: CustomRuleDefinition


class MatchedDialogPreview(BaseModel):
    chat_id: int
    title: str
    username: Optional[str] = None
    chat_type: str
    inactive_days: int
    match_reason: str


class RuleSimulationResponse(BaseModel):
    is_valid_regex: bool
    regex_error: Optional[str] = None
    total_evaluated: int
    matched_count: int
    matched_dialogs: List[MatchedDialogPreview]

