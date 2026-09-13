import time
import hashlib
from typing import Dict, List, Set, Any
from telethon import events

class SpamProtectionService:
    def __init__(self):
        # user_id -> {chat_id -> SpamRuleDTO}
        self.rules: Dict[int, Dict[int, Any]] = {}
        # user_id -> {chat_id -> {sender_id -> [timestamps]}}
        self.message_history: Dict[int, Dict[int, Dict[int, List[float]]]] = {}
        # user_id -> {chat_id -> set of recent hashes}
        self.recent_hashes: Dict[int, Dict[int, Set[str]]] = {}
        
        # user_id -> stats
        self.stats: Dict[int, Dict[str, int]] = {}

    def _init_stats(self, user_id: int):
        if user_id not in self.stats:
            self.stats[user_id] = {
                "actions_taken": 0,
                "messages_inspected": 0,
                "spam_detected": 0
            }

    async def set_rule(self, user_id: int, chat_id: int, rule_data: dict) -> None:
        if user_id not in self.rules:
            self.rules[user_id] = {}
        self.rules[user_id][chat_id] = rule_data

    async def get_rules(self, user_id: int) -> Dict[int, Any]:
        return self.rules.get(user_id, {})

    async def delete_rule(self, user_id: int, chat_id: int) -> bool:
        if user_id in self.rules and chat_id in self.rules[user_id]:
            del self.rules[user_id][chat_id]
            return True
        return False

    async def inspect_message(self, user_id: int, event: events.NewMessage.Event, client) -> bool:
        self._init_stats(user_id)
        self.stats[user_id]["messages_inspected"] += 1

        chat_id = event.chat_id
        if user_id not in self.rules or chat_id not in self.rules[user_id]:
            return False
        
        rule = self.rules[user_id][chat_id]
        if not rule.get("is_active", True):
            return False

        sender = await event.get_sender()
        if not sender:
            return False
            
        sender_id = sender.id

        # Safety check: Whitelist
        try:
            from features.whitelist.service import whitelist_service
            is_whitelisted = await whitelist_service.is_whitelisted(user_id, chat_id) or await whitelist_service.is_whitelisted(user_id, sender_id)
            if is_whitelisted:
                return False
        except ImportError:
            pass

        text = event.message.text or ""
        is_spam = False

        # Duplicate detection
        msg_hash = hashlib.md5(text.encode()).hexdigest()
        if user_id not in self.recent_hashes:
            self.recent_hashes[user_id] = {}
        if chat_id not in self.recent_hashes[user_id]:
            self.recent_hashes[user_id][chat_id] = set()
            
        if msg_hash in self.recent_hashes[user_id][chat_id]:
            is_spam = True
        else:
            self.recent_hashes[user_id][chat_id].add(msg_hash)
            if len(self.recent_hashes[user_id][chat_id]) > 100:
                self.recent_hashes[user_id][chat_id].pop()

        # Check forwards
        if not is_spam and rule.get("delete_forwards") and event.message.fwd_from:
            is_spam = True
            
        # Check links
        if not is_spam and rule.get("delete_links") and ("http://" in text or "https://" in text or "t.me/" in text):
            is_spam = True

        # Check keywords
        if not is_spam and rule.get("block_keywords"):
            lower_text = text.lower()
            for kw in rule["block_keywords"]:
                if kw.lower() in lower_text:
                    is_spam = True
                    break

        # Check rate limit
        now = time.time()
        if user_id not in self.message_history:
            self.message_history[user_id] = {}
        if chat_id not in self.message_history[user_id]:
            self.message_history[user_id][chat_id] = {}
        if sender_id not in self.message_history[user_id][chat_id]:
            self.message_history[user_id][chat_id][sender_id] = []
        
        history = self.message_history[user_id][chat_id][sender_id]
        history = [t for t in history if now - t < 60]
        history.append(now)
        self.message_history[user_id][chat_id][sender_id] = history
        
        if len(history) > rule.get("max_messages_per_minute", 10):
            is_spam = True

        if is_spam:
            self.stats[user_id]["spam_detected"] += 1
            try:
                await event.delete()
                self.stats[user_id]["actions_taken"] += 1
                return True
            except Exception:
                pass
                
        return False

    async def get_stats(self, user_id: int) -> dict:
        self._init_stats(user_id)
        return self.stats[user_id]

spam_protection_service = SpamProtectionService()
