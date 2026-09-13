from features.base import BaseFeatureModule, FeatureDefinition
from features.common.categories import FeatureCategory
from features.common.icons import ICONS
from features.translator.config import DEFAULT_SETTINGS

class TranslatorModule(BaseFeatureModule):
    def __init__(self):
        super().__init__(
            definition=FeatureDefinition(
                id="translator",
                name="Translator",
                description="Translate incoming and outgoing messages",
                category=FeatureCategory.COMMUNICATION,
                requires_telegram=False,
                icon=ICONS.get("translator", ""),
                has_settings=True
            )
        )
    
    async def on_enable(self, user_id: int) -> None:
        pass
    
    async def on_disable(self, user_id: int) -> None:
        pass
    
    def get_default_settings(self) -> dict:
        return DEFAULT_SETTINGS.copy()

translator_module = TranslatorModule()

__all__ = ["translator_module"]
