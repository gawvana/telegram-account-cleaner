import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import settings
from database import db
from services.crypto_service import crypto_service
from telegram_client.exceptions import (
    AuthRequiredException,
    ConcurrentJobError,
    SessionCorruptedError,
)
from utils.logger import logger


class ClientManager:
    """Manages secure loading, per-user locks, and lifecycle of Telethon clients."""

    def __init__(self):
        self._user_locks: Dict[int, asyncio.Lock] = {}
        self._active_clients: Dict[int, TelegramClient] = {}
        self._global_lock = asyncio.Lock()

    async def get_user_lock(self, telegram_id: int) -> asyncio.Lock:
        async with self._global_lock:
            if telegram_id not in self._user_locks:
                self._user_locks[telegram_id] = asyncio.Lock()
            return self._user_locks[telegram_id]

    async def has_active_session(self, telegram_id: int) -> bool:
        """Checks whether the user has a valid encrypted session on disk."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT session_path, is_active FROM sessions WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cursor.fetchone()
            if not row or not row["is_active"]:
                return False
            return Path(row["session_path"]).exists()

    async def load_client(self, telegram_id: int) -> TelegramClient:
        """Decrypts session from disk into an in-memory Telethon client."""
        async with db.get_connection() as conn:
            user_cursor = await conn.execute(
                "SELECT salt FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            user_row = await user_cursor.fetchone()
            if not user_row:
                raise AuthRequiredException("Пользователь не найден в базе данных.")

            user_salt = user_row["salt"]

            sess_cursor = await conn.execute(
                "SELECT session_path, is_active FROM sessions WHERE telegram_id = ?",
                (telegram_id,),
            )
            sess_row = await sess_cursor.fetchone()
            if not sess_row or not sess_row["is_active"]:
                raise AuthRequiredException("Аккаунт не подключён. Пожалуйста, пройдите авторизацию.")

            session_file = Path(sess_row["session_path"])
            if not session_file.exists():
                raise AuthRequiredException("Файл сессии не найден. Пройдите авторизацию заново.")

        try:
            encrypted_data = session_file.read_text(encoding="utf-8")
            decrypted_str = crypto_service.decrypt_string(encrypted_data, user_salt)
        except Exception as e:
            logger.error(f"Failed to decrypt session for {telegram_id}: {e}")
            raise SessionCorruptedError("Не удалось расшифровать сессию. Возможно, изменился мастер-ключ.")

        client = TelegramClient(
            StringSession(decrypted_str),
            settings.effective_api_id,
            settings.effective_api_hash,
        )
        return client

    @asynccontextmanager
    async def get_client(self, telegram_id: int) -> AsyncGenerator[TelegramClient, None]:
        """Provides a locked, authenticated Telethon client context."""
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

    async def logout_user(self, telegram_id: int) -> None:
        """Securely deletes session file and marks session as inactive."""
        lock = await self.get_user_lock(telegram_id)
        async with lock:
            async with db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT session_path FROM sessions WHERE telegram_id = ?", (telegram_id,)
                )
                row = await cursor.fetchone()
                if row:
                    path = Path(row["session_path"])
                    if path.exists():
                        # Overwrite with zeros before unlinking
                        path.write_bytes(b"\x00" * path.stat().st_size)
                        path.unlink()
                await conn.execute(
                    "UPDATE sessions SET is_active = 0 WHERE telegram_id = ?", (telegram_id,)
                )
                await conn.commit()

            await db.append_audit_log(telegram_id, action="ACCOUNT_LOGOUT")
            logger.info(f"User {telegram_id} session securely erased.")


client_manager = ClientManager()
