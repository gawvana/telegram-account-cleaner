import pytest
from httpx import AsyncClient
from features.mute.service import mute_service, whitelist_service
import time

pytestmark = pytest.mark.asyncio

async def test_mute_service_add_remove_is_muted():
    user_id = 99912345
    chat_id = -100500
    target_id = 200
    
    # Add mute
    await mute_service.add_mute(user_id, chat_id, target_id, duration_minutes=60)
    assert mute_service.is_muted(user_id, chat_id, target_id)
    
    # Active mutes
    active = mute_service.get_active_mutes(user_id)
    assert len(active) == 1
    assert active[0].chat_id == chat_id
    assert active[0].target_user_id == target_id
    
    # Remove mute
    removed = mute_service.remove_mute(user_id, chat_id, target_id)
    assert removed is True
    assert not mute_service.is_muted(user_id, chat_id, target_id)

async def test_mute_service_expiration():
    user_id = 99912345
    chat_id = -100501
    target_id = 201
    
    mute_service._active_mutes[(user_id, chat_id, target_id)] = time.time() - 10 # expired
    assert not mute_service.is_muted(user_id, chat_id, target_id)

async def test_whitelist_priority():
    user_id = 99912345
    chat_id = -100502
    target_id = 202
    
    # Add to whitelist
    from database import db
    async with db.get_connection() as conn:
        await conn.execute("INSERT OR IGNORE INTO whitelist (telegram_id, chat_id) VALUES (?, ?)", (user_id, chat_id))
        await conn.commit()
        
    # Attempt to mute should be ignored or harmless
    await mute_service.add_mute(user_id, chat_id, target_id)
    assert not mute_service.is_muted(user_id, chat_id, target_id)
    
def test_api_mute_endpoints(client, auth_headers):
    # Create rule
    payload = {
        "chat_id": -100600,
        "target_user_id": 300,
        "duration_minutes": 30,
        "reason": "spam"
    }
    resp = client.post("/api/features/mute/rules", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    
    # List rules
    resp = client.get("/api/features/mute/rules", headers=auth_headers)
    assert resp.status_code == 200
    rules = resp.json()
    assert isinstance(rules, list)
    assert any(r["chat_id"] == -100600 and r["target_user_id"] == 300 for r in rules)
    
    # Stats
    resp = client.get("/api/features/mute/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert "active_mutes" in resp.json()
    
    # Delete rule
    rule_id = "-100600_300"
    resp = client.delete(f"/api/features/mute/rules/{rule_id}", headers=auth_headers)
    assert resp.status_code == 200
