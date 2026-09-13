import pytest
from unittest.mock import AsyncMock, patch
from services.scheduler_service import SchedulerService
from telegram_client.models import ChatType, CleanupItemResult, DialogItem


@pytest.mark.asyncio
async def test_scheduler_dry_run_guarantee():
    scheduler = SchedulerService()
    user_id = 777888

    received_notifications = []

    async def mock_bot_callback(chat_id: int, text: str):
        received_notifications.append((chat_id, text))

    scheduler.set_bot_callback(mock_bot_callback)

    # Mock client_manager.has_active_session to True
    with patch("services.scheduler_service.client_manager.has_active_session", new=AsyncMock(return_value=True)):
        # Mock cleanup_service.run_cleanup
        mock_summary = {
            "job_id": 101,
            "status": "COMPLETED",
            "job_type": "SMART_CLEAN",
            "total": 15,
            "processed": 15,
            "success": 15,
            "skipped": 0,
            "errors": 0,
            "dry_run": True,
            "duration": "00:05",
        }
        with patch("services.cleanup_service.cleanup_service.run_cleanup", new=AsyncMock(return_value=mock_summary)) as mock_run:
            # Execute scheduled task in default 'dry_run' mode
            await scheduler.execute_scheduled_task(telegram_id=user_id, scope="smart", mode="dry_run")

            # Check that run_cleanup was called with dry_run = True
            mock_run.assert_called_once()
            called_plan = mock_run.call_args[0][1]
            assert called_plan.dry_run is True
            assert called_plan.is_smart_clean is True

            # Verify notification text highlights DRY-RUN
            assert len(received_notifications) == 1
            assert received_notifications[0][0] == user_id
            assert "DRY-RUN" in received_notifications[0][1]
            assert "Никаких изменений не внесено" in received_notifications[0][1]
