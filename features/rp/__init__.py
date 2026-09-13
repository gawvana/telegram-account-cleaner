from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS

class RPModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="rp",
                name="RP Languages",
                description="Transform text into character roleplay styles",
                category=FeatureCategory.COMMUNICATION,
                requires_telegram=False,
                icon=ICONS.get("rp", "")
            )
        )

    async def on_enable(self, user_id: int) -> None:
        pass

    async def on_disable(self, user_id: int) -> None:
        pass

    def get_default_settings(self) -> dict:
        return {}

rp_module = RPModule()
