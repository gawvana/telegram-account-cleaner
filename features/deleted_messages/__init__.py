from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.deleted_messages.config import DEFAULT_SETTINGS
from features.deleted_messages.handler import create_deleted_message_handler
from telethon import events
from telegram_client.event_manager import event_manager
from telegram_client.manager import client_manager

class DeletedMessagesModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(FeatureDefinition(
            id="deleted_messages",
            name="Удалённые сообщения",
            description="Восстановление локально сохранённого удалённого контента",
            category=FeatureCategory.MESSAGES,
            permissions=["telegram_connection", "chat_read"],
            requires_telegram=True,
            icon=ICONS.get("deleted_messages", "")
        ))

    async def on_enable(self, user_id: int) -> None:
        handler = create_deleted_message_handler(user_id)
        has_session = await client_manager.has_active_session(user_id)
        if has_session:
            async with client_manager.get_client(user_id) as client:
                await event_manager.register_handler(user_id, "deleted_messages", client, events.MessageDeleted, handler)

    async def on_disable(self, user_id: int) -> None:
        await event_manager.unregister_feature(user_id, "deleted_messages")

    def get_default_settings(self) -> dict:
        return DEFAULT_SETTINGS

deleted_messages_module = DeletedMessagesModule()
