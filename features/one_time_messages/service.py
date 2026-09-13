import asyncio
import time
from typing import Dict
from telethon import TelegramClient

class OneTimeMessageService:
    def __init__(self):
        # user_id -> stats
        self.stats: Dict[int, Dict[str, int]] = {}
        self.tasks: set = set()

    def _init_stats(self, user_id: int):
        if user_id not in self.stats:
            self.stats[user_id] = {"sent_count": 0, "deleted_count": 0}

    async def _delete_later(self, client: TelegramClient, chat_id: int, message_id: int, delay: int, user_id: int):
        await asyncio.sleep(delay)
        try:
            await client.delete_messages(chat_id, message_id)
            self._init_stats(user_id)
            self.stats[user_id]["deleted_count"] += 1
        except Exception:
            pass

    async def send_temporary_message(self, user_id: int, client: TelegramClient, chat_id: int, text: str, auto_delete_seconds: int) -> dict:
        message = await client.send_message(chat_id, text)
        self._init_stats(user_id)
        self.stats[user_id]["sent_count"] += 1
        
        task = asyncio.create_task(self._delete_later(client, chat_id, message.id, auto_delete_seconds, user_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        
        return {
            "message_id": message.id,
            "chat_id": chat_id,
            "expires_at": time.time() + auto_delete_seconds
        }

    async def get_stats(self, user_id: int) -> dict:
        self._init_stats(user_id)
        return self.stats[user_id]

one_time_message_service = OneTimeMessageService()
