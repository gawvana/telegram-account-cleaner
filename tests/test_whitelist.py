import pytest
from database import Database
from services.whitelist_service import WhitelistService
from telegram_client.cleaner import AccountCleaner
from telegram_client.models import ChatType, DialogItem


@pytest.mark.asyncio
async def test_whitelist_crud_and_export_import(tmp_path):
    test_db_path = str(tmp_path / "test_whitelist.db")
    test_db = Database(test_db_path)
    await test_db.init_db()

    # Monkeypatch db in whitelist_service
    import services.whitelist_service as ws_mod
    original_db = ws_mod.db
    ws_mod.db = test_db

    try:
        service = WhitelistService()
        user_id = 999111
        await test_db.get_or_create_user(user_id, salt="test_salt")

        # 1. Add item
        added = await service.add_to_whitelist(
            telegram_id=user_id,
            chat_id=-100123456789,
            title="Important Channel",
            username="important_chan",
        )
        assert added is True

        # 2. Check exists
        is_wl = await service.is_whitelisted(user_id, -100123456789)
        assert is_wl is True

        # 3. Export
        exported = await service.export_whitelist(user_id)
        assert len(exported) == 1
        assert exported[0]["chat_id"] == -100123456789

        # 4. Remove
        removed = await service.remove_from_whitelist(user_id, -100123456789)
        assert removed is True
        assert await service.is_whitelisted(user_id, -100123456789) is False

        # 5. Import back
        imported_count = await service.import_whitelist(user_id, exported)
        assert imported_count == 1
        assert await service.is_whitelisted(user_id, -100123456789) is True

    finally:
        ws_mod.db = original_db


@pytest.mark.asyncio
async def test_cleaner_strictly_skips_whitelisted():
    cleaner = AccountCleaner()
    whitelisted_item = DialogItem(
        chat_id=12345,
        title="Family Group",
        chat_type=ChatType.GROUP,
        is_whitelisted=True,  # Whitelisted
    )

    # Calling clean_single_item on whitelisted item must return SKIPPED without client interaction
    res = await cleaner.clean_single_item(client=None, item=whitelisted_item, dry_run=False)
    assert res.status == "SKIPPED"
    assert res.action == "SKIP"
    assert "Whitelist" in (res.error_message or "")


@pytest.mark.asyncio
async def test_whitelist_never_deleted():
    from unittest.mock import AsyncMock, MagicMock
    cleaner = AccountCleaner()
    mock_client = MagicMock()
    mock_client.delete_dialog = AsyncMock()
    mock_client.get_input_entity = AsyncMock()

    wl_items = [
        DialogItem(chat_id=101, title="Whitelisted 1", chat_type=ChatType.PRIVATE, is_whitelisted=True),
        DialogItem(chat_id=102, title="Whitelisted 2", chat_type=ChatType.CHANNEL, is_whitelisted=True),
        DialogItem(chat_id=103, title="Whitelisted 3", chat_type=ChatType.BOT, is_whitelisted=True),
    ]

    for item in wl_items:
        res = await cleaner.clean_single_item(client=mock_client, item=item, dry_run=False)
        assert res.status == "SKIPPED"
        assert res.action == "SKIP"

    # Ensure client was never called to delete or leave
    mock_client.delete_dialog.assert_not_called()
    mock_client.get_input_entity.assert_not_called()


@pytest.mark.asyncio
async def test_whitelist_overrides_scanner(tmp_path):
    import datetime
    from unittest.mock import AsyncMock, MagicMock
    from telethon.tl.types import User, Channel
    from telegram_client.scanner import AccountScanner

    scanner = AccountScanner()

    d1 = MagicMock()
    d1.id = 11111
    d1.name = "Spam Bot Whitelisted"
    d1.entity = User(id=11111, is_self=False, bot=True)
    d1.pinned = False
    d1.archived = False
    d1.unread_count = 0
    d1.date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=200)

    d2 = MagicMock()
    d2.id = 22222
    d2.name = "Dead Channel Whitelisted"
    d2.entity = Channel(
        id=22222,
        title="Dead Channel",
        photo=None,
        date=datetime.datetime.now(datetime.timezone.utc),
        broadcast=True,
    )
    d2.pinned = False
    d2.archived = False
    d2.unread_count = 0
    d2.date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=250)

    mock_client = MagicMock()
    mock_client.get_dialogs = AsyncMock(return_value=[d1, d2])

    test_db_path = str(tmp_path / "test_scanner_wl.db")
    test_db = Database(test_db_path)
    await test_db.init_db()

    import telegram_client.scanner as sc_mod
    import services.whitelist_service as ws_mod
    orig_sc_db = sc_mod.db
    orig_ws_db = ws_mod.db
    sc_mod.db = test_db
    ws_mod.db = test_db

    try:
        user_id = 777888
        await test_db.get_or_create_user(user_id, salt="salt123")
        wl_service = ws_mod.WhitelistService()
        await wl_service.add_to_whitelist(user_id, chat_id=11111, title="Spam Bot Whitelisted")
        await wl_service.add_to_whitelist(user_id, chat_id=22222, title="Dead Channel Whitelisted")

        result = await scanner.scan(mock_client, user_id)
        assert result.whitelisted_count == 2
        # Because both are whitelisted, recommended_count and actionable_count must be 0
        assert result.recommended_count == 0
        assert result.actionable_count == 0
        for item in result.items:
            assert item.is_whitelisted is True
    finally:
        sc_mod.db = orig_sc_db
        ws_mod.db = orig_ws_db


@pytest.mark.asyncio
async def test_whitelist_survives_cleanup(tmp_path):
    from unittest.mock import MagicMock
    test_db_path = str(tmp_path / "test_survive.db")
    test_db = Database(test_db_path)
    await test_db.init_db()

    import services.whitelist_service as ws_mod
    import telegram_client.cleaner as cl_mod

    orig_ws_db = ws_mod.db
    orig_cl_db = cl_mod.db
    ws_mod.db = test_db
    cl_mod.db = test_db

    try:
        service = WhitelistService()
        cleaner = AccountCleaner()
        user_id = 888999
        await test_db.get_or_create_user(user_id, salt="salt456")

        # 1. Add item to whitelist
        chat_id = 999888777
        await service.add_to_whitelist(user_id, chat_id=chat_id, title="Protected Group")
        assert await service.is_whitelisted(user_id, chat_id) is True

        # 2. Simulate cleanup job execution
        async with test_db.get_connection() as conn:
            cursor = await conn.execute(
                "INSERT INTO cleanup_jobs (telegram_id, job_type, status) VALUES (?, 'SELECTIVE', 'RUNNING')",
                (user_id,),
            )
            job_id = cursor.lastrowid
            await conn.commit()

        mock_client = MagicMock()

        items = [
            DialogItem(chat_id=chat_id, title="Protected Group", chat_type=ChatType.GROUP, is_whitelisted=True)
        ]
        results = await cleaner.execute_plan(mock_client, user_id, job_id, items, dry_run=False)

        assert len(results) == 1
        assert results[0].status == "SKIPPED"
        assert results[0].action == "SKIP"

        # 3. Whitelist remains intact in DB after cleanup job
        assert await service.is_whitelisted(user_id, chat_id) is True
        wl_items = await service.list_whitelist(user_id)
        assert len(wl_items) == 1
        assert wl_items[0]["chat_id"] == chat_id
    finally:
        ws_mod.db = orig_ws_db
        cl_mod.db = orig_cl_db

