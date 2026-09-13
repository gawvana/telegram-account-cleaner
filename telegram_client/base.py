from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from domain.models import RawDialogDTO, DialogItem


class ITelegramClientAdapter(ABC):
    """
    Abstract interface isolating Telegram MTProto client operations (Telethon, mock, etc.)
    from business and application services.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Connect to the Telegram network."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the Telegram network."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if currently connected."""
        pass

    @abstractmethod
    async def is_user_authorized(self) -> bool:
        """Check if the current session is authorized."""
        pass

    @abstractmethod
    async def get_me(self) -> Optional[Dict[str, Any]]:
        """Fetch current user profile information."""
        pass

    @abstractmethod
    async def send_code_request(self, phone: str) -> str:
        """Request verification code for the phone. Returns phone_code_hash."""
        pass

    @abstractmethod
    async def sign_in_code(self, phone: str, code: str, phone_code_hash: str) -> bool:
        """Sign in with phone code. Returns True if authorized, raises PasswordRequiredError if 2FA needed."""
        pass

    @abstractmethod
    async def sign_in_password(self, password: str) -> bool:
        """Complete 2FA authentication with cloud password."""
        pass

    @abstractmethod
    async def fetch_dialogs(self, limit: Optional[int] = None) -> List[RawDialogDTO]:
        """Fetch all user dialogs and chats."""
        pass

    @abstractmethod
    async def delete_dialog(self, chat_id: int, revoke: bool = True) -> bool:
        """Delete a private chat or clear dialog history."""
        pass

    @abstractmethod
    async def leave_chat(self, chat_id: int) -> bool:
        """Leave a group, supergroup, or channel."""
        pass

    @abstractmethod
    async def block_bot(self, bot_id: int) -> bool:
        """Block and stop a bot."""
        pass

    @abstractmethod
    async def log_out(self) -> bool:
        """Log out the current user session and revoke MTProto auth keys."""
        pass
