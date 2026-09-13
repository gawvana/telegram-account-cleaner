from telethon import events
from features.deleted_messages.service import deleted_messages_service
from utils.logger import logger
import datetime

def create_deleted_message_handler(user_id: int):
    async def handler(event: events.MessageDeleted.Event):
        try:
            chat_id = event.chat_id if event.chat_id else 0
            for message_id in event.deleted_ids:
                await deleted_messages_service.save_deleted(
                    telegram_id=user_id,
                    chat_id=chat_id,
                    message_id=message_id,
                    message_type='text',
                    text_content='Message content not available',
                    original_date=datetime.datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error handling deleted message for {user_id}: {e}")
    return handler
