from telethon import events
from features.edited_messages.service import edited_messages_service
from utils.logger import logger

def create_edited_message_handler(user_id: int):
    async def handler(event: events.MessageEdited.Event):
        try:
            chat_id = event.chat_id
            message_id = event.id
            sender_id = event.sender_id
            new_text = event.text
            
            await edited_messages_service.save_edit(
                telegram_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                sender_id=sender_id,
                new_text=new_text
            )
        except Exception as e:
            logger.error(f"Error handling edited message for {user_id}: {e}")
    return handler
