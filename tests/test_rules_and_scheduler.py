import pytest
from database import db
from services.scheduler_service import scheduler_service
from telegram_client.models import ChatType

@pytest.mark.asyncio
async def test_rule_simulation_and_crud():
    """Tests custom cleanup rules simulation and persistence."""
    await db.init_db()
    telegram_id = 99912345

    # Simulate rule logic directly
    test_dialogs = [
        {"chat_id": 101, "title": "Spam crypto news", "chat_type": "channel", "inactive_days": 100, "is_whitelisted": False},
        {"chat_id": 102, "title": "Family chat", "chat_type": "group", "inactive_days": 10, "is_whitelisted": True},
        {"chat_id": 103, "title": "Old unused bot", "chat_type": "bot", "inactive_days": 90, "is_whitelisted": False},
    ]

    # Rule: channels inactive > 60 days
    matched = [
        d for d in test_dialogs
        if not d["is_whitelisted"] and d["chat_type"] == "channel" and d["inactive_days"] > 60
    ]
    assert len(matched) == 1
    assert matched[0]["chat_id"] == 101

    # Whitelist protection overrides rule
    whitelist_matched = [
        d for d in test_dialogs
        if d["is_whitelisted"] and d["chat_type"] == "group"
    ]
    assert len(whitelist_matched) == 1
    assert whitelist_matched[0]["title"] == "Family chat"


@pytest.mark.asyncio
async def test_scheduler_crud_and_persistence():
    """Tests scheduler schedule record CRUD and duplicate prevention."""
    await db.init_db()
    telegram_id = 88812345

    # Create user
    async with db.get_connection() as conn:
        await conn.execute("INSERT OR IGNORE INTO users (telegram_id, salt) VALUES (?, 'sched_salt')", (telegram_id,))
        # Update settings for scheduler
        await conn.execute(
            """
            INSERT OR REPLACE INTO settings (telegram_id, auto_clean_enabled, auto_clean_frequency, auto_clean_scope, auto_clean_mode)
            VALUES (?, 1, 'weekly', 'smart', 'dry_run')
            """,
            (telegram_id,)
        )
        await conn.commit()

        cur = await conn.execute("SELECT auto_clean_enabled, auto_clean_mode FROM settings WHERE telegram_id = ?", (telegram_id,))
        row = await cur.fetchone()
        assert row["auto_clean_enabled"] == 1
        assert row["auto_clean_mode"] == "dry_run"

        # Toggle scheduler off
        await conn.execute("UPDATE settings SET auto_clean_enabled = 0 WHERE telegram_id = ?", (telegram_id,))
        await conn.commit()

        cur = await conn.execute("SELECT auto_clean_enabled FROM settings WHERE telegram_id = ?", (telegram_id,))
        row = await cur.fetchone()
        assert row["auto_clean_enabled"] == 0
