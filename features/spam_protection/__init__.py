from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.spam_protection.router import router

class SpamProtectionModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="spam_protection",
                name="Защита от спама",
                description="Защита от спама и флуда в администрируемых чатах",
                category=FeatureCategory.MODERATION,
                requires_telegram=True,
                requires_admin=True,
                icon=ICONS.get("spam_protection", "")
            )
        )
        self.router = router

    async def on_enable(self, user_id: int) -> None:
        pass

    async def on_disable(self, user_id: int) -> None:
        pass

    def get_default_settings(self) -> dict:
        return {}

spam_protection_module = SpamProtectionModule()
