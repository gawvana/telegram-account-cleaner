import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import settings
from database import db
from services.crypto_service import crypto_service
from telegram_client.base import ITelegramClientAdapter
from telegram_client.exceptions import (
    AuthRequiredException,
    ConcurrentJobError,
    SessionCorruptedError,
)
from telegram_client.telethon_adapter import TelethonAdapter
from utils.logger import logger


class ClientManager:
    """Manages secure loading, per-user locks, and lifecycle of Telegram client adapters."""

    def __init__(self):
        self._user_locks: Dict[int, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_user_lock(self, telegram_id: int) -> asyncio.Lock:
        async with self._global_lock:
            if telegram_id not in self._user_locks:
                self._user_locks[telegram_id] = asyncio.Lock()
            return self._user_locks[telegram_id]

    def get_user_session_dir(self, telegram_id: int) -> Path:
        """Returns isolated session directory for user."""
        return Path(settings.SESSION_DIR) / "users" / str(telegram_id)

    async def has_active_session(self, telegram_id: int) -> bool:
        """Checks whether the user has a valid encrypted session in DB or on disk."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT session_path, session_data, is_active FROM sessions WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cursor.fetchone()
            if not row or not row["is_active"]:
                return False
            # Check DB stored session_data first
            if "session_data" in row.keys() and row["session_data"] and len(row["session_data"]) > 0:
                return True
            # Fall back to disk file
            if row["session_path"]:
                p = Path(row["session_path"])
                return p.exists() and p.stat().st_size > 0
            return False

    async def load_client(self, telegram_id: int) -> TelegramClient:
        """Decrypts session from database or disk into an in-memory Telethon client."""
        async with db.get_connection() as conn:
            user_cursor = await conn.execute(
                "SELECT salt FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            user_row = await user_cursor.fetchone()
            if not user_row:
                raise AuthRequiredException("Пользователь не найден в базе данных.")

            user_salt = user_row["salt"]

            sess_cursor = await conn.execute(
                "SELECT session_path, session_data, is_active FROM sessions WHERE telegram_id = ?",
                (telegram_id,),
            )
            sess_row = await sess_cursor.fetchone()
            if not sess_row or not sess_row["is_active"]:
                raise AuthRequiredException("Аккаунт не подключён. Пожалуйста, пройдите авторизацию.")

            encrypted_data = None
            if "session_data" in sess_row.keys() and sess_row["session_data"] and len(sess_row["session_data"]) > 0:
                encrypted_data = sess_row["session_data"]
            else:
                session_file = Path(sess_row["session_path"]) if sess_row["session_path"] else None
                if session_file and session_file.exists():
                    encrypted_data = session_file.read_text(encoding="utf-8")
                else:
                    raise AuthRequiredException("Файл сессии не найден. Пройдите авторизацию заново.")

        try:
            decrypted_str = crypto_service.decrypt_string(encrypted_data, user_salt)
        except Exception as e:
            logger.error(f"Failed to decrypt session for {telegram_id}: {e}")
            raise SessionCorruptedError("Не удалось расшифровать сессию. Возможно, изменился мастер-ключ.")

        # Check for user credentials encrypted at rest
        custom_cred = await db.get_user_credentials(telegram_id)
        api_id = None
        api_hash = None
        if custom_cred and custom_cred.get("encrypted_api_id") and custom_cred.get("encrypted_api_hash"):
            try:
                decrypted_api_id = crypto_service.decrypt_string(custom_cred["encrypted_api_id"], user_salt)
                api_id = int(decrypted_api_id)
                api_hash = crypto_service.decrypt_string(custom_cred["encrypted_api_hash"], user_salt)
            except Exception as e:
                logger.warning(f"Failed to decrypt credentials for user {telegram_id}: {e}")

        # Only allow test credentials during pytest runs
        if not api_id or not api_hash:
            if settings.effective_api_id and settings.effective_api_hash:
                api_id = settings.effective_api_id
                api_hash = settings.effective_api_hash

        if not api_id or not api_hash:
            raise AuthRequiredException("Для повторного подключения введите API ID и API Hash.")

        client = TelegramClient(
            StringSession(decrypted_str),
            api_id,
            api_hash,
        )
        return client

    @asynccontextmanager
    async def get_client(self, telegram_id: int) -> AsyncGenerator[TelegramClient, None]:
        """Provides a locked, authenticated Telethon client context (legacy support)."""
        lock = await self.get_user_lock(telegram_id)
        if lock.locked():
            raise ConcurrentJobError("На вашем аккаунте уже выполняется операция. Подождите её завершения.")

        async with lock:
            client = await self.load_client(telegram_id)
            await client.connect()
            try:
                if not await client.is_user_authorized():
                    raise AuthRequiredException("Сессия Telegram устарела. Авторизуйтесь заново.")
                yield client
            finally:
                if client.is_connected():
                    await client.disconnect()

    @asynccontextmanager
    async def get_adapter(self, telegram_id: int) -> AsyncGenerator[ITelegramClientAdapter, None]:
        """Provides a locked, authenticated ITelegramClientAdapter context."""
        lock = await self.get_user_lock(telegram_id)
        if lock.locked():
            raise ConcurrentJobError("На вашем аккаунте уже выполняется операция. Подождите её завершения.")

        async with lock:
            client = await self.load_client(telegram_id)
            adapter = TelethonAdapter(client)
            await adapter.connect()
            try:
                if not await adapter.is_user_authorized():
                    raise AuthRequiredException("Сессия Telegram устарела. Авторизуйтесь заново.")
                yield adapter
            finally:
                if await adapter.is_connected():
                    await adapter.disconnect()

    async def logout_user(self, telegram_id: int) -> None:
        """Securely deletes session file and marks session as inactive with path traversal protection."""
        lock = await self.get_user_lock(telegram_id)
        async with lock:
            async with db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT session_path FROM sessions WHERE telegram_id = ?", (telegram_id,)
                )
                row = await cursor.fetchone()
                if row and row["session_path"]:
                    target_path = Path(row["session_path"]).resolve()
                    session_base = Path(settings.SESSION_DIR).resolve()

                    # Prevent path traversal outside session_dir
                    try:
                        target_path.relative_to(session_base)
                        is_safe_path = True
                    except ValueError:
                        is_safe_path = False

                    if is_safe_path and target_path.exists():
                        # Overwrite with zeros before unlinking
                        try:
                            file_size = target_path.stat().st_size
                            target_path.write_bytes(b"\x00" * max(file_size, 64))
                            target_path.unlink()
                        except Exception as e:
                            logger.warning(f"Error securely shredding session file {target_path}: {e}")

                await conn.execute(
                    "UPDATE sessions SET is_active = 0, session_data = NULL WHERE telegram_id = ?", (telegram_id,)
                )
                await conn.commit()

            await db.append_audit_log(telegram_id, action="ACCOUNT_LOGOUT")
            logger.info(f"User {telegram_id} session securely erased.")


client_manager = ClientManager()
