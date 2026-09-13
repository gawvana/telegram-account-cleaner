from typing import Any, Dict, List, Optional
from database import db
from utils.logger import logger

SECURITY_NOTICE = (
    "⚠️ ВНИМАНИЕ: Служба поддержки CLIN НИКОГДА не запрашивает API Hash, Telegram код, "
    "2FA-пароль или session string! Никогда не отправляйте их в тикетах или поддержке."
)

FAQ_ITEMS = [
    {
        "id": "faq-0",
        "question": "Как получить API ID и API Hash для подключения Telegram?",
        "answer": "1. Откройте официальный портал https://my.telegram.org\n2. Войдите в свой Telegram-аккаунт.\n3. Перейдите в 'API development tools'.\n4. Создайте приложение, если его ещё нет.\n5. Скопируйте 'App api_id' и 'App api_hash' в CLIN.\nВажно: Никогда не передавайте API Hash другим лицам и не отправляйте его в поддержку!",
    },
    {
        "id": "faq-1",
        "question": "Безопасно ли использовать CLIN?",
        "answer": "Да. Сессии Telegram и API credentials шифруются локально алгоритмом Fernet (AES-128-CBC) с индивидуальной солью для каждого пользователя. Ваши ключи и пароли не передаются третьим лицам.",
    },
    {
        "id": "faq-2",
        "question": "Что делает режим Dry-Run (Тестовый прогон)?",
        "answer": "В режиме Dry-Run CLIN симулирует полный процесс сканирования и очистки, показывает точный список каналов и диалогов, которые были бы удалены, но НЕ совершает никаких реальных действий в Telegram.",
    },
    {
        "id": "faq-3",
        "question": "Как работает Белый список (Whitelist)?",
        "answer": "Чаты и каналы, добавленные в Белый список, защищены строгой серверной проверкой. Даже при нажатии 'Очистить всё' или запуске авто-очистки, чаты из белого списка будут пропущены.",
    },
    {
        "id": "faq-4",
        "question": "Что такое Rejoin Manifest?",
        "answer": "Перед тем как покинуть публичный канал или супергруппу, CLIN сохраняет его публичную ссылку (@username или t.me/...) в манифест. Вы можете в любой момент экспортировать его в Настройках, чтобы вернуться в нужный канал.",
    },
    {
        "id": "faq-5",
        "question": "Как полностью удалить свои данные из CLIN?",
        "answer": "В Настройках выберите 'Отозвать согласие и выйти'. Ваша сессия на сервере будет немедленно перезаписана нулями и удалена, а активные задачи очистки отменены.",
    },
]


class SupportService:
    """Manages customer support tickets, threaded messages, and knowledge base."""

    async def create_ticket(
        self,
        telegram_id: int,
        category: str,
        subject: str,
        description: str,
        priority: str = "medium",
    ) -> Dict[str, Any]:
        """Creates a new support ticket and sends initial user message to the thread."""
        ticket = await db.create_support_ticket(
            telegram_id=telegram_id,
            category=category,
            subject=subject.strip(),
            description=description.strip(),
            priority=priority,
        )

        ticket_id = ticket["id"]
        # Add the initial description as the first thread message
        await db.add_ticket_message(
            ticket_id=ticket_id,
            sender_type="user",
            sender_id=telegram_id,
            message=description.strip(),
        )

        await db.append_audit_log(telegram_id, action="SUPPORT_TICKET_CREATED")
        logger.info(f"User {telegram_id} opened support ticket {ticket.get('ticket_number')}")
        return ticket

    async def get_user_tickets(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Lists all tickets opened by a user."""
        return await db.list_tickets(telegram_id=telegram_id)

    async def get_ticket_details(
        self, ticket_number: str, telegram_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieves ticket details and thread messages. Checks IDOR if telegram_id passed."""
        ticket = await db.get_ticket(ticket_number)
        if not ticket:
            return None

        # IDOR protection: if user is not admin and not ticket owner, deny access
        if telegram_id is not None and ticket["telegram_id"] != telegram_id:
            logger.warning(f"IDOR attempt: User {telegram_id} tried to read ticket {ticket_number}")
            return None

        messages = await db.get_ticket_messages(ticket["id"])
        return {
            "ticket": ticket,
            "messages": messages,
            "security_notice": SECURITY_NOTICE,
        }

    async def add_reply(
        self,
        ticket_number: str,
        sender_type: str,
        sender_id: int,
        message: str,
        attachments: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Appends a reply to the ticket thread."""
        ticket = await db.get_ticket(ticket_number)
        if not ticket:
            return None

        # IDOR check for regular user
        if sender_type == "user" and ticket["telegram_id"] != sender_id:
            logger.warning(f"IDOR attempt: User {sender_id} tried to reply to ticket {ticket_number}")
            return None

        msg_id = await db.add_ticket_message(
            ticket_id=ticket["id"],
            sender_type=sender_type,
            sender_id=sender_id,
            message=message.strip(),
            attachments=attachments,
        )

        # Update status if closed/waiting
        if sender_type == "user" and ticket["status"] in ("resolved", "closed"):
            await db.update_ticket_status(ticket_number, "in_progress")
        elif sender_type == "admin":
            await db.update_ticket_status(ticket_number, "waiting_user")

        return {
            "message_id": msg_id,
            "ticket_number": ticket_number,
            "sender_type": sender_type,
            "message": message,
        }

    async def update_status(self, ticket_number: str, new_status: str) -> bool:
        """Updates ticket status."""
        return await db.update_ticket_status(ticket_number, new_status)

    def get_faq(self) -> List[Dict[str, str]]:
        """Returns preloaded FAQ entries."""
        return FAQ_ITEMS


support_service = SupportService()
