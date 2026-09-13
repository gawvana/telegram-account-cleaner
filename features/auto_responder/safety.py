import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class AutoResponderSafety:
    def __init__(self):
        # (user_id, chat_id, rule_id) -> timestamp
        self._cooldowns: Dict[Tuple[int, int, int], float] = {}

    def is_on_cooldown(self, user_id: int, chat_id: int, rule_id: int, cooldown_seconds: int) -> bool:
        if cooldown_seconds <= 0:
            return False
            
        key = (user_id, chat_id, rule_id)
        now = time.time()
        last_used = self._cooldowns.get(key, 0)
        
        if now - last_used < cooldown_seconds:
            return True
            
        self._cooldowns[key] = now
        return False

    def is_safe_to_respond(self, event, response_text: str) -> bool:
        # Prevent self-loop
        if getattr(event, 'out', False):
            return False
            
        # Ignore messages from known bots if possible
        sender = getattr(event, 'sender', None)
        if sender and getattr(sender, 'bot', False):
            return False
            
        # Prevent ping-pong loop where response triggers another bot
        text = getattr(event, 'text', '')
        if text and text == response_text:
            return False
            
        return True

auto_responder_safety = AutoResponderSafety()
