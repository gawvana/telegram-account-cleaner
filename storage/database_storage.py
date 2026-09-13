from storage.base import BaseStorageAdapter
from database import db
import json

class DatabaseStorage(BaseStorageAdapter):
    async def save_archive_metadata(self, user_id: int, item_type: str, metadata: dict) -> int:
        # Uses database.db to record archive metadata
        if item_type == "deleted_message":
            return await db.save_deleted_message(
                telegram_id=user_id,
                chat_id=metadata.get("chat_id", 0),
                message_id=metadata.get("message_id", 0),
                sender_id=metadata.get("sender_id"),
                sender_name=metadata.get("sender_name"),
                chat_title=metadata.get("chat_title"),
                message_type=metadata.get("message_type", "text"),
                text_content=metadata.get("text_content"),
                media_metadata=json.dumps(metadata.get("media_metadata", {})),
                original_date=metadata.get("original_date")
            )
        return 0
    
    async def get_storage_usage(self, user_id: int) -> dict:
        return await db.get_storage_usage(user_id)
    
    async def cleanup_expired(self, user_id: int, retention_days: int) -> int:
        res = await db.cleanup_expired_archive(user_id)
        return res.get("deleted_removed", 0)
    
    async def check_quota(self, user_id: int) -> bool:
        usage = await db.get_storage_usage(user_id)
        used = usage.get("deleted_messages_bytes", 0)
        quota = usage.get("storage_quota_bytes", 104857600)
        return used < quota

storage = DatabaseStorage()
