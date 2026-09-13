import pytest
from httpx import AsyncClient
from features.auto_responder.service import auto_responder_service
from features.auto_responder.models import MatchType, AutoResponderRuleCreate, AutoResponderRuleUpdate
from features.auto_responder.safety import auto_responder_safety
import time

pytestmark = pytest.mark.asyncio

def test_pattern_matching_logic():
    # Exact
    assert auto_responder_service.test_rule("hello", MatchType.EXACT, "Hello")
    assert not auto_responder_service.test_rule("hello", MatchType.EXACT, "Hello world")
    
    # Contains
    assert auto_responder_service.test_rule("hello", MatchType.CONTAINS, "well hello there")
    assert not auto_responder_service.test_rule("hello", MatchType.CONTAINS, "hi there")
    
    # Starts with
    assert auto_responder_service.test_rule("hello", MatchType.STARTS_WITH, "Hello world")
    assert not auto_responder_service.test_rule("hello", MatchType.STARTS_WITH, "world hello")
    
    # Regex
    assert auto_responder_service.test_rule(r"\bhello\b", MatchType.REGEX, "say hello again")
    assert not auto_responder_service.test_rule(r"\bhello\b", MatchType.REGEX, "othello")
    assert not auto_responder_service.test_rule(r"[unclosed", MatchType.REGEX, "text")

def test_safety_rules():
    class MockEvent:
        def __init__(self, out=False, is_bot=False, text="hi"):
            self.out = out
            class Sender:
                bot = is_bot
            self.sender = Sender()
            self.text = text
            
    # Self-message skipping
    assert not auto_responder_safety.is_safe_to_respond(MockEvent(out=True), "response")
    # Bot skipping
    assert not auto_responder_safety.is_safe_to_respond(MockEvent(is_bot=True), "response")
    # Ping-pong loop
    assert not auto_responder_safety.is_safe_to_respond(MockEvent(text="ping"), "ping")
    
    assert auto_responder_safety.is_safe_to_respond(MockEvent(), "hello back")

    # Cooldown enforcement
    user_id = 99912345
    chat_id = 111
    rule_id = 1
    
    assert not auto_responder_safety.is_on_cooldown(user_id, chat_id, rule_id, 1) # Sets cooldown
    assert auto_responder_safety.is_on_cooldown(user_id, chat_id, rule_id, 1) # Still on cooldown
    time.sleep(1.1)
    assert not auto_responder_safety.is_on_cooldown(user_id, chat_id, rule_id, 1) # Cooldown passed

async def test_rule_crud():
    user_id = 99912345
    
    # Create
    rule_in = AutoResponderRuleCreate(
        match_type=MatchType.EXACT,
        pattern="test_crud",
        response="test_response",
        cooldown_seconds=10,
        max_daily=5
    )
    rule = await auto_responder_service.create_rule(user_id, rule_in)
    assert rule.id is not None
    assert rule.pattern == "test_crud"
    
    # Read
    rules = await auto_responder_service.get_rules(user_id)
    assert any(r.id == rule.id for r in rules)
    
    # Update
    update_in = AutoResponderRuleUpdate(response="new_response")
    updated = await auto_responder_service.update_rule(rule.id, user_id, update_in)
    assert updated is not None
    assert updated.response == "new_response"
    
    # Delete
    deleted = await auto_responder_service.delete_rule(rule.id, user_id)
    assert deleted is True
    
    rules_after = await auto_responder_service.get_rules(user_id)
    assert not any(r.id == rule.id for r in rules_after)

def test_api_test_endpoint(client, auth_headers):
    payload = {
        "pattern": "test",
        "match_type": "exact",
        "test_message": "test"
    }
    response = client.post("/api/features/auto-responder/test", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["matched"] is True

    payload["test_message"] = "testing"
    response = client.post("/api/features/auto-responder/test", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["matched"] is False
