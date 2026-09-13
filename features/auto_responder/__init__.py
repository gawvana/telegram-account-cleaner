from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.auto_responder.handler import create_auto_responder_handler
from telethon import events
import logging

logger = logging.getLogger(__name__)

class AutoResponderModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="auto_responder",
                name="Auto Responder",
                description="Automatically respond using your custom rules",
                category=FeatureCategory.AUTOMATION,
                requires_telegram=True,
                icon=ICONS.get("auto_responder", "")
            )
        )
        self._handlers = {}

    async def on_enable(self, user_id: int) -> None:
        logger.info(f"Enabling Auto Responder for user {user_id}")
        try:
            from core.bot_manager import bot_manager
            client = bot_manager.get_client(user_id)
            if client:
                handler = create_auto_responder_handler(user_id)
                client.add_event_handler(handler, events.NewMessage(incoming=True))
                self._handlers[user_id] = handler
        except ImportError:
            pass

    async def on_disable(self, user_id: int) -> None:
        logger.info(f"Disabling Auto Responder for user {user_id}")
        try:
            from core.bot_manager import bot_manager
            client = bot_manager.get_client(user_id)
            if client and user_id in self._handlers:
                client.remove_event_handler(self._handlers[user_id])
                del self._handlers[user_id]
        except ImportError:
            pass

    def get_default_settings(self) -> dict:
        return {
            "global_cooldown": 60,
            "max_daily_replies": 100,
            "ignore_groups": False
        }

auto_responder_module = AutoResponderModule()
