import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class RepeaterService:
    def __init__(self):
        # (user_id, chat_id, target_user_id) -> state dict
        self._active_targets: Dict[Tuple[int, int, int], dict] = {}
        self._stats: Dict[int, dict] = {}
    
    def set_target(self, user_id: int, chat_id: int, target_user_id: int, cooldown_seconds: int = 3, max_messages: int = 10):
        key = (user_id, chat_id, target_user_id)
        self._active_targets[key] = {
            "cooldown": max(2, cooldown_seconds),
            "max": max_messages,
            "count": 0,
            "last_time": 0
        }
        if user_id not in self._stats:
            self._stats[user_id] = {"repeated_count": 0}

    def remove_target(self, user_id: int, chat_id: int, target_user_id: int):
        key = (user_id, chat_id, target_user_id)
        if key in self._active_targets:
            del self._active_targets[key]

    def get_targets(self, user_id: int) -> list:
        targets = []
        for (u_id, c_id, t_id), state in self._active_targets.items():
            if u_id == user_id:
                targets.append({
                    "chat_id": c_id,
                    "target_user_id": t_id,
                    "cooldown_seconds": state["cooldown"],
                    "max_messages": state["max"],
                    "count": state["count"]
                })
        return targets

    def get_stats(self, user_id: int) -> dict:
        stats = self._stats.get(user_id, {"repeated_count": 0})
        active_chats = len(set(c_id for (u_id, c_id, t_id) in self._active_targets.keys() if u_id == user_id))
        return {
            "repeated_count": stats["repeated_count"],
            "active_chats": active_chats
        }

    async def process_incoming_message(self, user_id: int, event, client):
        if event.out:
            return
            
        sender = await event.get_sender()
        if not sender or getattr(sender, 'bot', False):
            return

        chat_id = event.chat_id
        target_user_id = sender.id
        key = (user_id, chat_id, target_user_id)
        
        state = self._active_targets.get(key)
        if not state:
            return

        now = time.time()
        if now - state["last_time"] < state["cooldown"]:
            return

        if state["count"] >= state["max"]:
            self.remove_target(user_id, chat_id, target_user_id)
            return

        try:
            state["last_time"] = now
            state["count"] += 1
            if user_id in self._stats:
                self._stats[user_id]["repeated_count"] += 1
            
            await client.send_message(chat_id, event.message)
        except Exception as e:
            logger.error(f"Repeater error: {e}")

repeater_service = RepeaterService()
