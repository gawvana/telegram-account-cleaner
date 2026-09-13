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
