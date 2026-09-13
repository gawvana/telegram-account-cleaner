from typing import Any, Dict, List
from database import db


class StatisticsService:
    """Provides user-level and privacy-preserving aggregate statistics."""

    async def get_user_statistics(self, telegram_id: int) -> Dict[str, Any]:
        """Calculates comprehensive cleanup stats for an individual user."""
        async with db.get_connection() as conn:
            # Aggregate jobs count
            j_cursor = await conn.execute(
                """
                SELECT
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_jobs,
                    SUM(total_items) as total_target_items,
                    SUM(processed_items) as total_processed,
                    SUM(skipped_items) as total_skipped,
                    SUM(error_items) as total_errors
                FROM cleanup_jobs
                WHERE telegram_id = ? AND dry_run = 0
                """,
                (telegram_id,),
            )
            j_row = await j_cursor.fetchone()

            # Breakdown by chat_type
            t_cursor = await conn.execute(
                """
                SELECT ci.chat_type, COUNT(*) as count
                FROM cleanup_items ci
                JOIN cleanup_jobs cj ON ci.job_id = cj.id
                WHERE cj.telegram_id = ? AND ci.status = 'SUCCESS' AND cj.dry_run = 0
                GROUP BY ci.chat_type
                """,
                (telegram_id,),
            )
            type_counts = {r["chat_type"]: r["count"] for r in await t_cursor.fetchall()}

            # Recent jobs
            r_cursor = await conn.execute(
                """
                SELECT id, job_type, status, total_items, processed_items, skipped_items, error_items, started_at, finished_at, dry_run
                FROM cleanup_jobs
                WHERE telegram_id = ?
                ORDER BY id DESC LIMIT 10
                """,
                (telegram_id,),
            )
            recent_jobs = [dict(r) for r in await r_cursor.fetchall()]

            return {
                "summary": dict(j_row) if j_row else {},
                "type_breakdown": type_counts,
                "recent_jobs": recent_jobs,
            }

    async def get_anonymized_admin_stats(self) -> Dict[str, Any]:
        """Returns strictly anonymized aggregate statistics for the instance operator."""
        async with db.get_connection() as conn:
            # Total users
            u_cursor = await conn.execute("SELECT COUNT(*) as count FROM users")
            u_row = await u_cursor.fetchone()
            total_users = u_row["count"] if u_row else 0

            # Jobs in last 7 days
            j7_cursor = await conn.execute(
                """
                SELECT
                    COUNT(*) as jobs_7d,
                    SUM(error_items) as errors_7d,
                    SUM(processed_items) as processed_7d
                FROM cleanup_jobs
                WHERE started_at >= datetime('now', '-7 days')
                """
            )
            j7_row = await j7_cursor.fetchone()
            jobs_7d = j7_row["jobs_7d"] if j7_row else 0
            errors_7d = j7_row["errors_7d"] or 0
            processed_7d = j7_row["processed_7d"] or 0

            error_rate = 0.0
            if processed_7d > 0:
                error_rate = round((errors_7d / processed_7d) * 100, 2)

            return {
                "total_users": total_users,
                "jobs_last_7_days": jobs_7d,
                "items_processed_7d": processed_7d,
                "error_rate_percent": error_rate,
                "privacy_guarantee": "Strictly anonymized. No chat names, titles, or PII exposed.",
            }


statistics_service = StatisticsService()
