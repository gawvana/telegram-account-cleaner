from telethon import events
from features.repeater.service import repeater_service
from telegram_client.manager import client_manager

def create_repeater_handler(user_id: int):
    async def repeater_handler(event):
        client = event.client
        await repeater_service.process_incoming_message(user_id, event, client)
    return repeater_handler
