import datetime
from typing import Any, Dict, List, Optional
from domain.models import RawDialogDTO, ChatType
from telegram_client.base import ITelegramClientAdapter
from telegram_client.exceptions import (
    AuthRequiredException,
    InvalidCodeError,
    InvalidPhoneError,
    PasswordRequiredError,
    InvalidPasswordError,
)


class MockTelegramClientAdapter(ITelegramClientAdapter):
    """
    In-memory mock adapter for offline testing and development.
    Simulates MTProto client responses, authorization, dialog retrieval, and actions.
    """

    def __init__(
        self,
        is_authorized: bool = True,
        user_id: int = 123456789,
        dialogs: Optional[List[RawDialogDTO]] = None,
        require_2fa: bool = False,
    ):
        self._connected = True
        self._is_authorized = is_authorized
        self._user_id = user_id
        self._require_2fa = require_2fa
        self._code_sent = False
        self._pending_phone: Optional[str] = None
        self._pending_hash: Optional[str] = None

        if dialogs is not None:
            self._dialogs = dialogs
        else:
            # Default fixture dialogs
            now = datetime.datetime.now(datetime.timezone.utc)
            self._dialogs = [
                RawDialogDTO(
                    chat_id=101,
                    title="Old Dead Channel",
                    username="dead_channel_test",
                    chat_type=ChatType.CHANNEL.value,
                    unread_count=0,
                    last_message_date=now - datetime.timedelta(days=90),
                    is_creator=False,
                    is_admin=False,
                    is_pinned=False,
                    is_archived=False,
                ),
                RawDialogDTO(
                    chat_id=102,
                    title="Crypto Free Bot",
                    username="crypto_bonus_free_bot",
                    chat_type=ChatType.BOT.value,
                    unread_count=0,
                    last_message_date=now - datetime.timedelta(days=40),
                    is_creator=False,
                    is_admin=False,
                    is_pinned=False,
                    is_archived=False,
                ),
                RawDialogDTO(
                    chat_id=103,
                    title="Active Work Chat",
                    username="work_chat_team",
                    chat_type=ChatType.SUPERGROUP.value,
                    unread_count=5,
                    last_message_date=now - datetime.timedelta(hours=1),
                    is_creator=False,
                    is_admin=False,
                    is_pinned=True,
                    is_archived=False,
                ),
            ]

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def is_user_authorized(self) -> bool:
        return self._is_authorized

    async def get_me(self) -> Optional[Dict[str, Any]]:
        if not self._is_authorized:
            return None
        return {
            "id": self._user_id,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "phone": "+19999999999",
        }

    async def send_code_request(self, phone: str) -> str:
        if not phone or len(phone) < 5:
            raise InvalidPhoneError("Invalid phone number format")
        self._pending_phone = phone
        self._pending_hash = f"mock_hash_{hash(phone)}"
        self._code_sent = True
        return self._pending_hash

    async def sign_in_code(self, phone: str, code: str, phone_code_hash: str) -> bool:
        if code == "00000":
            raise InvalidCodeError("Invalid verification code")
        if self._require_2fa:
            raise PasswordRequiredError("Two-step verification enabled")
        self._is_authorized = True
        return True

    async def sign_in_password(self, password: str) -> bool:
        if password != "correct_password":
            raise InvalidPasswordError("Incorrect 2FA password")
        self._is_authorized = True
        return True

    async def fetch_dialogs(self, limit: Optional[int] = None) -> List[RawDialogDTO]:
        if not self._is_authorized:
            raise AuthRequiredException("Session not authorized")
        if limit:
            return self._dialogs[:limit]
        return list(self._dialogs)

    async def delete_dialog(self, chat_id: int, revoke: bool = True) -> bool:
        if not self._is_authorized:
            raise AuthRequiredException("Session not authorized")
        self._dialogs = [d for d in self._dialogs if d.chat_id != chat_id]
        return True

    async def leave_chat(self, chat_id: int) -> bool:
        if not self._is_authorized:
            raise AuthRequiredException("Session not authorized")
        self._dialogs = [d for d in self._dialogs if d.chat_id != chat_id]
        return True

    async def block_bot(self, bot_id: int) -> bool:
        if not self._is_authorized:
            raise AuthRequiredException("Session not authorized")
        self._dialogs = [d for d in self._dialogs if d.chat_id != bot_id]
        return True

    async def log_out(self) -> bool:
        self._is_authorized = False
        self._dialogs.clear()
        return True
