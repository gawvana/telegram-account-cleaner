from telethon import events
from features.repeater.service import repeater_service
from telegram_client.manager import client_manager

async def repeater_handler(event):
    client = event.client
    user_id = await client_manager.get_user_id_by_client(client)
    if not user_id:
        return
    await repeater_service.process_incoming_message(user_id, event, client)
