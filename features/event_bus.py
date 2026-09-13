import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Awaitable, Any, Optional

logger = logging.getLogger(__name__)

class AppEventType(str, Enum):
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_DELETED = "message_deleted"
    MESSAGE_SENT = "message_sent"
    MESSAGE_READ = "message_read"
    CHAT_UPDATED = "chat_updated"
    ACCOUNT_CONNECTED = "account_connected"
    ACCOUNT_DISCONNECTED = "account_disconnected"

@dataclass
class AppEvent:
    type: AppEventType
    user_id: int
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

EventHandler = Callable[[AppEvent], Awaitable[None]]

class EventBus:
    def __init__(self):
        self._subscribers: dict[AppEventType, list[tuple[str, EventHandler]]] = {}
        self._rate_limits: dict[str, datetime] = {}  # feature_id:event_type -> last_emit
        self._min_interval_ms: int = 100  # minimum ms between handler calls
    
    def subscribe(self, feature_id: str, event_type: AppEventType, handler: EventHandler) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        # Prevent duplicate registration
        for existing_fid, _ in self._subscribers[event_type]:
            if existing_fid == feature_id:
                logger.warning(f"Feature '{feature_id}' already subscribed to {event_type}, skipping")
                return
        self._subscribers[event_type].append((feature_id, handler))
        logger.debug(f"Feature '{feature_id}' subscribed to {event_type}")
    
    def unsubscribe(self, feature_id: str, event_type: Optional[AppEventType] = None) -> None:
        if event_type:
            types = [event_type]
        else:
            types = list(self._subscribers.keys())
        for et in types:
            if et in self._subscribers:
                self._subscribers[et] = [
                    (fid, h) for fid, h in self._subscribers[et] if fid != feature_id
                ]
        logger.debug(f"Feature '{feature_id}' unsubscribed from {event_type or 'all events'}")
    
    def unsubscribe_all(self, feature_id: str) -> None:
        self.unsubscribe(feature_id)
    
    async def emit(self, event: AppEvent) -> None:
        handlers = self._subscribers.get(event.type, [])
        if not handlers:
            return
        
        for feature_id, handler in handlers:
            try:
                # Check if feature is enabled for this user
                from features.registry import feature_registry
                if not await feature_registry.is_enabled(event.user_id, feature_id):
                    continue
                
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler for feature '{feature_id}' on {event.type}: {e}",
                    exc_info=True
                )
                # Error isolation: continue to next handler
                try:
                    from database import db
                    await db.increment_feature_errors(event.user_id, feature_id)
                except Exception:
                    pass

event_bus = EventBus()
