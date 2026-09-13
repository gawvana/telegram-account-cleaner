from typing import Any, Dict, List, Optional
from database import db
from utils.logger import logger


class WhitelistService:
    """Manages chat and channel whitelist with pattern rules and export/import."""

    async def add_to_whitelist(
        self,
        telegram_id: int,
        chat_id: int,
        title: str = "",
        username: Optional[str] = None,
        rule_pattern: Optional[str] = None,
    ) -> bool:
        """Adds a chat or pattern rule to user's whitelist."""
        async with db.get_connection() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO whitelist (telegram_id, chat_id, title, username, rule_pattern)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(telegram_id, chat_id) DO UPDATE SET
                        title = excluded.title,
                        username = excluded.username,
                        rule_pattern = excluded.rule_pattern
                    """,
                    (telegram_id, chat_id, title, username, rule_pattern),
                )
                await conn.commit()
                logger.info(f"User {telegram_id} added chat {chat_id} to whitelist")
                return True
            except Exception as e:
                logger.error(f"Error adding to whitelist: {e}")
                return False

    async def remove_from_whitelist(self, telegram_id: int, chat_id: int) -> bool:
        """Removes a chat from user's whitelist."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM whitelist WHERE telegram_id = ? AND chat_id = ?",
                (telegram_id, chat_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def list_whitelist(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Lists all whitelisted items for a user."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM whitelist WHERE telegram_id = ? ORDER BY added_at DESC",
                (telegram_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def is_whitelisted(self, telegram_id: int, chat_id: int) -> bool:
        """Checks if a chat_id is explicitly whitelisted."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM whitelist WHERE telegram_id = ? AND chat_id = ?",
                (telegram_id, chat_id),
            )
            row = await cursor.fetchone()
            return bool(row)

    async def export_whitelist(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Exports user whitelist for backup."""
        items = await self.list_whitelist(telegram_id)
        # Sanitize for export
        return [
            {
                "chat_id": item["chat_id"],
                "title": item["title"],
                "username": item["username"],
                "rule_pattern": item["rule_pattern"],
            }
            for item in items
        ]

    async def import_whitelist(self, telegram_id: int, items: List[Dict[str, Any]]) -> int:
        """Imports whitelist items from external JSON payload."""
        imported_count = 0
        for item in items:
            chat_id = item.get("chat_id")
            if not chat_id:
                continue
            success = await self.add_to_whitelist(
                telegram_id=telegram_id,
                chat_id=int(chat_id),
                title=item.get("title", ""),
                username=item.get("username"),
                rule_pattern=item.get("rule_pattern"),
            )
            if success:
                imported_count += 1
        return imported_count


whitelist_service = WhitelistService()
