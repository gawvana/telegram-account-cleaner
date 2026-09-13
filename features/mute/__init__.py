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
                name="Mute Mode",
                description="Moderation mode deleting messages from muted users",
                category=FeatureCategory.MODERATION,
                requires_telegram=True,
                requires_admin=True,
                icon=ICONS.get("mute", "")
            )
        )
        self._handlers = {}

    async def on_enable(self, user_id: int) -> None:
        logger.info(f"Enabling Mute Mode for user {user_id}")
        try:
            from core.bot_manager import bot_manager
            client = bot_manager.get_client(user_id)
            if client:
                handler = create_mute_handler(user_id)
                client.add_event_handler(handler, events.NewMessage(incoming=True))
                self._handlers[user_id] = handler
        except ImportError:
            pass

    async def on_disable(self, user_id: int) -> None:
        logger.info(f"Disabling Mute Mode for user {user_id}")
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
            "auto_delete": True,
            "notify_user": False
        }

mute_module = MuteModule()
