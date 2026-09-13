from telethon import events
from features.auto_responder.service import auto_responder_service
import logging

logger = logging.getLogger(__name__)

def create_auto_responder_handler(user_id: int):
    async def handler(event):
        try:
            await auto_responder_service.process_incoming_message(user_id, event, event.client)
        except Exception as e:
            logger.error(f"Error in auto_responder handler for {user_id}: {e}")
    return handler
