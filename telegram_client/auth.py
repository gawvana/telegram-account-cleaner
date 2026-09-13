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
from domain.models import AuthState, AuthStatus
from services.crypto_service import crypto_service
from telegram_client.exceptions import AuthRequiredException, FloodWaitTimeoutException
from utils.logger import logger


class PendingAuthSession:
    """Holds in-memory transient Telethon client during the authentication handshake."""

    def __init__(
        self,
        telegram_id: int,
        client: TelegramClient,
        phone: str,
        phone_code_hash: str,
    ):
        self.telegram_id = telegram_id
        self.client = client
        self.phone = phone
        self.phone_code_hash = phone_code_hash
        self.status = AuthStatus.WAITING_FOR_CODE
        self.created_at = time.time()
        self.timeout_seconds = settings.AUTH_TIMEOUT_SECONDS

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.timeout_seconds

    @property
    def expires_at(self) -> float:
        return self.created_at + self.timeout_seconds


class AuthManager:
    """
    Manages the secure Telethon login process with explicit state machine,
    strict per-user concurrency locks, and automatic transient session cleanup.
    """

    def __init__(self):
        self._pending_sessions: Dict[int, PendingAuthSession] = {}
        self._user_locks: Dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_user_lock(self, telegram_id: int) -> asyncio.Lock:
        async with self._global_lock:
            if telegram_id not in self._user_locks:
                self._user_locks[telegram_id] = asyncio.Lock()
            return self._user_locks[telegram_id]

    async def cleanup_expired(self) -> None:
        """Closes and purges transient clients exceeding AUTH_TIMEOUT_SECONDS."""
        to_disconnect = []
        async with self._global_lock:
            expired_ids = [uid for uid, s in self._pending_sessions.items() if s.is_expired]
            for uid in expired_ids:
                pending = self._pending_sessions.pop(uid, None)
                if pending and pending.client and pending.client.is_connected():
                    to_disconnect.append(pending.client)
                logger.info(f"Purged expired transient auth session for user {uid}")

        for client in to_disconnect:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def get_auth_state(self, telegram_id: int) -> AuthState:
        """Determines the current precise AuthStatus for the user."""
        await self.cleanup_expired()

        async with self._global_lock:
            pending = self._pending_sessions.get(telegram_id)

        if pending:
            if pending.status == AuthStatus.WAITING_FOR_CODE:
                return AuthState(
                    status=AuthStatus.WAITING_FOR_CODE,
                    is_authorized=False,
                    phone=pending.phone,
                    phone_code_hash=pending.phone_code_hash,
                    step="CODE",
                    expires_at=pending.expires_at,
                )
            elif pending.status == AuthStatus.WAITING_FOR_2FA:
                return AuthState(
                    status=AuthStatus.WAITING_FOR_2FA,
                    is_authorized=False,
                    phone=pending.phone,
                    phone_code_hash=pending.phone_code_hash,
                    step="2FA",
                    expires_at=pending.expires_at,
                )
            elif pending.status == AuthStatus.AUTHENTICATING:
                return AuthState(
                    status=AuthStatus.AUTHENTICATING,
                    is_authorized=False,
                    phone=pending.phone,
                    step="AUTHENTICATING",
                )

        # Check DB for active session
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT session_path, is_active FROM sessions WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cursor.fetchone()
            if row and row["is_active"]:
                p = Path(row["session_path"])
                if p.exists() and p.stat().st_size > 0:
                    u_cursor = await conn.execute(
                        "SELECT phone FROM users WHERE telegram_id = ?", (telegram_id,)
                    )
                    u_row = await u_cursor.fetchone()
                    phone = u_row["phone"] if u_row else None
                    return AuthState(
                        status=AuthStatus.CONNECTED,
                        is_authorized=True,
                        phone=phone,
                        step="AUTHORIZED",
                    )

        return AuthState(
            status=AuthStatus.DISCONNECTED,
            is_authorized=False,
            step="PHONE",
        )

    async def _cancel_auth_locked(self, telegram_id: int) -> None:
        """Internal cancellation cleanup executed when the caller already holds the user lock."""
        async with self._global_lock:
            pending = self._pending_sessions.pop(telegram_id, None)
        if pending and pending.client and pending.client.is_connected():
            try:
                await pending.client.disconnect()
            except Exception:
                pass
        logger.info(f"User {telegram_id} auth handshake safely cancelled (locked).")

    async def cancel_auth(self, telegram_id: int) -> None:
        """Explicitly cancels pending authentication and frees client resources."""
        lock = await self._get_user_lock(telegram_id)
        async with lock:
            await self._cancel_auth_locked(telegram_id)

    async def request_phone_code(
        self,
        telegram_id: int,
        phone: str,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ) -> AuthState:
        """
        Step 1: Connects Telethon client and requests verification code from Telegram.
        Backend uses server-configured API_ID and API_HASH by default — never forces user to enter credentials.
        """
        lock = await self._get_user_lock(telegram_id)
        if lock.locked():
            raise AuthRequiredException("Процесс авторизации уже выполняется. Пожалуйста, подождите.")

        async with lock:
            await self.cleanup_expired()

            clean_phone = "".join(filter(lambda c: c.isdigit() or c == "+", phone))
            if len(clean_phone) < 7:
                raise AuthRequiredException("Некорректный формат номера телефона.")

            # Create transient in-memory client
            effective_api_id = api_id or settings.effective_api_id
            effective_api_hash = api_hash or settings.effective_api_hash
            client = TelegramClient(
                StringSession(),
                effective_api_id,
                effective_api_hash,
            )

            try:
                await asyncio.wait_for(client.connect(), timeout=30.0)
                sent_code = await asyncio.wait_for(client.send_code_request(clean_phone), timeout=30.0)

                old_client = None
                async with self._global_lock:
                    old = self._pending_sessions.pop(telegram_id, None)
                    if old and old.client and old.client.is_connected():
                        old_client = old.client

                    pending = PendingAuthSession(
                        telegram_id=telegram_id,
                        client=client,
                        phone=clean_phone,
                        phone_code_hash=sent_code.phone_code_hash,
                    )
                    self._pending_sessions[telegram_id] = pending

                if old_client:
                    try:
                        await old_client.disconnect()
                    except Exception:
                        pass

                logger.info(f"Auth code requested successfully for user {telegram_id}")
                return AuthState(
                    status=AuthStatus.WAITING_FOR_CODE,
                    is_authorized=False,
                    phone=clean_phone,
                    phone_code_hash=sent_code.phone_code_hash,
                    step="CODE",
                    expires_at=pending.expires_at,
                )

            except PhoneNumberInvalidError:
                if client.is_connected():
                    await client.disconnect()
                raise AuthRequiredException("Номер телефона указан неверно.")
            except FloodWaitError as e:
                if client.is_connected():
                    await client.disconnect()
                raise FloodWaitTimeoutException(e.seconds)
            except Exception as e:
                if client.is_connected():
                    await client.disconnect()
                logger.error(f"Error requesting code for {telegram_id}: {str(e)}")
                raise AuthRequiredException(f"Ошибка запроса кода: {str(e)}")

    async def submit_auth_code(
        self, telegram_id: int, code: str
    ) -> Tuple[AuthState, Optional[str]]:
        """Step 2: Submits code; returns AuthState and optional encrypted session file path."""
        lock = await self._get_user_lock(telegram_id)
        async with lock:
            async with self._global_lock:
                pending = self._pending_sessions.get(telegram_id)

            if not pending:
                raise AuthRequiredException("Сессия авторизации не найдена. Начните сначала.")

            if pending.is_expired:
                await self._cancel_auth_locked(telegram_id)
                raise AuthRequiredException("Время ожидания кода истекло (5 минут). Запросите код заново.")

            clean_code = code.strip().replace(" ", "")
            if not clean_code:
                raise AuthRequiredException("Введите код подтверждения.")

            pending.status = AuthStatus.AUTHENTICATING

            try:
                await asyncio.wait_for(
                    pending.client.sign_in(
                        phone=pending.phone,
                        code=clean_code,
                        phone_code_hash=pending.phone_code_hash,
                    ),
                    timeout=30.0,
                )
                return await self._finalize_login(telegram_id, pending)

            except asyncio.TimeoutError:
                await self._cancel_auth_locked(telegram_id)
                raise AuthRequiredException("Время ожидания ответа Telegram истекло. Попробуйте запросить код снова.")
            except SessionPasswordNeededError:
                logger.info(f"User {telegram_id} requires 2FA password")
                pending.status = AuthStatus.WAITING_FOR_2FA
                return (
                    AuthState(
                        status=AuthStatus.WAITING_FOR_2FA,
                        is_authorized=False,
                        phone=pending.phone,
                        phone_code_hash=pending.phone_code_hash,
                        step="2FA",
                        expires_at=pending.expires_at,
                    ),
                    None,
                )
            except PhoneCodeInvalidError:
                pending.status = AuthStatus.WAITING_FOR_CODE
                raise AuthRequiredException("Неверный код подтверждения.")
            except PhoneCodeExpiredError:
                await self._cancel_auth_locked(telegram_id)
                raise AuthRequiredException("Срок действия кода истёк. Запросите код заново.")
            except FloodWaitError as e:
                raise FloodWaitTimeoutException(e.seconds)
            except Exception as e:
                logger.error(f"Error verifying code for {telegram_id}: {e}")
                raise AuthRequiredException(f"Ошибка проверки кода: {str(e)}")

    async def submit_2fa_password(
        self, telegram_id: int, password: str
    ) -> Tuple[AuthState, Optional[str]]:
        """Step 3: Submits 2FA cloud password if required."""
        lock = await self._get_user_lock(telegram_id)
        async with lock:
            async with self._global_lock:
                pending = self._pending_sessions.get(telegram_id)

            if not pending:
                raise AuthRequiredException("Сессия авторизации не найдена. Начните сначала.")

            if pending.is_expired:
                await self._cancel_auth_locked(telegram_id)
                raise AuthRequiredException("Время ожидания истекло. Начните заново.")

            if pending.status != AuthStatus.WAITING_FOR_2FA:
                raise AuthRequiredException("2FA пароль сейчас не требуется.")

            pending.status = AuthStatus.AUTHENTICATING

            try:
                await asyncio.wait_for(
                    pending.client.sign_in(password=password),
                    timeout=30.0,
                )
                return await self._finalize_login(telegram_id, pending)
            except asyncio.TimeoutError:
                await self._cancel_auth_locked(telegram_id)
                raise AuthRequiredException("Время ожидания ответа Telegram истекло. Попробуйте снова.")
            except PasswordHashInvalidError:
                pending.status = AuthStatus.WAITING_FOR_2FA
                raise AuthRequiredException("Неверный 2FA пароль.")
            except FloodWaitError as e:
                pending.status = AuthStatus.WAITING_FOR_2FA
                raise FloodWaitTimeoutException(e.seconds)
            except Exception as e:
                pending.status = AuthStatus.WAITING_FOR_2FA
                logger.error(f"Error checking 2FA password for {telegram_id}: {e}")
                raise AuthRequiredException(f"Ошибка проверки пароля: {str(e)}")

    async def _finalize_login(
        self, telegram_id: int, pending: PendingAuthSession
    ) -> Tuple[AuthState, str]:
        """Saves encrypted session to sessions/users/<user_id>/session.enc and registers in DB."""
        session_str = pending.client.session.save()

        # Generate per-user salt and encrypt
        salt = crypto_service.generate_salt()
        user = await db.get_or_create_user(telegram_id, salt=salt)
        user_salt = user.get("salt") or salt
        encrypted_session = crypto_service.encrypt_string(session_str, user_salt)

        # Write to isolated per-user directory
        user_session_dir = Path(settings.SESSION_DIR) / "users" / str(telegram_id)
        user_session_dir.mkdir(parents=True, exist_ok=True)
        session_file = user_session_dir / "session.enc"
        session_file.write_text(encrypted_session, encoding="utf-8")

        # Mask phone to prevent plaintext PII storage
        clean_phone = pending.phone
        if len(clean_phone) >= 7:
            masked_phone = clean_phone[:3] + "***" + clean_phone[-4:]
        else:
            masked_phone = "***"

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
                (masked_phone, telegram_id),
            )
            await conn.commit()

        await db.append_audit_log(telegram_id, action="ACCOUNT_AUTHORIZED")

        # Safely disconnect transient client
        if pending.client and pending.client.is_connected():
            await pending.client.disconnect()

        async with self._global_lock:
            self._pending_sessions.pop(telegram_id, None)

        logger.info(f"User {telegram_id} successfully authenticated and session encrypted.")
        return (
            AuthState(
                status=AuthStatus.CONNECTED,
                is_authorized=True,
                phone=masked_phone,
                step="AUTHORIZED",
            ),
            str(session_file),
        )


auth_manager = AuthManager()
