from telethon import events
from features.spam_protection.service import spam_protection_service

async def handle_spam_protection(event):
    if not hasattr(event.client, "user_id"):
        return
    user_id = event.client.user_id
    await spam_protection_service.inspect_message(user_id, event, event.client)

def register_handlers(client_manager):
    @client_manager.on(events.NewMessage(incoming=True))
    async def handler(event):
        await handle_spam_protection(event)
