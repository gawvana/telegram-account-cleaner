import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from database import Database
from domain.models import ChatType as DomainChatType
from telegram_client.cleaner import AccountCleaner
from telegram_client.models import ChatType, CleanupPlan, DialogItem
from services.cleanup_service import CleanupService, ActiveJobContext
from utils.progress import ProgressTracker


@pytest.mark.asyncio
async def test_clean_single_item_whitelist_protection():
    cleaner = AccountCleaner()
    mock_client = MagicMock()

    whitelisted_item = DialogItem(
        chat_id=1234567,
        title="Protected Family Group",
        chat_type=ChatType.GROUP,
        is_whitelisted=True,
    )

    result = await cleaner.clean_single_item(mock_client, whitelisted_item, dry_run=False)
    assert result.status == "SKIPPED"
    assert result.action == "SKIP"
    assert "Whitelist" in result.error_message


@pytest.mark.asyncio
async def test_clean_single_item_dry_run_safety():
    cleaner = AccountCleaner()
    mock_client = MagicMock()

    item = DialogItem(
        chat_id=9876543,
        title="Spam Channel",
        chat_type=ChatType.CHANNEL,
        is_whitelisted=False,
    )

    result = await cleaner.clean_single_item(mock_client, item, dry_run=True)
    assert result.status == "SUCCESS"
    assert result.action == "LEAVE"
    # Ensure no network methods were invoked on mock_client
    mock_client.delete_dialog.assert_not_called()


@pytest.mark.asyncio
async def test_cooperative_cancellation_service():
    service = CleanupService()
    user_id = 777888999

    cancel_evt = asyncio.Event()
    progress = ProgressTracker(total=10, title="Test Job")
    ctx = ActiveJobContext(job_id=101, cancel_event=cancel_evt, progress=progress)

    async with service._lock:
        service._active_jobs[user_id] = ctx

    assert cancel_evt.is_set() is False
    stopped = await service.stop_cleanup(user_id)
    assert stopped is True
    assert cancel_evt.is_set() is True


@pytest.mark.asyncio
async def test_cleanup_completed_with_warnings(tmp_path):
    test_db_path = str(tmp_path / "test_cleanup.db")
    test_db = Database(test_db_path)
    await test_db.init_db()

    user_id = 333222111
    await test_db.get_or_create_user(user_id, salt="somesalt")

    async with test_db.get_connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO cleanup_jobs (telegram_id, job_type, status, total_items, processed_items, error_items)
            VALUES (?, 'SMART_CLEAN', 'COMPLETED_WITH_WARNINGS', 10, 10, 2)
            """,
            (user_id,),
        )
        job_id = cursor.lastrowid
        await conn.commit()

        cursor = await conn.execute("SELECT status, error_items FROM cleanup_jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        assert row["status"] == "COMPLETED_WITH_WARNINGS"
        assert row["error_items"] == 2


@pytest.mark.asyncio
async def test_clean_single_item_creator_protection():
    cleaner = AccountCleaner()
    mock_client = MagicMock()

    creator_item = DialogItem(
        chat_id=555444333,
        title="My Own Channel",
        chat_type=ChatType.CHANNEL,
        is_creator=True,
        requires_special_rights=True,
        is_whitelisted=False,
    )

    result = await cleaner.clean_single_item(mock_client, creator_item, dry_run=False)
    assert result.status == "SKIPPED"
    assert result.action == "SKIP"
    assert "создателем" in result.error_message


@pytest.mark.asyncio
async def test_clean_single_item_system_and_self_protection():
    cleaner = AccountCleaner()
    mock_client = MagicMock()

    service_item = DialogItem(
        chat_id=777000,
        title="Telegram Notifications",
        chat_type=ChatType.PRIVATE,
        can_delete=False,
        can_leave=False,
        is_whitelisted=False,
    )

    result = await cleaner.clean_single_item(mock_client, service_item, dry_run=False)
    assert result.status == "SKIPPED"
    assert result.action == "SKIP"
    assert "системный диалог" in result.error_message


def test_scan_result_attribute_contract():
    from domain.models import ScanResult

    sr = ScanResult(
        total_dialogs=15,
        private_chats=5,
        bot_chats=3,
        group_chats=4,
        channel_chats=3,
    )

    # Verify both naming conventions are accessible
    assert sr.private_chats == 5
    assert sr.bot_chats == 3
    assert sr.group_chats == 4
    assert sr.channel_chats == 3
    assert hasattr(sr, "private_count")
    assert hasattr(sr, "bots_count")
