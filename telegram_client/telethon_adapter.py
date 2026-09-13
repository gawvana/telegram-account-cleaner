import asyncio
from typing import Any, Dict, List, Optional
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserNotParticipantError,
)
from telethon.tl.types import Channel, Chat, User
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import BlockRequest

from config import settings
from domain.models import ChatType, RawDialogDTO
from telegram_client.base import ITelegramClientAdapter
from telegram_client.exceptions import (
    AuthRequiredException,
    FloodWaitTimeoutException,
    InvalidCodeError,
    InvalidPasswordError,
    InvalidPhoneError,
    PasswordRequiredError,
    PermissionDeniedException,
)
from utils.logger import logger


class TelethonAdapter(ITelegramClientAdapter):
    """
    Concrete implementation of ITelegramClientAdapter backed by Telethon MTProto client.
    Converts Telethon exceptions into domain exceptions.
    """

    def __init__(self, client: TelegramClient):
        self._client = client

    @property
    def client(self) -> TelegramClient:
        return self._client

    async def connect(self) -> None:
        if not self._client.is_connected():
            await self._client.connect()

    async def disconnect(self) -> None:
        if self._client.is_connected():
            await self._client.disconnect()

    async def is_connected(self) -> bool:
        return self._client.is_connected()

    async def is_user_authorized(self) -> bool:
        try:
            return await self._client.is_user_authorized()
        except Exception as e:
            logger.warning(f"Error checking is_user_authorized: {e}")
            return False

    async def get_me(self) -> Optional[Dict[str, Any]]:
        try:
            me = await self._client.get_me()
            if not me:
                return None
            return {
                "id": me.id,
                "first_name": getattr(me, "first_name", None),
                "last_name": getattr(me, "last_name", None),
                "username": getattr(me, "username", None),
                "phone": getattr(me, "phone", None),
            }
        except Exception as e:
            logger.error(f"Error calling get_me: {e}")
            return None

    async def send_code_request(self, phone: str) -> str:
        clean_phone = "".join(filter(lambda c: c.isdigit() or c == "+", phone))
        try:
            sent_code = await self._client.send_code_request(clean_phone)
            return sent_code.phone_code_hash
        except PhoneNumberInvalidError as e:
            raise InvalidPhoneError("Номер телефона указан неверно.") from e
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds) from e

    async def sign_in_code(self, phone: str, code: str, phone_code_hash: str) -> bool:
        clean_phone = "".join(filter(lambda c: c.isdigit() or c == "+", phone))
        clean_code = "".join(filter(str.isdigit, code))
        try:
            await self._client.sign_in(
                phone=clean_phone,
                code=clean_code,
                phone_code_hash=phone_code_hash,
            )
            return True
        except SessionPasswordNeededError as e:
            raise PasswordRequiredError("Требуется ввод пароля двухэтапной аутентификации (2FA).") from e
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
            raise InvalidCodeError("Код подтверждения неверен или истёк.") from e
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds) from e

    async def sign_in_password(self, password: str) -> bool:
        try:
            await self._client.sign_in(password=password)
            return True
        except PasswordHashInvalidError as e:
            raise InvalidPasswordError("Неверный 2FA пароль.") from e
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds) from e

    async def fetch_dialogs(self, limit: Optional[int] = None) -> List[RawDialogDTO]:
        try:
            dialogs = await self._client.get_dialogs(limit=limit)
        except Exception as e:
            logger.error(f"Error fetching dialogs: {e}")
            raise AuthRequiredException("Failed to fetch dialogs from Telegram.") from e

        results: List[RawDialogDTO] = []
        for d in dialogs:
            entity = d.entity
            chat_id = d.id
            title = d.name or "Unnamed Dialog"
            username = getattr(entity, "username", None)
            is_pinned = bool(d.pinned)
            is_archived = bool(d.archived)
            unread_count = d.unread_count or 0
            last_date = d.date

            chat_type = ChatType.OTHER.value
            is_creator = getattr(entity, "creator", False)
            is_admin = bool(getattr(entity, "admin_rights", None))

            if isinstance(entity, User):
                if getattr(entity, "bot", False):
                    chat_type = ChatType.BOT.value
                else:
                    chat_type = ChatType.PRIVATE.value
            elif isinstance(entity, Channel):
                if getattr(entity, "megagroup", False) or getattr(entity, "gigagroup", False):
                    chat_type = ChatType.SUPERGROUP.value
                else:
                    chat_type = ChatType.CHANNEL.value
            elif isinstance(entity, Chat):
                chat_type = ChatType.GROUP.value

            results.append(
                RawDialogDTO(
                    chat_id=chat_id,
                    title=title,
                    username=username,
                    chat_type=chat_type,
                    unread_count=unread_count,
                    last_message_date=last_date,
                    is_creator=is_creator,
                    is_admin=is_admin,
                    is_pinned=is_pinned,
                    is_archived=is_archived,
                )
            )
        return results

    async def delete_dialog(self, chat_id: int, revoke: bool = True) -> bool:
        try:
            entity = await self._client.get_input_entity(chat_id)
            await self._client.delete_dialog(entity, revoke=revoke)
            return True
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds) from e
        except (ChannelPrivateError, ChatAdminRequiredError) as e:
            raise PermissionDeniedException(f"Cannot delete chat {chat_id}: permission denied") from e
        except Exception as e:
            logger.warning(f"Error deleting dialog {chat_id}: {e}")
            return False

    async def leave_chat(self, chat_id: int) -> bool:
        try:
            entity = await self._client.get_input_entity(chat_id)
            if isinstance(entity, (Channel, User)):
                await self._client(LeaveChannelRequest(channel=entity))
            else:
                await self._client.delete_dialog(entity)
            return True
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds) from e
        except (UserNotParticipantError, ChannelPrivateError) as e:
            # Already left or not participant
            return True
        except Exception as e:
            logger.warning(f"Error leaving chat {chat_id}: {e}")
            return False

    async def block_bot(self, bot_id: int) -> bool:
        try:
            entity = await self._client.get_input_entity(bot_id)
            try:
                await self._client(BlockRequest(id=entity))
            except Exception:
                pass
            await self._client.delete_dialog(entity)
            return True
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds) from e
        except Exception as e:
            logger.warning(f"Error blocking bot {bot_id}: {e}")
            return False

    async def log_out(self) -> bool:
        try:
            await self._client.log_out()
            return True
        except Exception as e:
            logger.warning(f"Error logging out Telethon client: {e}")
            return False
