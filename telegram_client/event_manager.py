"""Manages Telethon event handlers for feature modules.

Provides safe registration/unregistration of event handlers
to prevent duplicate handlers and ensure clean lifecycle management.
"""
import asyncio
import logging
from typing import Callable, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class TelethonEventManager:
    """Manages per-user, per-feature Telethon event handlers."""
    
    def __init__(self):
        # user_id -> feature_id -> list of (event_type, handler, registered_handler)
        self._handlers: dict[int, dict[str, list[tuple]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = asyncio.Lock()
    
    async def register_handler(
        self,
        user_id: int,
        feature_id: str,
        client,  # TelegramClient
        event_type,  # Telethon event class (e.g. events.NewMessage)
        handler: Callable,
        **event_kwargs  # Additional event filter kwargs
    ) -> bool:
        """Register a Telethon event handler for a specific user and feature.
        
        Returns True if successfully registered, False if already exists.
        """
        async with self._lock:
            existing = self._handlers[user_id][feature_id]
            
            # Check for duplicate
            for et, h, _ in existing:
                if et == event_type and h == handler:
                    logger.warning(
                        f"Handler already registered: user={user_id}, "
                        f"feature={feature_id}, event={event_type.__name__}"
                    )
                    return False
            
            # Wrap handler with error isolation
            async def safe_handler(event):
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(
                        f"Error in Telethon handler for feature '{feature_id}' "
                        f"user={user_id}: {e}",
                        exc_info=True
                    )
                    try:
                        from database import db
                        await db.increment_feature_errors(user_id, feature_id)
                    except Exception:
                        pass
            
            # Register with Telethon client
            client.add_event_handler(safe_handler, event_type(**event_kwargs))
            existing.append((event_type, handler, safe_handler))
            
            logger.info(
                f"Registered Telethon handler: user={user_id}, "
                f"feature={feature_id}, event={event_type.__name__}"
            )
            return True
    
    async def unregister_feature(
        self,
        user_id: int,
        feature_id: str,
        client=None  # TelegramClient, if available
    ) -> int:
        """Unregister all handlers for a specific feature.
        
        Returns number of handlers removed.
        """
        async with self._lock:
            handlers = self._handlers[user_id].get(feature_id, [])
            count = 0
            
            for event_type, original_handler, safe_handler in handlers:
                if client:
                    try:
                        client.remove_event_handler(safe_handler, event_type)
                    except (ValueError, Exception) as e:
                        logger.debug(
                            f"Could not remove handler from client: {e}"
                        )
                count += 1
            
            self._handlers[user_id][feature_id] = []
            
            if count:
                logger.info(
                    f"Unregistered {count} handler(s): user={user_id}, "
                    f"feature={feature_id}"
                )
            return count
    
    async def unregister_all(self, user_id: int, client=None) -> int:
        """Unregister ALL handlers for a user (used on logout/disconnect).
        
        Returns total number of handlers removed.
        """
        async with self._lock:
            total = 0
            feature_ids = list(self._handlers[user_id].keys())
            
            for feature_id in feature_ids:
                handlers = self._handlers[user_id][feature_id]
                for event_type, original_handler, safe_handler in handlers:
                    if client:
                        try:
                            client.remove_event_handler(safe_handler, event_type)
                        except (ValueError, Exception):
                            pass
                    total += 1
                self._handlers[user_id][feature_id] = []
            
            # Clean up user entry
            if user_id in self._handlers:
                del self._handlers[user_id]
            
            if total:
                logger.info(
                    f"Unregistered all {total} handler(s) for user={user_id}"
                )
            return total
    
    def get_active_handlers(self, user_id: int) -> dict[str, int]:
        """Get count of active handlers per feature for a user."""
        result = {}
        for feature_id, handlers in self._handlers.get(user_id, {}).items():
            if handlers:
                result[feature_id] = len(handlers)
        return result
    
    def get_all_active_users(self) -> list[int]:
        """Get list of user IDs with active handlers."""
        return [uid for uid, features in self._handlers.items() if any(features.values())]


# Singleton
event_manager = TelethonEventManager()
