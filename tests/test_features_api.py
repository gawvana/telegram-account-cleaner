import pytest
import asyncio
from fastapi.testclient import TestClient
from webapp_server import app
from webapp.api.auth import get_current_user_id
from features.registry import feature_registry
from features.base import FeatureDefinition, BaseFeatureModule
from features.common.categories import FeatureCategory
from database import db

def override_get_current_user_id():
    return 1

client = TestClient(app)

class DummyFeature(BaseFeatureModule):
    async def on_enable(self, user_id): return True
    async def on_disable(self, user_id): return True
    def get_default_settings(self): return {"dummy_state": "ok"}
    async def get_state(self, user_id): return {"dummy_state": "ok"}

@pytest.fixture(autouse=True)
def setup_feature():
    async def _setup_db():
        await db.init_db()
        async with db.get_connection() as conn:
            await conn.execute("INSERT OR IGNORE INTO users (telegram_id, salt) VALUES (1, 'salt')")
            await conn.commit()
    
    # Run db setup synchronously
    try:
        loop = asyncio.get_running_loop()
        loop.run_until_complete(_setup_db())
    except RuntimeError:
        asyncio.run(_setup_db())

    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    feat = DummyFeature(FeatureDefinition(id="dummy", name="Dummy", description="Dummy feature", category=FeatureCategory.AUTOMATION, icon="icon", has_settings=True))
    feature_registry.register(feat)
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    feature_registry._modules.pop("dummy", None)
    feature_registry._features.pop("dummy", None)

def test_api_features_list():
    response = client.get("/api/features")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["features"], list)
    assert any(f["id"] == "dummy" for f in data["features"])

def test_api_features_search():
    response = client.get("/api/features/search?q=Dummy")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) >= 1
    assert data["results"][0]["id"] == "dummy"

def test_api_features_favorites():
    response = client.post("/api/features/favorites/dummy")
    assert response.status_code == 200
    
    response = client.get("/api/features/favorites")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["favorites"], list)

def test_api_features_analytics():
    response = client.get("/api/features/analytics")
    assert response.status_code == 200
    assert "features_active" in response.json()

def test_api_features_detail():
    response = client.get("/api/features/dummy")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "dummy"
    assert isinstance(data.get("settings"), dict)

def test_api_features_enable_disable():
    response = client.post("/api/features/dummy/enable")
    assert response.status_code == 200
    
    response = client.post("/api/features/dummy/disable")
    assert response.status_code == 200

def test_api_features_settings():
    response = client.get("/api/features/dummy/settings")
    assert response.status_code == 200
    
    response = client.post("/api/features/dummy/settings", json={"settings": {"test": "val"}})
    assert response.status_code == 200

def test_api_features_stop_all():
    response = client.post("/api/features/stop-all")
    assert response.status_code == 200

def test_api_settings_storage():
    response = client.get("/api/settings/storage")
    assert response.status_code == 200
    data = response.json()
    assert "usage" in data
    assert "deleted_messages_stats" in data

def test_api_settings_storage_cleanup():
    response = client.post("/api/settings/storage/cleanup")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_api_settings_storage_retention():
    response = client.post("/api/settings/storage/retention", json={"retention_days": 30})
    assert response.status_code == 200
    assert response.json()["retention_days"] == 30
