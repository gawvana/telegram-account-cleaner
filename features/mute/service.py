import time
import logging
from typing import Dict, Tuple, List, Optional
from features.mute.models import MuteRuleCreate, MuteRuleDTO

logger = logging.getLogger(__name__)

class WhitelistService:
    async def is_whitelisted(self, user_id: int, chat_id: int) -> bool:
        from database import db
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM whitelist WHERE telegram_id = ? AND chat_id = ?",
                (user_id, chat_id)
            )
            return await cursor.fetchone() is not None

whitelist_service = WhitelistService()

class MuteService:
    def __init__(self):
        # (user_id, chat_id, target_user_id) -> expires_at
        self._active_mutes: Dict[Tuple[int, int, int], float] = {}

    async def add_mute(self, user_id: int, chat_id: int, target_user_id: int, duration_minutes: int = 60, reason: Optional[str] = None) -> None:
        if await whitelist_service.is_whitelisted(user_id, chat_id):
            logger.info(f"Cannot mute in {chat_id}, it is whitelisted.")
            return
            
        expires_at = time.time() + (duration_minutes * 60)
        self._active_mutes[(user_id, chat_id, target_user_id)] = expires_at

    def remove_mute(self, user_id: int, chat_id: int, target_user_id: int) -> bool:
        key = (user_id, chat_id, target_user_id)
        if key in self._active_mutes:
            del self._active_mutes[key]
            return True
        return False

    def get_active_mutes(self, user_id: int) -> List[MuteRuleDTO]:
        now = time.time()
        mutes = []
        keys_to_remove = []
        
        for (uid, cid, tid), expires_at in self._active_mutes.items():
            if uid == user_id:
                if expires_at < now:
                    keys_to_remove.append((uid, cid, tid))
                else:
                    mutes.append(MuteRuleDTO(
                        chat_id=cid,
                        target_user_id=tid,
                        duration_minutes=int((expires_at - now)/60),
                        expires_at=expires_at
                    ))
        
        for k in keys_to_remove:
            del self._active_mutes[k]
            
        return mutes

    def is_muted(self, user_id: int, chat_id: int, sender_id: int) -> bool:
        key = (user_id, chat_id, sender_id)
        expires_at = self._active_mutes.get(key)
        if expires_at:
            if time.time() < expires_at:
                return True
            else:
                del self._active_mutes[key]
        return False

    async def process_incoming_message(self, user_id: int, event, client) -> None:
        chat_id = event.chat_id
        sender_id = getattr(event, 'sender_id', None)
        
        if not chat_id or not sender_id:
            return
            
        if self.is_muted(user_id, chat_id, sender_id):
            if await whitelist_service.is_whitelisted(user_id, chat_id):
                return
                
            try:
                await event.delete()
                
                from database import db
                async with db.get_connection() as conn:
                    await conn.execute(
                        "INSERT INTO feature_activity (telegram_id, feature_id, action, details) VALUES (?, ?, ?, ?)",
                        (user_id, "mute", "deleted_message", f"Deleted message from {sender_id} in {chat_id}")
                    )
                    await conn.commit()
            except Exception as e:
                logger.error(f"Failed to delete muted user message: {e}")

mute_service = MuteService()
