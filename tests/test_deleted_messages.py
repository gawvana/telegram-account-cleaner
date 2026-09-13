import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
from features.deleted_messages.service import deleted_messages_service
from database import db

pytestmark = pytest.mark.asyncio

async def test_deleted_messages_service_save_and_get():
    user_id = 99912345
    chat_id = -100123
    
    msg_id = await deleted_messages_service.save_deleted(
        telegram_id=user_id,
        chat_id=chat_id,
        message_id=10,
        text_content="Hello deleted",
        message_type="text"
    )
    assert msg_id is not None
    
    msgs = await deleted_messages_service.get_messages(user_id)
    assert len(msgs) >= 1
    assert any(m.message_id == 10 and m.text_content == "Hello deleted" for m in msgs)
    
    msgs_chat = await deleted_messages_service.get_messages(user_id, chat_id=chat_id)
    assert len(msgs_chat) >= 1
    
    msgs_other_chat = await deleted_messages_service.get_messages(user_id, chat_id=-999)
    assert not any(m.message_id == 10 for m in msgs_other_chat)

async def test_deleted_messages_stats_and_search():
    user_id = 99912345
    chat_id = -100124
    
    await deleted_messages_service.save_deleted(
        telegram_id=user_id,
        chat_id=chat_id,
        message_id=11,
        text_content="Searchable text here"
    )
    
    stats = await deleted_messages_service.get_stats(user_id)
    assert stats.total_messages >= 1
    assert stats.total_chats >= 1
    
    results = await deleted_messages_service.search(user_id, "Searchable")
    assert len(results) >= 1
    assert results[0].text_content == "Searchable text here"

async def test_deleted_messages_cleanup():
    user_id = 99912345
    chat_id = -100125
    
    # Manually insert an old message
    async with db.get_connection() as conn:
        old_date = datetime.utcnow() - timedelta(days=10)
        await conn.execute(
            """
            INSERT INTO deleted_messages (
                telegram_id, chat_id, message_id, text_content, deleted_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, chat_id, 999, "Old message", old_date)
        )
        await conn.commit()
        
    deleted_count = await deleted_messages_service.cleanup(user_id, retention_days=5)
    assert deleted_count >= 1

def test_api_list_messages(client, auth_headers):
    response = client.get("/api/features/deleted-messages/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_get_stats(client, auth_headers):
    response = client.get("/api/features/deleted-messages/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_messages" in data
    assert "total_chats" in data

def test_api_cleanup(client, auth_headers):
    response = client.post("/api/features/deleted-messages/cleanup?retention_days=7", headers=auth_headers)
    assert response.status_code == 200
    assert "deleted_count" in response.json()

def test_api_search(client, auth_headers):
    response = client.get("/api/features/deleted-messages/search?query=test", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

async def test_owner_isolation():
    user_a = 99912345
    user_b = 88812345
    
    # Save for A
    await deleted_messages_service.save_deleted(user_a, -1, 1, text_content="Secret A")
    # Save for B
    await deleted_messages_service.save_deleted(user_b, -1, 2, text_content="Secret B")
    
    msgs_a = await deleted_messages_service.get_messages(user_a)
    assert any(m.text_content == "Secret A" for m in msgs_a)
    assert not any(m.text_content == "Secret B" for m in msgs_a)
    
    msgs_b = await deleted_messages_service.get_messages(user_b)
    assert any(m.text_content == "Secret B" for m in msgs_b)
    assert not any(m.text_content == "Secret A" for m in msgs_b)
