from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.edited_messages.handler import create_edited_message_handler
from telethon import events
from telegram_client.event_manager import event_manager

class EditedMessagesModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(FeatureDefinition(
            id="edited_messages",
            name="Edited Messages",
            description="View message edit history",
            category=FeatureCategory.MESSAGES,
            requires_telegram=True,
            icon=ICONS.get("edited_messages", "")
        ))

    async def on_enable(self, user_id: int) -> None:
        handler = create_edited_message_handler(user_id)
        await event_manager.register_handler(user_id, "edited_messages_edited", events.MessageEdited, handler)

    async def on_disable(self, user_id: int) -> None:
        await event_manager.unregister_handler(user_id, "edited_messages_edited")

    def get_default_settings(self) -> dict:
        return {"track_bots": False, "track_groups": True, "track_private": True}

edited_messages_module = EditedMessagesModule()
