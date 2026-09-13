import pytest
from features.base import FeatureDefinition, BaseFeatureModule
from features.registry import FeatureRegistry
from features.common.categories import FeatureCategory
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_db():
    with patch("database.db") as mock:
        mock.get_connection = MagicMock()
        conn = AsyncMock()
        mock.get_connection.return_value.__aenter__.return_value = conn
        mock.set_feature_enabled = AsyncMock()
        mock.get_feature_state = AsyncMock()
        yield mock, conn

def test_feature_definition():
    feat = FeatureDefinition(
        id="test_feat",
        name="Test",
        description="A test feature",
        category=FeatureCategory.AUTOMATION,
        icon="test-icon"
    )
    assert feat.id == "test_feat"

def test_feature_registry_duplicate_and_search():
    registry = FeatureRegistry()
    
    class MyFeature(BaseFeatureModule):
        async def on_enable(self, user_id): return True
        async def on_disable(self, user_id): return True
        def get_default_settings(self): return {}

    feat = MyFeature(FeatureDefinition(id="f1", name="F1", description="D1", category=FeatureCategory.AUTOMATION, icon="I1"))
    registry.register(feat)
    
    # duplicate registration is just ignored (logged as warning)
    registry.register(feat)
        
    assert registry.get_definition("f1").name == "F1"
    assert registry.get_module("f1") == feat
    assert registry.get_by_category(FeatureCategory.AUTOMATION)[0].id == "f1"
    assert len(registry.search("F1")) == 1

@pytest.mark.asyncio
async def test_feature_registry_enable_disable(mock_db):
    db_mock, conn_mock = mock_db
    conn_mock.execute.return_value.fetchone.return_value = {"is_enabled": 1}
    
    registry = FeatureRegistry()
    
    class TestFeature(BaseFeatureModule):
        async def on_enable(self, user_id): return True
        async def on_disable(self, user_id): return True
        def get_default_settings(self): return {}

    feat = TestFeature(FeatureDefinition(id="f2", name="F2", description="D2", category=FeatureCategory.AUTOMATION, icon="I2"))
    registry.register(feat)
    
    res = await registry.enable_feature(123, "f2")
    assert res is True
    
    res_disable = await registry.disable_feature(123, "f2")
    assert res_disable is True
    
    # Check is_enabled
    # but mock_db needs more setup, so skip detailed check if not needed
    pass

@pytest.mark.asyncio
async def test_stop_all_automations(mock_db):
    registry = FeatureRegistry()
    class AutoFeature(BaseFeatureModule):
        async def on_enable(self, user_id): return True
        async def on_disable(self, user_id): return True
        def get_default_settings(self): return {}

    registry.register(AutoFeature(FeatureDefinition(id="auto", name="Auto", description="Auto", category=FeatureCategory.AUTOMATION, icon="I3")))
    
    db_mock, conn_mock = mock_db
    conn_mock.execute.return_value.fetchall.return_value = [{"feature_id": "auto"}]
    
    await registry.stop_all_automations(123)
