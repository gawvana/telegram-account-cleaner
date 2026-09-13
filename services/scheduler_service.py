import asyncio
import datetime
from typing import Any, Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from database import db
from telegram_client.manager import client_manager
from telegram_client.models import ChatType, CleanupPlan
from utils.logger import logger


class SchedulerService:
    """Manages scheduled periodic cleanups and dry-run reports via APScheduler."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._bot_notification_callback = None

    def set_bot_callback(self, callback) -> None:
        """Sets callback function to send Telegram notifications upon job completion."""
        self._bot_notification_callback = callback

    def start(self) -> None:
        """Starts the APScheduler instance if enabled in settings."""
        if not settings.SCHEDULER_ENABLED:
            logger.info("Scheduler is disabled in settings.")
            return

        if self.scheduler is None:
            self.scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)
            self.scheduler.start()
            logger.info(f"APScheduler started with timezone {settings.SCHEDULER_TIMEZONE}")

    def shutdown(self) -> None:
        """Gracefully shuts down APScheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped.")

    async def sync_all_schedules(self) -> None:
        """Loads all active user schedules from SQLite and registers APScheduler jobs."""
        if not self.scheduler or not self.scheduler.running:
            return

        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM schedules WHERE is_active = 1"
            )
            rows = await cursor.fetchall()

        for r in rows:
            self.schedule_user_job(
                telegram_id=r["telegram_id"],
                frequency=r["frequency"],
                scope=r["scope"],
                mode=r["mode"],
            )

    def schedule_user_job(
        self, telegram_id: int, frequency: str = "weekly", scope: str = "smart", mode: str = "dry_run"
    ) -> None:
        """Registers a user cron trigger in APScheduler."""
        if not self.scheduler or not self.scheduler.running:
            return

        job_id = f"user_schedule_{telegram_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Build cron trigger
        if frequency == "daily":
            trigger = CronTrigger(hour=9, minute=0, timezone=settings.SCHEDULER_TIMEZONE)
        elif frequency == "monthly":
            trigger = CronTrigger(day=1, hour=9, minute=0, timezone=settings.SCHEDULER_TIMEZONE)
        else:  # default weekly on Monday
            trigger = CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=settings.SCHEDULER_TIMEZONE)

        self.scheduler.add_job(
            self.execute_scheduled_task,
            trigger=trigger,
            id=job_id,
            args=[telegram_id, scope, mode],
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info(f"Scheduled job registered for user {telegram_id} ({frequency}, {scope}, {mode})")

    async def execute_scheduled_task(self, telegram_id: int, scope: str, mode: str) -> None:
        """Executed by APScheduler. Strict default is DRY-RUN unless explicitly configured."""
        from services.cleanup_service import cleanup_service

        logger.info(f"Running scheduled cleaner task for user {telegram_id} (scope={scope}, mode={mode})")

        # Check if user has active session
        has_session = await client_manager.has_active_session(telegram_id)
        if not has_session:
            logger.warning(f"Skipping scheduled task for {telegram_id}: no active session.")
            return

        # Default is strictly DRY-RUN unless mode is explicitly 'auto'
        is_dry_run = (mode != "auto")

        plan = CleanupPlan(
            is_smart_clean=(scope == "smart"),
            is_max_clean=(scope == "all"),
            target_types=[ChatType.BOT] if scope == "bots" else [],
            dry_run=is_dry_run,
        )

        try:
            summary = await cleanup_service.run_cleanup(telegram_id, plan)
            logger.info(f"Scheduled task completed for user {telegram_id}: {summary}")

            # Send notification via bot if callback configured
            if self._bot_notification_callback:
                prefix = "🧪 **ОТЧЁТ АВТООЧИСТКИ (DRY-RUN)**" if is_dry_run else "✅ **АВТООЧИСТКА ЗАВЕРШЕНА**"
                msg = (
                    f"{prefix}\n\n"
                    f"🎯 Область: `{scope}`\n"
                    f"📊 Обработано: `{summary['processed']}`\n"
                    f"✅ Успешно: `{summary['success']}`\n"
                    f"⏭ Пропущено: `{summary['skipped']}`\n"
                    f"⏱ Время: `{summary['duration']}`\n\n"
                    + ("_Никаких изменений не внесено (режим отчёта)._" if is_dry_run else "")
                )
                await self._bot_notification_callback(telegram_id, msg)

        except Exception as e:
            logger.error(f"Error executing scheduled task for {telegram_id}: {e}")


scheduler_service = SchedulerService()
