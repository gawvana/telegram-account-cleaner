import asyncio
import datetime
from typing import Any, Callable, Dict, List, Optional
from database import db
from services.hygiene_score_service import hygiene_score_service
from telegram_client.cleaner import cleaner
from telegram_client.exceptions import ConcurrentJobError, UserCancelledException
from telegram_client.manager import client_manager
from telegram_client.models import ChatType, CleanupItemResult, CleanupPlan, DialogItem
from telegram_client.scanner import scanner
from utils.logger import logger
from utils.progress import ProgressTracker


class ActiveJobContext:
    def __init__(self, job_id: int, cancel_event: asyncio.Event, progress: ProgressTracker):
        self.job_id = job_id
        self.cancel_event = cancel_event
        self.progress = progress


class CleanupService:
    """Orchestrates scanning, filtering, plan execution, and cancellation."""

    def __init__(self):
        self._active_jobs: Dict[int, ActiveJobContext] = {}
        self._lock = asyncio.Lock()

    def get_active_tracker(self, telegram_id: int) -> Optional[ProgressTracker]:
        ctx = self._active_jobs.get(telegram_id)
        return ctx.progress if ctx else None

    async def stop_cleanup(self, telegram_id: int) -> bool:
        """Signals active job cancellation via cooperative asyncio.Event."""
        async with self._lock:
            ctx = self._active_jobs.get(telegram_id)
            if ctx:
                ctx.cancel_event.set()
                logger.info(f"Cancellation requested for user {telegram_id}, job {ctx.job_id}")
                return True
            return False

    async def run_cleanup(
        self,
        telegram_id: int,
        plan: CleanupPlan,
        progress_callback: Optional[Callable[[ProgressTracker], Any]] = None,
    ) -> Dict[str, Any]:
        """Runs complete cleanup sequence with safety checks, whitelist, and progress reporting."""
        async with self._lock:
            if telegram_id in self._active_jobs:
                raise ConcurrentJobError("Операция уже выполняется. Дождитесь её завершения или отмените.")

        job_type = "MAX_CLEAN" if plan.is_max_clean else ("SMART_CLEAN" if plan.is_smart_clean else "CATEGORY_CLEAN")

        # 1. Create DB Job Record
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO cleanup_jobs (telegram_id, job_type, status, dry_run)
                VALUES (?, ?, 'RUNNING', ?)
                """,
                (telegram_id, job_type, 1 if plan.dry_run else 0),
            )
            job_id = cursor.lastrowid
            await conn.commit()

        cancel_event = asyncio.Event()
        progress = ProgressTracker(
            total=1,
            title="Очистка Telegram-аккаунта" if not plan.dry_run else "🧪 DRY-RUN Предпросмотр",
            update_callback=progress_callback,
        )

        ctx = ActiveJobContext(job_id=job_id, cancel_event=cancel_event, progress=progress)
        async with self._lock:
            self._active_jobs[telegram_id] = ctx

        start_dt = datetime.datetime.now(datetime.timezone.utc)
        results: List[CleanupItemResult] = []
        status = "COMPLETED"

        try:
            async with client_manager.get_client(telegram_id) as client:
                # 2. Scan dialogs
                scan = await scanner.scan(client, telegram_id)

                # 3. Filter dialogs based on plan
                target_items: List[DialogItem] = []
                for item in scan.items:
                    # Strict whitelist bypass
                    if item.is_whitelisted:
                        continue

                    if plan.is_smart_clean:
                        if item.heuristics.recommended_for_cleanup:
                            target_items.append(item)
                    elif plan.target_chat_ids:
                        if item.chat_id in plan.target_chat_ids:
                            target_items.append(item)
                    elif plan.target_types:
                        if item.chat_type in plan.target_types:
                            target_items.append(item)
                    elif plan.is_max_clean:
                        target_items.append(item)

                progress.total = max(len(target_items), 1)

                # 4. Execute cleanup
                results = await cleaner.execute_plan(
                    client=client,
                    telegram_id=telegram_id,
                    job_id=job_id,
                    items=target_items,
                    dry_run=plan.dry_run,
                    cancel_event=cancel_event,
                    progress_tracker=progress,
                )

        except UserCancelledException:
            status = "CANCELLED"
            logger.info(f"Job {job_id} cancelled by user {telegram_id}")
        except Exception as e:
            status = "FAILED"
            logger.error(f"Job {job_id} failed for user {telegram_id}: {e}", exc_info=True)
            raise
        finally:
            await progress.finish()
            async with self._lock:
                self._active_jobs.pop(telegram_id, None)

            # 5. Finalize DB Record
            processed = progress.processed
            skipped = progress.skipped
            errors = progress.errors
            success = max(processed - skipped - errors, 0)
            if status == "COMPLETED" and errors > 0:
                status = "COMPLETED_WITH_WARNINGS"
            finished_dt = datetime.datetime.now(datetime.timezone.utc)

            async with db.get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE cleanup_jobs SET
                        status = ?,
                        total_items = ?,
                        processed_items = ?,
                        skipped_items = ?,
                        error_items = ?,
                        finished_at = ?
                    WHERE id = ?
                    """,
                    (status, progress.total, processed, skipped, errors, finished_dt.isoformat(), job_id),
                )
                await conn.commit()

            # 6. Update Hygiene Score
            if not plan.dry_run and status == "COMPLETED":
                # Recalculate snapshot
                await hygiene_score_service.record_snapshot(
                    telegram_id=telegram_id,
                    total_dialogs=scan.total_dialogs if 'scan' in locals() else progress.total,
                    whitelisted_count=scan.whitelisted_count if 'scan' in locals() else 0,
                    cleaned_count=success,
                )

        duration = (finished_dt - start_dt).total_seconds()
        mins, secs = divmod(int(duration), 60)

        return {
            "job_id": job_id,
            "status": status,
            "job_type": job_type,
            "total": progress.total,
            "processed": processed,
            "success": success,
            "skipped": skipped,
            "errors": errors,
            "dry_run": plan.dry_run,
            "duration": f"{mins:02d}:{secs:02d}",
        }


cleanup_service = CleanupService()
