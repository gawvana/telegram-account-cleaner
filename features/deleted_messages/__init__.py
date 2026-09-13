from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.deleted_messages.config import DEFAULT_SETTINGS
from features.deleted_messages.handler import create_deleted_message_handler
from telethon import events
from telegram_client.event_manager import event_manager

class DeletedMessagesModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(FeatureDefinition(
            id="deleted_messages",
            name="Deleted Messages",
            description="Recover locally archived deleted content",
            category=FeatureCategory.MESSAGES,
            permissions=["telegram_connection", "chat_read"],
            requires_telegram=True,
            icon=ICONS.get("deleted_messages", "")
        ))

    async def on_enable(self, user_id: int) -> None:
        handler = create_deleted_message_handler(user_id)
        await event_manager.register_handler(user_id, "deleted_messages_deleted", events.MessageDeleted, handler)

    async def on_disable(self, user_id: int) -> None:
        await event_manager.unregister_handler(user_id, "deleted_messages_deleted")

    def get_default_settings(self) -> dict:
        return DEFAULT_SETTINGS

deleted_messages_module = DeletedMessagesModule()
