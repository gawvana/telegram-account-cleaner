import pytest
from httpx import AsyncClient
from features.edited_messages.service import edited_messages_service

pytestmark = pytest.mark.asyncio

async def test_edited_messages_service_save_and_get():
    import random
    user_id = 99912345
    chat_id = random.randint(-1000000, -100)
    msg_id = random.randint(100, 1000000)
    
    # Edit #1
    edit_id1 = await edited_messages_service.save_edit(
        telegram_id=user_id,
        chat_id=chat_id,
        message_id=msg_id,
        old_text="Original",
        new_text="Edit 1"
    )
    assert edit_id1 is not None
    
    # Edit #2
    edit_id2 = await edited_messages_service.save_edit(
        telegram_id=user_id,
        chat_id=chat_id,
        message_id=msg_id,
        old_text="Edit 1",
        new_text="Edit 2"
    )
    
    history = await edited_messages_service.get_history(user_id, chat_id, msg_id)
    assert len(history) == 2
    assert history[0].edit_version == 1
    assert history[0].old_text == "Original"
    assert history[1].edit_version == 2
    assert history[1].new_text == "Edit 2"
    
    msgs = await edited_messages_service.get_messages(user_id)
    assert len(msgs) >= 2
    
    stats = await edited_messages_service.get_stats(user_id)
    assert stats.total_edits >= 2
    assert stats.unique_messages_edited >= 1

def test_api_list_edited_messages(client, auth_headers):
    response = client.get("/api/features/edited-messages/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_get_edit_history(client, auth_headers):
    chat_id = -100200
    msg_id = 15
    response = client.get(f"/api/features/edited-messages/{chat_id}/{msg_id}/history", headers=auth_headers)
    assert response.status_code == 200
    history = response.json()
    assert isinstance(history, list)
    if len(history) > 0:
        assert "edit_version" in history[0]

def test_api_get_edit_stats(client, auth_headers):
    response = client.get("/api/features/edited-messages/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_edits" in data
    assert "unique_messages_edited" in data

async def test_edited_messages_owner_isolation():
    user_a = 99912345
    user_b = 88812345
    
    await edited_messages_service.save_edit(user_a, -1, 100, old_text="A", new_text="B")
    await edited_messages_service.save_edit(user_b, -1, 101, old_text="X", new_text="Y")
    
    msgs_a = await edited_messages_service.get_messages(user_a)
    assert any(m.message_id == 100 for m in msgs_a)
    assert not any(m.message_id == 101 for m in msgs_a)
