from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from features.common.categories import FeatureCategory

@dataclass
class FeatureDefinition:
    id: str
    name: str
    description: str
    icon: str  # SVG string
    category: FeatureCategory
    permissions: list[str] = field(default_factory=list)
    default_enabled: bool = False
    requires_telegram: bool = False
    requires_admin: bool = False
    has_settings: bool = True
    coming_soon: bool = False

@dataclass
class FeatureActivity:
    last_activity: Optional[datetime] = None
    actions_count: int = 0
    errors_count: int = 0
    enabled_since: Optional[datetime] = None

@dataclass
class FeatureState:
    feature_id: str
    enabled: bool = False
    settings: dict = field(default_factory=dict)
    enabled_at: Optional[datetime] = None
    activity: FeatureActivity = field(default_factory=FeatureActivity)

class BaseFeatureModule(ABC):
    def __init__(self, definition: FeatureDefinition):
        self.definition = definition
        self.feature_id = definition.id
    
    @abstractmethod
    async def on_enable(self, user_id: int) -> None: ...
    
    @abstractmethod
    async def on_disable(self, user_id: int) -> None: ...
    
    @abstractmethod
    def get_default_settings(self) -> dict: ...
    
    async def get_settings_schema(self) -> dict:
        return {}
    
    async def handle_event(self, event) -> None:
        pass  # Override if module needs events
    
    async def get_activity(self, user_id: int) -> FeatureActivity:
        from database import db
        state = await db.get_feature_state(user_id, self.feature_id)
        if state:
            return FeatureActivity(
                last_activity=state.get('last_activity'),
                actions_count=state.get('actions_count', 0),
                errors_count=state.get('errors_count', 0),
                enabled_since=state.get('enabled_at')
            )
        return FeatureActivity()
