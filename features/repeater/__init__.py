from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.repeater.handler import repeater_handler
from telethon import events
from telegram_client.manager import client_manager

class RepeaterModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="repeater",
                name="Message Repeater",
                description="Repeats messages from selected user with strict limits",
                category=FeatureCategory.FUN,
                requires_telegram=True,
                icon=ICONS.get("repeater", "")
            )
        )

    async def on_enable(self, user_id: int) -> None:
        client = await client_manager.get_client(user_id)
        if client:
            client.add_event_handler(repeater_handler, events.NewMessage(incoming=True))

    async def on_disable(self, user_id: int) -> None:
        client = await client_manager.get_client(user_id)
        if client:
            client.remove_event_handler(repeater_handler, events.NewMessage(incoming=True))

    def get_default_settings(self) -> dict:
        return {}

repeater_module = RepeaterModule()
