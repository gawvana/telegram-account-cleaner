import pytest
from fastapi.testclient import TestClient
from webapp_server import app

def test_whitelist_api_mutations_contract(client, auth_headers):
    """Tests POST and DELETE on /api/whitelist."""
    # 1. Add item
    post_res = client.post(
        "/api/whitelist",
        json={"chat_id": 777000111, "title": "Work Channel"},
        headers=auth_headers
    )
    assert post_res.status_code in [200, 201]

    # 2. Verify it shows up
    get_res = client.get("/api/whitelist", headers=auth_headers)
    assert get_res.status_code == 200
    raw_items = get_res.json()
    items = raw_items if isinstance(raw_items, list) else raw_items.get("items", [])
    assert any(i["chat_id"] == 777000111 for i in items)

    # 3. Delete item
    del_res = client.delete("/api/whitelist/777000111", headers=auth_headers)
    assert del_res.status_code == 200

    # 4. Verify it was removed
    get_res2 = client.get("/api/whitelist", headers=auth_headers)
    raw_items2 = get_res2.json()
    items2 = raw_items2 if isinstance(raw_items2, list) else raw_items2.get("items", [])
    assert not any(i["chat_id"] == 777000111 for i in items2)


def test_unauthenticated_api_mutations_are_rejected(client):
    """Verifies that API mutations without auth header return 401."""
    res1 = client.post("/api/whitelist", json={"chat_id": 12345})
    assert res1.status_code == 401

    res2 = client.delete("/api/whitelist/12345")
    assert res2.status_code == 401

    res3 = client.post("/api/cleanup/run", json={"target_chat_ids": [12345]})
    assert res3.status_code == 401


def test_support_ticket_creation_and_reply_contract(client, auth_headers):
    """Tests creating a support ticket and adding a message."""
    create_res = client.post(
        "/api/support/tickets",
        json={
            "category": "bug",
            "subject": "Test Issue",
            "description": "Found a test issue in webapp"
        },
        headers=auth_headers
    )
    assert create_res.status_code in [200, 201]
    res_json = create_res.json()
    ticket_data = res_json.get("data") or res_json
    ticket_number = ticket_data.get("ticket_number")
    assert ticket_number is not None

    # Reply to ticket
    reply_res = client.post(
        f"/api/support/tickets/{ticket_number}/reply",
        json={"message": "Follow up details here"},
        headers=auth_headers
    )
    assert reply_res.status_code == 200
