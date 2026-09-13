from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.edited_messages.handler import create_edited_message_handler
from telethon import events
from telegram_client.event_manager import event_manager
from telegram_client.manager import client_manager

class EditedMessagesModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(FeatureDefinition(
            id="edited_messages",
            name="Изменённые сообщения",
            description="Просмотр истории изменений сообщений",
            category=FeatureCategory.MESSAGES,
            requires_telegram=True,
            icon=ICONS.get("edited_messages", "")
        ))

    async def on_enable(self, user_id: int) -> None:
        handler = create_edited_message_handler(user_id)
        has_session = await client_manager.has_active_session(user_id)
        if has_session:
            async with client_manager.get_client(user_id) as client:
                await event_manager.register_handler(user_id, "edited_messages", client, events.MessageEdited, handler)

    async def on_disable(self, user_id: int) -> None:
        await event_manager.unregister_feature(user_id, "edited_messages")

    def get_default_settings(self) -> dict:
        return {"track_bots": False, "track_groups": True, "track_private": True}

edited_messages_module = EditedMessagesModule()
