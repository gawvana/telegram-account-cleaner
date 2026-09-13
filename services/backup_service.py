import csv
import io
from typing import Any, Dict, List, Optional
from database import db
from services.whitelist_service import whitelist_service
from utils.logger import logger


class BackupService:
    """Handles full user data backup, restore, and Rejoin Manifest exports."""

    async def get_rejoin_manifest(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Returns list of public channels and groups left during cleanups."""
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT title, username, invite_link, chat_type, left_at
                FROM rejoin_manifest
                WHERE telegram_id = ?
                ORDER BY left_at DESC
                """,
                (telegram_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def export_full_backup(self, telegram_id: int) -> Dict[str, Any]:
        """Exports user whitelist, settings, history, and rejoin manifest."""
        # 1. Whitelist
        wl_items = await whitelist_service.export_whitelist(telegram_id)

        # 2. Settings
        async with db.get_connection() as conn:
            s_cursor = await conn.execute(
                "SELECT * FROM settings WHERE telegram_id = ?", (telegram_id,)
            )
            s_row = await s_cursor.fetchone()
            settings_dict = dict(s_row) if s_row else {}

            # 3. Rejoin Manifest
            manifest = await self.get_rejoin_manifest(telegram_id)

            # 4. Job History Summary
            h_cursor = await conn.execute(
                """
                SELECT id, job_type, status, total_items, processed_items, skipped_items,
                       error_items, started_at, finished_at, dry_run
                FROM cleanup_jobs
                WHERE telegram_id = ?
                ORDER BY id DESC
                LIMIT 100
                """,
                (telegram_id,),
            )
            jobs = [dict(r) for r in await h_cursor.fetchall()]

        return {
            "version": "2.0",
            "telegram_id": telegram_id,
            "whitelist": wl_items,
            "settings": settings_dict,
            "rejoin_manifest": manifest,
            "jobs_history": jobs,
        }

    async def import_backup(self, telegram_id: int, payload: Dict[str, Any]) -> Dict[str, int]:
        """Imports settings and whitelist from backup."""
        imported_wl = 0
        if "whitelist" in payload and isinstance(payload["whitelist"], list):
            imported_wl = await whitelist_service.import_whitelist(telegram_id, payload["whitelist"])

        if "settings" in payload and isinstance(payload["settings"], dict):
            s = payload["settings"]
            async with db.get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE settings SET
                        auto_clean_enabled = ?,
                        auto_clean_frequency = ?,
                        auto_clean_scope = ?,
                        auto_clean_mode = ?,
                        dead_channel_days = ?,
                        notifications_enabled = ?
                    WHERE telegram_id = ?
                    """,
                    (
                        s.get("auto_clean_enabled", 0),
                        s.get("auto_clean_frequency", "weekly"),
                        s.get("auto_clean_scope", "smart"),
                        s.get("auto_clean_mode", "dry_run"),
                        s.get("dead_channel_days", 60),
                        s.get("notifications_enabled", 1),
                        telegram_id,
                    ),
                )
                await conn.commit()

        logger.info(f"User {telegram_id} imported backup: {imported_wl} whitelist items")
        return {"imported_whitelist": imported_wl}

    async def export_history_csv(self, telegram_id: int) -> str:
        """Generates CSV string of cleanup action history."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Job ID", "Chat Title", "Chat Type", "Action", "Status", "Error", "Timestamp"])

        async with db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT ci.job_id, ci.chat_title, ci.chat_type, ci.action, ci.status, ci.error_message, ci.processed_at
                FROM cleanup_items ci
                JOIN cleanup_jobs cj ON ci.job_id = cj.id
                WHERE cj.telegram_id = ?
                ORDER BY ci.id DESC
                LIMIT 500
                """,
                (telegram_id,),
            )
            rows = await cursor.fetchall()
            for r in rows:
                writer.writerow([r["job_id"], r["chat_title"], r["chat_type"], r["action"], r["status"], r["error_message"] or "", r["processed_at"]])

        return output.getvalue()


backup_service = BackupService()
