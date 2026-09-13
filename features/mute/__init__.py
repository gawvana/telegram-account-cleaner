from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.mute.handler import create_mute_handler
from telethon import events
import logging

logger = logging.getLogger(__name__)

class MuteModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="mute",
                name="Игнор",
                description="Режим модерации с удалением сообщений от заглушенных пользователей",
                category=FeatureCategory.MODERATION,
                requires_telegram=True,
                requires_admin=True,
                icon=ICONS.get("mute", "")
            )
        )
        self._handlers = {}

    async def on_enable(self, user_id: int) -> None:
        logger.info(f"Enabling Mute Mode for user {user_id}")
        from telegram_client.manager import client_manager
        from telegram_client.event_manager import event_manager
        has_session = await client_manager.has_active_session(user_id)
        if has_session:
            async with client_manager.get_client(user_id) as client:
                handler = create_mute_handler(user_id)
                await event_manager.register_handler(user_id, "mute", client, events.NewMessage(incoming=True), handler)
                self._handlers[user_id] = handler

    async def on_disable(self, user_id: int) -> None:
        logger.info(f"Disabling Mute Mode for user {user_id}")
        from telegram_client.event_manager import event_manager
        await event_manager.unregister_feature(user_id, "mute")
        if user_id in self._handlers:
            del self._handlers[user_id]

    def get_default_settings(self) -> dict:
        return {
            "auto_delete": True,
            "notify_user": False
        }

mute_module = MuteModule()
