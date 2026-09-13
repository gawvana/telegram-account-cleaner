from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import datetime


class ChatType(str, Enum):
    PRIVATE = "PRIVATE"
    BOT = "BOT"
    GROUP = "GROUP"
    SUPERGROUP = "SUPERGROUP"
    CHANNEL = "CHANNEL"
    OTHER = "OTHER"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(str, Enum):
    BUG = "bug"
    LOGIN_PROBLEM = "login_problem"
    CLEANUP_PROBLEM = "cleanup_problem"
    ACCOUNT_PROBLEM = "account_problem"
    SECURITY = "security"
    OTHER = "other"


class HeuristicTags(BaseModel):
    inactive_days: int = 0
    likely_dead_channel: bool = False
    likely_spam_bot: bool = False
    zero_interaction: bool = False
    recommended_for_cleanup: bool = False
    needs_review: bool = False
    tags: List[str] = Field(default_factory=list)


class DialogItem(BaseModel):
    chat_id: int
    title: str
    username: Optional[str] = None
    chat_type: ChatType
    unread_count: int = 0
    last_message_date: Optional[datetime.datetime] = None
    is_creator: bool = False
    is_admin: bool = False
    is_pinned: bool = False
    is_archived: bool = False
    is_whitelisted: bool = False
    can_leave: bool = True
    can_delete: bool = True
    requires_special_rights: bool = False
    tags: List[str] = Field(default_factory=list)
    heuristics: HeuristicTags = Field(default_factory=HeuristicTags)
    invite_link: Optional[str] = None


class RawDialogDTO(BaseModel):
    chat_id: int
    title: str
    username: Optional[str] = None
    chat_type: str
    unread_count: int = 0
    last_message_date: Optional[datetime.datetime] = None
    is_creator: bool = False
    is_admin: bool = False
    is_pinned: bool = False
    is_archived: bool = False
    invite_link: Optional[str] = None


class EntityInfoDTO(BaseModel):
    chat_id: int
    title: str
    username: Optional[str] = None
    chat_type: str
    can_delete: bool = True
    invite_link: Optional[str] = None


class ScanResult(BaseModel):
    total_dialogs: int = 0
    private_count: int = 0
    bots_count: int = 0
    groups_count: int = 0
    channels_count: int = 0
    archived_count: int = 0
    whitelisted_count: int = 0
    recommended_count: int = 0
    actionable_count: int = 0
    special_rights_count: int = 0
    inaccessible_count: int = 0
    dialogs: List[DialogItem] = Field(default_factory=list)
    items: List[DialogItem] = Field(default_factory=list)
    scan_timestamp: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    duration_seconds: float = 0.0


class CleanupPlan(BaseModel):
    job_id: str = ""
    user_id: int = 0
    target_types: List[ChatType] = Field(default_factory=list)
    target_chat_ids: List[int] = Field(default_factory=list)
    total_items: int = 0
    items: List[DialogItem] = Field(default_factory=list)
    is_smart_clean: bool = False
    is_max_clean: bool = False
    is_dry_run: bool = False
    dry_run: bool = False
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class CleanupItemResult(BaseModel):
    chat_id: int
    title: str = ""
    chat_title: str = ""
    chat_type: str = ""
    action: str = ""  # "DELETE", "LEAVE", "BLOCK", "SKIP"
    status: str = "SUCCESS"  # "SUCCESS", "FAILED", "SKIPPED"
    error_message: Optional[str] = None
    rejoin_data: Optional[Dict[str, Any]] = None
    processed_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class AuthStatus(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    WAITING_FOR_CODE = "WAITING_FOR_CODE"
    WAITING_FOR_2FA = "WAITING_FOR_2FA"
    AUTHENTICATING = "AUTHENTICATING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ERROR = "ERROR"


class AuthState(BaseModel):
    status: AuthStatus = AuthStatus.DISCONNECTED
    is_authorized: bool = False
    phone: Optional[str] = None
    phone_code_hash: Optional[str] = None
    step: str = "PHONE"  # Backwards compatibility: "PHONE", "CODE", "2FA", "AUTHORIZED"
    error_message: Optional[str] = None
    expires_at: Optional[float] = None


class TicketDTO(BaseModel):
    id: int
    ticket_number: str
    telegram_id: int
    category: str
    subject: str
    description: str
    status: str
    priority: str = "normal"
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    assigned_admin_id: Optional[int] = None


class TicketMessageDTO(BaseModel):
    id: int
    ticket_id: int
    sender_type: str  # "user" or "admin"
    sender_id: int
    message: str
    attachments: Optional[str] = None
    created_at: str


class ConsentDTO(BaseModel):
    id: int
    telegram_id: int
    agreement_version: int
    privacy_version: int
    terms_hash: str
    accepted_at: str
    withdrawn_at: Optional[str] = None
    is_active: bool = True
