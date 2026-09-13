from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.one_time_messages.router import router

class OneTimeMessagesModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="one_time_messages",
                name="Одноразовые сообщения",
                description="Отправка самоуничтожающихся временных сообщений по таймеру",
                category=FeatureCategory.MESSAGES,
                requires_telegram=True,
                icon=ICONS.get("one_time_messages", "")
            )
        )
        self.router = router

    async def on_enable(self, user_id: int) -> None:
        pass

    async def on_disable(self, user_id: int) -> None:
        pass

    def get_default_settings(self) -> dict:
        return {}

one_time_messages_module = OneTimeMessagesModule()
