from typing import List, Optional
from datetime import datetime, timedelta
from database import db
from features.deleted_messages.models import DeletedMessageDTO, ArchiveStatsDTO
import json

class DeletedMessagesService:
    async def save_deleted(self, telegram_id: int, chat_id: int, message_id: int, sender_id: Optional[int] = None, sender_name: Optional[str] = None, chat_title: Optional[str] = None, message_type: str = 'text', text_content: Optional[str] = None, media_metadata: Optional[str] = None, original_date: Optional[datetime] = None) -> int:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO deleted_messages (
                    telegram_id, chat_id, message_id, sender_id, sender_name,
                    chat_title, message_type, text_content, media_metadata, original_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (telegram_id, chat_id, message_id, sender_id, sender_name, chat_title, message_type, text_content, media_metadata, original_date)
            )
            msg_id = cursor.lastrowid
            await conn.commit()
            return msg_id

    async def get_messages(self, telegram_id: int, chat_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[DeletedMessageDTO]:
        async with db.get_connection() as conn:
            if chat_id:
                cursor = await conn.execute(
                    "SELECT * FROM deleted_messages WHERE telegram_id = ? AND chat_id = ? ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
                    (telegram_id, chat_id, limit, offset)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM deleted_messages WHERE telegram_id = ? ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
                    (telegram_id, limit, offset)
                )
            rows = await cursor.fetchall()
            return [DeletedMessageDTO(**dict(row)) for row in rows]
            
    async def get_stats(self, telegram_id: int) -> ArchiveStatsDTO:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    COUNT(id) as total_messages,
                    COUNT(DISTINCT chat_id) as total_chats,
                    MIN(deleted_at) as oldest,
                    MAX(deleted_at) as newest
                FROM deleted_messages
                WHERE telegram_id = ?
                """,
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                return ArchiveStatsDTO(
                    total_messages=row['total_messages'] or 0,
                    total_chats=row['total_chats'] or 0,
                    oldest_message_date=row['oldest'],
                    newest_message_date=row['newest']
                )
            return ArchiveStatsDTO(total_messages=0, total_chats=0)

    async def cleanup(self, telegram_id: int, retention_days: Optional[int] = None) -> int:
        if retention_days is None:
            return 0
            
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM deleted_messages WHERE telegram_id = ? AND deleted_at < ?",
                (telegram_id, cutoff_date)
            )
            count = cursor.rowcount
            await conn.commit()
            return count

    async def search(self, telegram_id: int, query: str, limit: int = 50) -> List[DeletedMessageDTO]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM deleted_messages WHERE telegram_id = ? AND text_content LIKE ? ORDER BY deleted_at DESC LIMIT ?",
                (telegram_id, f"%{query}%", limit)
            )
            rows = await cursor.fetchall()
            return [DeletedMessageDTO(**dict(row)) for row in rows]

deleted_messages_service = DeletedMessagesService()
