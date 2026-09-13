from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.repeater.handler import create_repeater_handler
from telethon import events
from telegram_client.manager import client_manager
from telegram_client.event_manager import event_manager

class RepeaterModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="repeater",
                name="Повторитель сообщений",
                description="Повторяет сообщения пользователя со строгими лимитами",
                category=FeatureCategory.FUN,
                requires_telegram=True,
                icon=ICONS.get("repeater", "")
            )
        )
        self._handlers = {}

    async def on_enable(self, user_id: int) -> None:
        has_session = await client_manager.has_active_session(user_id)
        if has_session:
            async with client_manager.get_client(user_id) as client:
                handler = create_repeater_handler(user_id)
                await event_manager.register_handler(user_id, "repeater", client, events.NewMessage(incoming=True), handler)
                self._handlers[user_id] = handler

    async def on_disable(self, user_id: int) -> None:
        await event_manager.unregister_feature(user_id, "repeater")
        if user_id in self._handlers:
            del self._handlers[user_id]

    def get_default_settings(self) -> dict:
        return {}

repeater_module = RepeaterModule()
