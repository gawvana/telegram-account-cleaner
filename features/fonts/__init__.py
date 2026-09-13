from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS

class FontsModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="fonts",
                name="Fonts",
                description="Style your messages with Unicode fonts",
                category=FeatureCategory.TEXT,
                requires_telegram=False,
                icon=ICONS.get("fonts", "")
            )
        )

    async def on_enable(self, user_id: int) -> None:
        pass

    async def on_disable(self, user_id: int) -> None:
        pass

    def get_default_settings(self) -> dict:
        return {}

fonts_module = FontsModule()
