import os
import pytest
from database import Database, db


@pytest.mark.asyncio
async def test_database_initialization_and_migrations(tmp_path):
    """Test that a new database initializes all tables and migration records cleanly."""
    db_file = str(tmp_path / "test_init.db")
    test_db = Database(db_file)
    await test_db.init_db()

    async with test_db.get_connection() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in await cursor.fetchall()}
        
        expected_tables = {
            "users",
            "sessions",
            "whitelist",
            "cleanup_jobs",
            "cleanup_items",
            "settings",
            "schedules",
            "audit_log",
            "rejoin_manifest",
            "hygiene_score_history",
            "schema_migrations",
            "consents",
            "support_tickets",
            "ticket_messages",
            "user_credentials",
            "rate_limits",
        }
        for table in expected_tables:
            assert table in tables, f"Expected table {table} missing from schema"

        # Verify migrations recorded
        cur_mig = await conn.execute("SELECT version, name FROM schema_migrations ORDER BY version ASC")
        migrations = await cur_mig.fetchall()
        assert len(migrations) == 6
        assert migrations[0]["version"] == 1
        assert migrations[-1]["version"] == 6


@pytest.mark.asyncio
async def test_migration_preserves_existing_legacy_data(tmp_path):
    """Test that existing legacy database is upgraded without data loss."""
    db_file = str(tmp_path / "legacy.db")
    
    # Create legacy database with v1 schema directly
    import sqlite3
    sync_conn = sqlite3.connect(db_file)
    sync_conn.execute("""
    CREATE TABLE users (
        telegram_id INTEGER PRIMARY KEY,
        phone TEXT,
        salt TEXT NOT NULL,
        language TEXT DEFAULT 'ru',
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    sync_conn.execute("INSERT INTO users (telegram_id, phone, salt) VALUES (777888999, '+1234567890', 'salt123')")
    sync_conn.commit()
    sync_conn.close()

    # Now upgrade via Database migrations
    test_db = Database(db_file)
    await test_db.init_db()

    # Verify user is completely intact
    async with test_db.get_connection() as conn:
        cur = await conn.execute("SELECT * FROM users WHERE telegram_id = 777888999")
        user = await cur.fetchone()
        assert user is not None
        assert user["telegram_id"] == 777888999
        assert user["phone"] == "+1234567890"
        assert user["salt"] == "salt123"

        # Verify new tables are now available
        cur_t = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consents'")
        assert await cur_t.fetchone() is not None


@pytest.mark.asyncio
async def test_consents_crud_and_withdrawal(tmp_path):
    """Test consents table recording and withdrawal."""
    db_file = str(tmp_path / "test_consents.db")
    test_db = Database(db_file)
    user_id = 112233
    await test_db.get_or_create_user(user_id, salt="s")

    # Record consent
    cid = await test_db.record_consent(
        telegram_id=user_id,
        agreement_version="2.0.0",
        privacy_version="2.0.0",
        terms_hash="abc_terms_hash",
        ip_address="127.0.0.1",
        user_agent="TelegramBot/2.0",
    )
    assert cid > 0

    active = await test_db.get_active_consent(user_id)
    assert active is not None
    assert active["agreement_version"] == "2.0.0"
    assert active["withdrawn_at"] is None

    # Withdraw consent
    withdrawn = await test_db.withdraw_consent(user_id)
    assert withdrawn is True

    # Check that active consent is now None
    active_after = await test_db.get_active_consent(user_id)
    assert active_after is None


@pytest.mark.asyncio
async def test_support_tickets_system(tmp_path):
    """Test support tickets creation with CLIN-XXXXX identifier, messages threading, and status updates."""
    db_file = str(tmp_path / "test_tickets.db")
    test_db = Database(db_file)
    user_id = 445566
    await test_db.get_or_create_user(user_id, salt="s")

    ticket = await test_db.create_support_ticket(
        telegram_id=user_id,
        category="auth",
        subject="Login 2FA issue",
        description="Password rejected",
        priority="high",
    )
    assert ticket["ticket_number"].startswith("CLIN-")
    ticket_num = ticket["ticket_number"]

    fetched = await test_db.get_ticket(ticket_num)
    assert fetched is not None
    assert fetched["status"] == "open"
    assert fetched["priority"] == "high"

    # Add message
    msg_id = await test_db.add_ticket_message(
        ticket_id=ticket["id"],
        sender_type="user",
        sender_id=user_id,
        message="I tried again and still failing.",
    )
    assert msg_id > 0

    # Add support reply
    msg_id2 = await test_db.add_ticket_message(
        ticket_id=ticket["id"],
        sender_type="support",
        sender_id=999,
        message="Please reset your 2FA cloud password via official Telegram client.",
    )
    assert msg_id2 > 0

    messages = await test_db.get_ticket_messages(ticket["id"])
    assert len(messages) == 2
    assert messages[0]["sender_type"] == "user"
    assert messages[1]["sender_type"] == "support"

    # Update status
    updated = await test_db.update_ticket_status(ticket_num, "resolved")
    assert updated is True

    resolved_ticket = await test_db.get_ticket(ticket_num)
    assert resolved_ticket["status"] == "resolved"
    assert resolved_ticket["closed_at"] is not None


@pytest.mark.asyncio
async def test_user_credentials_crud(tmp_path):
    """Test user credentials storage and retrieval."""
    db_file = str(tmp_path / "test_cred.db")
    test_db = Database(db_file)
    user_id = 556677
    await test_db.get_or_create_user(user_id, salt="s")

    await test_db.set_user_credentials(
        telegram_id=user_id,
        encrypted_api_id="enc_id_12345",
        encrypted_api_hash="enc_hash_abcdef",
        is_custom=1,
    )

    creds = await test_db.get_user_credentials(user_id)
    assert creds is not None
    assert creds["encrypted_api_id"] == "enc_id_12345"
    assert creds["encrypted_api_hash"] == "enc_hash_abcdef"
    assert creds["is_custom"] == 1

    # Delete
    deleted = await test_db.delete_user_credentials(user_id)
    assert deleted is True
    assert await test_db.get_user_credentials(user_id) is None


@pytest.mark.asyncio
async def test_foreign_key_cascades(tmp_path):
    """Test that deleting a user cascades and wipes child records cleanly."""
    db_file = str(tmp_path / "test_cascade.db")
    test_db = Database(db_file)
    user_id = 888999
    await test_db.get_or_create_user(user_id, salt="s")

    await test_db.record_consent(user_id, "1.0", "1.0", "h")
    t = await test_db.create_support_ticket(user_id, "gen", "sub", "desc")
    await test_db.set_user_credentials(user_id, "id", "h", 1)

    async with test_db.get_connection() as conn:
        # Delete user
        await conn.execute("DELETE FROM users WHERE telegram_id = ?", (user_id,))
        await conn.commit()

        # Check cascading deletion
        cur_c = await conn.execute("SELECT COUNT(*) as cnt FROM consents WHERE telegram_id = ?", (user_id,))
        assert (await cur_c.fetchone())["cnt"] == 0

        cur_t = await conn.execute("SELECT COUNT(*) as cnt FROM support_tickets WHERE telegram_id = ?", (user_id,))
        assert (await cur_t.fetchone())["cnt"] == 0

        cur_cr = await conn.execute("SELECT COUNT(*) as cnt FROM user_credentials WHERE telegram_id = ?", (user_id,))
        assert (await cur_cr.fetchone())["cnt"] == 0
