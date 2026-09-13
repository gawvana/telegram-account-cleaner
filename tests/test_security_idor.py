import pytest
from database import Database
from services.support_service import SupportService
from services.whitelist_service import WhitelistService


@pytest.mark.asyncio
async def test_support_ticket_idor_protection(tmp_path):
    test_db_path = str(tmp_path / "test_idor.db")
    db_instance = Database(db_path=test_db_path)
    await db_instance.init_db()

    user_a = 111111
    user_b = 222222
    # Ensure users exist for foreign key constraint
    await db_instance.get_or_create_user(telegram_id=user_a, salt="salt_a")
    await db_instance.get_or_create_user(telegram_id=user_b, salt="salt_b")

    # Monkeypatch db
    import services.support_service as ss_module
    old_db = ss_module.db
    ss_module.db = db_instance

    try:
        service = SupportService()

        # 1. User A creates a ticket
        ticket_a = await service.create_ticket(
            telegram_id=user_a,
            category="security",
            subject="Private ticket for user A",
            description="Confidential information that User B must never see.",
        )
        ticket_number = ticket_a["ticket_number"]
        assert ticket_number.startswith("CLIN-")

        # 2. User A can view ticket details
        detail_a = await service.get_ticket_details(ticket_number, telegram_id=user_a)
        assert detail_a is not None
        assert detail_a["ticket"]["telegram_id"] == user_a

        # 3. User B tries to view User A's ticket (IDOR attack) -> must be DENIED (None)
        detail_b = await service.get_ticket_details(ticket_number, telegram_id=user_b)
        assert detail_b is None

        # 4. User B tries to reply to User A's ticket (IDOR attack) -> must be DENIED (None)
        reply_b = await service.add_reply(
            ticket_number=ticket_number,
            sender_type="user",
            sender_id=user_b,
            message="Malicious injection attempt",
        )
        assert reply_b is None

        # 5. User A replies -> Allowed
        reply_a = await service.add_reply(
            ticket_number=ticket_number,
            sender_type="user",
            sender_id=user_a,
            message="Legitimate follow up by owner",
        )
        assert reply_a is not None
        assert reply_a["sender_type"] == "user"

    finally:
        ss_module.db = old_db


@pytest.mark.asyncio
async def test_whitelist_user_isolation(tmp_path):
    test_db_path = str(tmp_path / "test_wl_idor.db")
    db_instance = Database(db_path=test_db_path)
    await db_instance.init_db()

    user_a = 333333
    user_b = 444444
    await db_instance.get_or_create_user(telegram_id=user_a, salt="salt_a")
    await db_instance.get_or_create_user(telegram_id=user_b, salt="salt_b")

    import services.whitelist_service as wl_module
    old_db = wl_module.db
    wl_module.db = db_instance

    try:
        service = WhitelistService()

        # User A adds chat 12345
        await service.add_to_whitelist(user_a, chat_id=12345, title="User A Secret Group")

        # User B lists whitelist -> chat 12345 must NOT be in User B's list
        b_list = await service.list_whitelist(user_b)
        assert not any(i["chat_id"] == 12345 for i in b_list)

        # User B tries to remove User A's whitelist item -> returns False, cannot affect User A
        removed_by_b = await service.remove_from_whitelist(user_b, chat_id=12345)
        assert removed_by_b is False

        # User A still has item
        a_list = await service.list_whitelist(user_a)
        assert any(i["chat_id"] == 12345 for i in a_list)

    finally:
        wl_module.db = old_db
