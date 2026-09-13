from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from .router import router

class PrankModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="prank",
                name="Prank Tools",
                description="Harmless fun prank text effects",
                category=FeatureCategory.FUN,
                requires_telegram=False,
                icon=ICONS.get("prank", "")
            )
        )
        self.coming_soon = False
    
    async def on_enable(self, user_id: int):
        pass

    async def on_disable(self, user_id: int):
        pass

    def get_default_settings(self) -> dict:
        return {}

prank_module = PrankModule()
