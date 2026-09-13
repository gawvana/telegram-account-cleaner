import asyncio
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
)
from telethon.sessions import StringSession

from config import settings
from database import db
from services.crypto_service import crypto_service
from telegram_client.exceptions import AuthRequiredException, FloodWaitTimeoutException
from telegram_client.models import AuthState
from utils.logger import logger


class PendingAuthSession:
    """Holds in-memory transient Telethon client during the authentication handshake."""

    def __init__(self, telegram_id: int, client: TelegramClient, phone: str, phone_code_hash: str):
        self.telegram_id = telegram_id
        self.client = client
        self.phone = phone
        self.phone_code_hash = phone_code_hash
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        # 10 minutes timeout for login flow
        return time.time() - self.created_at > 600


class AuthManager:
    """Manages the secure Telethon login process (chat-based or Mini App)."""

    def __init__(self):
        self._pending_sessions: Dict[int, PendingAuthSession] = {}
        self._lock = asyncio.Lock()

    async def cleanup_expired(self) -> None:
        async with self._lock:
            expired_ids = [uid for uid, s in self._pending_sessions.items() if s.is_expired]
            for uid in expired_ids:
                pending = self._pending_sessions.pop(uid, None)
                if pending and pending.client.is_connected():
                    await pending.client.disconnect()

    async def request_phone_code(self, telegram_id: int, phone: str) -> AuthState:
        """Step 1: Connects Telethon client and requests SMS/Telegram auth code."""
        await self.cleanup_expired()
        clean_phone = "".join(filter(lambda c: c.isdigit() or c == "+", phone))

        # Create transient client in memory
        client = TelegramClient(StringSession(), settings.API_ID, settings.API_HASH)
        await client.connect()

        try:
            sent_code = await client.send_code_request(clean_phone)
            async with self._lock:
                # Disconnect old pending if any
                old = self._pending_sessions.pop(telegram_id, None)
                if old and old.client.is_connected():
                    await old.client.disconnect()

                self._pending_sessions[telegram_id] = PendingAuthSession(
                    telegram_id=telegram_id,
                    client=client,
                    phone=clean_phone,
                    phone_code_hash=sent_code.phone_code_hash,
                )

            logger.info(f"Auth code requested successfully for user {telegram_id}")
            return AuthState(
                is_authorized=False,
                phone=clean_phone,
                phone_code_hash=sent_code.phone_code_hash,
                step="CODE",
            )
        except PhoneNumberInvalidError:
            await client.disconnect()
            raise AuthRequiredException("Номер телефона указан неверно.")
        except FloodWaitError as e:
            await client.disconnect()
            raise FloodWaitTimeoutException(e.seconds)
        except Exception as e:
            await client.disconnect()
            logger.error(f"Error requesting code for {telegram_id}: {str(e)}")
            raise AuthRequiredException("Ошибка при отправке запроса кода в Telegram.")

    async def submit_auth_code(self, telegram_id: int, code: str) -> Tuple[AuthState, Optional[str]]:
        """Step 2: Submits SMS/Telegram code; returns AuthState and optional encrypted session."""
        async with self._lock:
            pending = self._pending_sessions.get(telegram_id)

        if not pending or pending.is_expired:
            raise AuthRequiredException("Сессия авторизации истекла. Запросите код заново.")

        clean_code = code.strip().replace(" ", "")

        try:
            await pending.client.sign_in(
                phone=pending.phone,
                code=clean_code,
                phone_code_hash=pending.phone_code_hash,
            )
            # If successful, complete session creation
            return await self._finalize_login(telegram_id, pending)

        except SessionPasswordNeededError:
            # 2FA password required
            logger.info(f"User {telegram_id} requires 2FA password")
            return (
                AuthState(
                    is_authorized=False,
                    phone=pending.phone,
                    phone_code_hash=pending.phone_code_hash,
                    step="2FA",
                ),
                None,
            )
        except PhoneCodeInvalidError:
            raise AuthRequiredException("Неверный код подтверждения.")
        except PhoneCodeExpiredError:
            raise AuthRequiredException("Срок действия кода истёк. Запросите код заново.")
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds)

    async def submit_2fa_password(self, telegram_id: int, password: str) -> Tuple[AuthState, Optional[str]]:
        """Step 3: Submits 2FA cloud password if enabled."""
        async with self._lock:
            pending = self._pending_sessions.get(telegram_id)

        if not pending or pending.is_expired:
            raise AuthRequiredException("Сессия авторизации истекла. Пожалуйста, начните заново.")

        try:
            await pending.client.sign_in(password=password)
            return await self._finalize_login(telegram_id, pending)
        except PasswordHashInvalidError:
            raise AuthRequiredException("Неверный 2FA пароль.")
        except FloodWaitError as e:
            raise FloodWaitTimeoutException(e.seconds)

    async def _finalize_login(
        self, telegram_id: int, pending: PendingAuthSession
    ) -> Tuple[AuthState, str]:
        """Saves encrypted session file to disk and registers in DB."""
        # Telethon StringSession exported
        session_str = pending.client.session.save()

        # Retrieve user salt from DB
        salt = crypto_service.generate_salt()
        user = await db.get_or_create_user(telegram_id, salt=salt)
        user_salt = user.get("salt") or salt

        # Encrypt the session string
        encrypted_session = crypto_service.encrypt_string(session_str, user_salt)

        # Write to secure user directory
        user_session_dir = Path(settings.SESSION_DIR) / str(telegram_id)
        user_session_dir.mkdir(parents=True, exist_ok=True)
        session_file = user_session_dir / "account.enc"
        session_file.write_text(encrypted_session, encoding="utf-8")

        # Update database
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (telegram_id, session_path, is_active, updated_at)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    session_path = excluded.session_path,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, str(session_file)),
            )
            await conn.execute(
                "UPDATE users SET phone = ? WHERE telegram_id = ?",
                (pending.phone, telegram_id),
            )
            await conn.commit()

        # Audit log
        await db.append_audit_log(telegram_id, action="ACCOUNT_AUTHORIZED")

        # Disconnect transient client
        if pending.client.is_connected():
            await pending.client.disconnect()

        async with self._lock:
            self._pending_sessions.pop(telegram_id, None)

        logger.info(f"User {telegram_id} successfully authenticated and session encrypted.")
        return (
            AuthState(
                is_authorized=True,
                phone=pending.phone,
                step="AUTHORIZED",
            ),
            str(session_file),
        )


auth_manager = AuthManager()
