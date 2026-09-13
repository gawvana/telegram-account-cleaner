import os
import pytest
from fastapi.testclient import TestClient
from webapp_server import app
from webapp.api.auth import create_access_token
from database import db

# Set test environment flags
os.environ["TESTING"] = "true"
os.environ["PYTEST_CURRENT_TEST"] = "1"

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "99912345"})
    return {"Authorization": f"Bearer {token}"}

import asyncio

@pytest.fixture(autouse=True)
def init_test_db():
    async def _setup():
        await db.init_db()
        async with db.get_connection() as conn:
            await conn.execute("INSERT OR IGNORE INTO users (telegram_id, salt) VALUES (99912345, 'test_salt_12345')")
            await conn.commit()
    asyncio.run(_setup())
