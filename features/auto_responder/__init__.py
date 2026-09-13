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
                name="Автоответчик",
                description="Автоматические ответы по вашим правилам",
                category=FeatureCategory.AUTOMATION,
                requires_telegram=True,
                icon=ICONS.get("auto_responder", "")
            )
        )
        self._handlers = {}

    async def on_enable(self, user_id: int) -> None:
        logger.info(f"Enabling Auto Responder for user {user_id}")
        from telegram_client.manager import client_manager
        from telegram_client.event_manager import event_manager
        
        has_session = await client_manager.has_active_session(user_id)
        if has_session:
            async with client_manager.get_client(user_id) as client:
                handler = create_auto_responder_handler(user_id)
                await event_manager.register_handler(user_id, "auto_responder", client, events.NewMessage(incoming=True), handler)
                self._handlers[user_id] = handler

    async def on_disable(self, user_id: int) -> None:
        logger.info(f"Disabling Auto Responder for user {user_id}")
        from telegram_client.event_manager import event_manager
        await event_manager.unregister_feature(user_id, "auto_responder")
        if user_id in self._handlers:
            del self._handlers[user_id]

    def get_default_settings(self) -> dict:
        return {
            "global_cooldown": 60,
            "max_daily_replies": 100,
            "ignore_groups": False
        }

auto_responder_module = AutoResponderModule()
