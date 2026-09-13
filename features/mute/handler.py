from telethon import events
from features.mute.service import mute_service
import logging

logger = logging.getLogger(__name__)

def create_mute_handler(user_id: int):
    async def handler(event):
        try:
            await mute_service.process_incoming_message(user_id, event, event.client)
        except Exception as e:
            logger.error(f"Error in mute handler for {user_id}: {e}")
    return handler
