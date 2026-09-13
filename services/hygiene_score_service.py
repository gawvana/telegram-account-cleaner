import datetime
from typing import Any, Dict, List, Optional
from database import db
from utils.logger import logger


class HygieneScoreService:
    """Computes and tracks transparent, pressure-free Account Hygiene Score."""

    @staticmethod
    def calculate_score(total_dialogs: int, whitelisted_count: int, cleaned_count: int) -> int:
        """Formula: 100 * (whitelisted + cleaned) / max(total_dialogs, 1), clamped 0..100."""
        if total_dialogs <= 0:
            return 100
        raw = 100.0 * (whitelisted_count + cleaned_count) / max(total_dialogs, 1)
        return max(0, min(int(round(raw)), 100))

    async def get_current_score(self, telegram_id: int) -> Dict[str, Any]:
        """Calculates current score from database stats and latest history."""
        async with db.get_connection() as conn:
            # Get latest snapshot
            cursor = await conn.execute(
                "SELECT * FROM hygiene_score_history WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
                (telegram_id,),
            )
            latest = await cursor.fetchone()

            # Count total cleaned items from completed jobs
            c_cursor = await conn.execute(
                """
                SELECT COUNT(*) as total_cleaned
                FROM cleanup_items ci
                JOIN cleanup_jobs cj ON ci.job_id = cj.id
                WHERE cj.telegram_id = ? AND ci.status = 'SUCCESS' AND cj.dry_run = 0
                """,
                (telegram_id,),
            )
            c_row = await c_cursor.fetchone()
            total_cleaned = c_row["total_cleaned"] if c_row else 0

            # Count whitelist
            w_cursor = await conn.execute(
                "SELECT COUNT(*) as total_wl FROM whitelist WHERE telegram_id = ?",
                (telegram_id,),
            )
            w_row = await w_cursor.fetchone()
            total_wl = w_row["total_wl"] if w_row else 0

            if latest:
                return {
                    "score": latest["score"],
                    "total_dialogs": latest["total_dialogs"],
                    "whitelisted": latest["whitelisted_count"],
                    "cleaned": latest["cleaned_count"],
                    "recorded_at": latest["recorded_at"],
                }

            # Default initial estimation
            score = self.calculate_score(
                total_dialogs=total_wl + total_cleaned or 1,
                whitelisted_count=total_wl,
                cleaned_count=total_cleaned,
            )
            return {
                "score": score,
                "total_dialogs": total_wl + total_cleaned,
                "whitelisted": total_wl,
                "cleaned": total_cleaned,
                "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

    async def record_snapshot(
        self, telegram_id: int, total_dialogs: int, whitelisted_count: int, cleaned_count: int
    ) -> int:
        """Computes and records a new score snapshot."""
        score = self.calculate_score(total_dialogs, whitelisted_count, cleaned_count)
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO hygiene_score_history (telegram_id, score, total_dialogs, whitelisted_count, cleaned_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_id, score, total_dialogs, whitelisted_count, cleaned_count),
            )
            await conn.commit()

        logger.info(f"Recorded hygiene score snapshot for user {telegram_id}: {score}/100")
        return score

    async def get_history(self, telegram_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        """Returns time series of score snapshots for Chart.js display."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT score, total_dialogs, whitelisted_count, cleaned_count, recorded_at
                FROM hygiene_score_history
                WHERE telegram_id = ?
                ORDER BY recorded_at ASC
                LIMIT ?
                """,
                (telegram_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


hygiene_score_service = HygieneScoreService()
