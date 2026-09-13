from typing import List, Optional
from database import db
from features.edited_messages.models import EditedMessageDTO, EditVersionDTO, EditStatsDTO

class EditedMessagesService:
    async def save_edit(self, telegram_id: int, chat_id: int, message_id: int, sender_id: Optional[int] = None, sender_name: Optional[str] = None, chat_title: Optional[str] = None, old_text: Optional[str] = None, new_text: Optional[str] = None) -> int:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT MAX(edit_version) as max_version FROM edited_messages WHERE telegram_id = ? AND chat_id = ? AND message_id = ?",
                (telegram_id, chat_id, message_id)
            )
            row = await cursor.fetchone()
            edit_version = (row['max_version'] or 0) + 1

            cursor = await conn.execute(
                """
                INSERT INTO edited_messages (
                    telegram_id, chat_id, message_id, sender_id, sender_name,
                    chat_title, old_text, new_text, edit_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (telegram_id, chat_id, message_id, sender_id, sender_name, chat_title, old_text, new_text, edit_version)
            )
            msg_id = cursor.lastrowid
            await conn.commit()
            return msg_id

    async def get_messages(self, telegram_id: int, chat_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[EditedMessageDTO]:
        async with db.get_connection() as conn:
            if chat_id:
                cursor = await conn.execute(
                    "SELECT * FROM edited_messages WHERE telegram_id = ? AND chat_id = ? ORDER BY edited_at DESC LIMIT ? OFFSET ?",
                    (telegram_id, chat_id, limit, offset)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM edited_messages WHERE telegram_id = ? ORDER BY edited_at DESC LIMIT ? OFFSET ?",
                    (telegram_id, limit, offset)
                )
            rows = await cursor.fetchall()
            return [EditedMessageDTO(**dict(row)) for row in rows]

    async def get_history(self, telegram_id: int, chat_id: int, message_id: int) -> List[EditVersionDTO]:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT old_text, new_text, edit_version, edited_at FROM edited_messages WHERE telegram_id = ? AND chat_id = ? AND message_id = ? ORDER BY edit_version ASC",
                (telegram_id, chat_id, message_id)
            )
            rows = await cursor.fetchall()
            return [EditVersionDTO(**dict(row)) for row in rows]

    async def get_stats(self, telegram_id: int) -> EditStatsDTO:
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    COUNT(id) as total_edits,
                    COUNT(DISTINCT message_id) as unique_messages
                FROM edited_messages
                WHERE telegram_id = ?
                """,
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                return EditStatsDTO(
                    total_edits=row['total_edits'] or 0,
                    unique_messages_edited=row['unique_messages'] or 0
                )
            return EditStatsDTO(total_edits=0, unique_messages_edited=0)

edited_messages_service = EditedMessagesService()
