import json
import logging
from typing import Optional
from features.base import FeatureDefinition, BaseFeatureModule, FeatureState
from features.common.categories import FeatureCategory

logger = logging.getLogger(__name__)

class FeatureRegistry:
    def __init__(self):
        self._features: dict[str, FeatureDefinition] = {}
        self._modules: dict[str, BaseFeatureModule] = {}
    
    def register(self, module: BaseFeatureModule) -> None:
        fid = module.feature_id
        if fid in self._features:
            logger.warning(f"Feature '{fid}' already registered, skipping")
            return
        self._features[fid] = module.definition
        self._modules[fid] = module
        logger.info(f"Registered feature: {fid}")
    
    def get_definition(self, feature_id: str) -> Optional[FeatureDefinition]:
        return self._features.get(feature_id)
    
    def get_module(self, feature_id: str) -> Optional[BaseFeatureModule]:
        return self._modules.get(feature_id)
    
    def get_all(self) -> list[FeatureDefinition]:
        return list(self._features.values())
    
    def get_by_category(self, category: FeatureCategory) -> list[FeatureDefinition]:
        return [f for f in self._features.values() if f.category == category]
    
    def search(self, query: str) -> list[FeatureDefinition]:
        q = query.lower()
        return [
            f for f in self._features.values()
            if q in f.name.lower() or q in f.description.lower() or q in f.id.lower()
        ]
    
    async def get_user_states(self, user_id: int) -> dict[str, FeatureState]:
        from database import db
        states = {}
        all_db_states = await db.get_all_feature_states(user_id)
        db_map = {s['feature_id']: s for s in all_db_states}
        for fid, fdef in self._features.items():
            db_state = db_map.get(fid)
            if db_state:
                states[fid] = FeatureState(
                    feature_id=fid,
                    enabled=bool(db_state.get('enabled', 0)),
                    settings=json.loads(db_state.get('settings_json', '{}')) if db_state.get('settings_json') else {},
                    enabled_at=db_state.get('enabled_at')
                )
            else:
                states[fid] = FeatureState(feature_id=fid)
        return states
    
    async def enable_feature(self, user_id: int, feature_id: str) -> bool:
        module = self._modules.get(feature_id)
        if not module:
            return False
        from database import db
        await db.set_feature_enabled(user_id, feature_id, True)
        try:
            await module.on_enable(user_id)
        except Exception as e:
            logger.error(f"Error enabling {feature_id} for user {user_id}: {e}")
        return True
    
    async def disable_feature(self, user_id: int, feature_id: str) -> bool:
        module = self._modules.get(feature_id)
        if not module:
            return False
        from database import db
        await db.set_feature_enabled(user_id, feature_id, False)
        try:
            await module.on_disable(user_id)
        except Exception as e:
            logger.error(f"Error disabling {feature_id} for user {user_id}: {e}")
        return True
    
    async def is_enabled(self, user_id: int, feature_id: str) -> bool:
        from database import db
        state = await db.get_feature_state(user_id, feature_id)
        return bool(state and state.get('enabled', 0))
    
    async def stop_all_automations(self, user_id: int) -> list[str]:
        stopped = []
        automation_categories = {FeatureCategory.AUTOMATION, FeatureCategory.MODERATION}
        for fid, fdef in self._features.items():
            if fdef.category in automation_categories or fid in ('auto_responder', 'repeater', 'mute', 'spam_protection'):
                if await self.is_enabled(user_id, fid):
                    await self.disable_feature(user_id, fid)
                    stopped.append(fid)
        return stopped

feature_registry = FeatureRegistry()
