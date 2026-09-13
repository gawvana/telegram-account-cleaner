from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from .router import router

class MiniGamesModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            FeatureDefinition(
                id="mini_games",
                name="Мини-игры",
                description="Играйте в казуальные игры прямо в CLIN",
                category=FeatureCategory.GAMES,
                requires_telegram=False,
                icon=ICONS.get("mini_games", "")
            )
        )
        self.coming_soon = False
    
    async def on_enable(self, user_id: int):
        pass

    async def on_disable(self, user_id: int):
        pass

    def get_default_settings(self) -> dict:
        return {}

mini_games_module = MiniGamesModule()
