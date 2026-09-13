import pytest
from features.event_bus import EventBus, AppEvent, AppEventType
from features.registry import feature_registry

@pytest.fixture
def test_event_bus():
    return EventBus()

@pytest.mark.asyncio
async def test_event_bus_subscribe_unsubscribe(test_event_bus):
    handler_called = False
    async def handler(event):
        nonlocal handler_called
        handler_called = True

    test_event_bus.subscribe("test_feat", AppEventType.MESSAGE_DELETED, handler)
    
    # duplicate subscription test
    test_event_bus.subscribe("test_feat", AppEventType.MESSAGE_DELETED, handler)
    assert len(test_event_bus._subscribers[AppEventType.MESSAGE_DELETED]) == 1

    await test_event_bus.emit(AppEvent(type=AppEventType.MESSAGE_DELETED, user_id=1, data={}))
    # handler shouldn't be called if feature is not enabled. 
    # But wait, test_event_bus will check feature_registry.is_enabled, which might fail or be true depending on db mock. 
    # Let's mock feature_registry.is_enabled for this test as well.

@pytest.mark.asyncio
async def test_event_bus_feature_gating_and_isolation(test_event_bus, monkeypatch):
    async def mock_is_enabled(user_id, feature_id):
        if feature_id == "f_disabled": return False
        return True
    monkeypatch.setattr(feature_registry, "is_enabled", mock_is_enabled)
    
    handler1_called = False
    handler2_called = False
    
    async def handler1(event):
        nonlocal handler1_called
        handler1_called = True
        raise Exception("Failing handler")
        
    async def handler2(event):
        nonlocal handler2_called
        handler2_called = True
        
    feature_handler_called = False
    async def feature_handler(event):
        nonlocal feature_handler_called
        feature_handler_called = True

    test_event_bus.subscribe("f_enabled1", AppEventType.ACCOUNT_CONNECTED, handler1)
    test_event_bus.subscribe("f_enabled2", AppEventType.ACCOUNT_CONNECTED, handler2)
    test_event_bus.subscribe("f_disabled", AppEventType.ACCOUNT_CONNECTED, feature_handler)
    
    await test_event_bus.emit(AppEvent(type=AppEventType.ACCOUNT_CONNECTED, user_id=1, data={}))
    
    assert handler1_called is True
    assert handler2_called is True
    assert feature_handler_called is False

    test_event_bus.unsubscribe("f_enabled1", AppEventType.ACCOUNT_CONNECTED)
    assert len(test_event_bus._subscribers[AppEventType.ACCOUNT_CONNECTED]) == 2
    
    test_event_bus.unsubscribe_all("f_enabled2")
    assert len(test_event_bus._subscribers[AppEventType.ACCOUNT_CONNECTED]) == 1
