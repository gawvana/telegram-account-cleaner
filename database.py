import datetime
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional
import aiosqlite

from config import settings
from utils.logger import logger


class Database:
    """Async SQLite database manager for Telegram Account Cleaner."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Async context manager for SQLite connections with row factory configured."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA journal_mode = WAL;")
            yield conn

    async def init_db(self) -> None:
        """Initializes all database tables and indexes."""
        logger.info(f"Initializing database at: {self.db_path}")
        async with self.get_connection() as conn:
            await conn.executescript(
                """
                -- Users
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    phone TEXT,
                    salt TEXT NOT NULL,
                    language TEXT DEFAULT 'ru',
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Sessions (path to encrypted session file)
                CREATE TABLE IF NOT EXISTS sessions (
                    telegram_id INTEGER PRIMARY KEY,
                    session_path TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Whitelist
                CREATE TABLE IF NOT EXISTS whitelist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    title TEXT,
                    username TEXT,
                    rule_pattern TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                    UNIQUE(telegram_id, chat_id)
                );

                -- Cleanup Jobs
                CREATE TABLE IF NOT EXISTS cleanup_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_items INTEGER DEFAULT 0,
                    processed_items INTEGER DEFAULT 0,
                    skipped_items INTEGER DEFAULT 0,
                    error_items INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP,
                    dry_run INTEGER DEFAULT 0,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Cleanup Items
                CREATE TABLE IF NOT EXISTS cleanup_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    chat_title TEXT,
                    chat_type TEXT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES cleanup_jobs(id) ON DELETE CASCADE
                );

                -- Settings
                CREATE TABLE IF NOT EXISTS settings (
                    telegram_id INTEGER PRIMARY KEY,
                    auto_clean_enabled INTEGER DEFAULT 0,
                    auto_clean_frequency TEXT DEFAULT 'weekly',
                    auto_clean_scope TEXT DEFAULT 'smart',
                    auto_clean_mode TEXT DEFAULT 'dry_run',
                    dead_channel_days INTEGER DEFAULT 60,
                    notifications_enabled INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Schedules
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    cron_expr TEXT,
                    frequency TEXT,
                    scope TEXT,
                    mode TEXT DEFAULT 'dry_run',
                    is_active INTEGER DEFAULT 1,
                    next_run_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Audit Log with cryptographic hash-chain
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    job_id INTEGER,
                    action TEXT NOT NULL,
                    chat_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    prev_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Rejoin Manifest
                CREATE TABLE IF NOT EXISTS rejoin_manifest (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    job_id INTEGER,
                    chat_id INTEGER NOT NULL,
                    title TEXT,
                    username TEXT,
                    invite_link TEXT,
                    chat_type TEXT,
                    left_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Account Hygiene Score History
                CREATE TABLE IF NOT EXISTS hygiene_score_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    total_dialogs INTEGER DEFAULT 0,
                    whitelisted_count INTEGER DEFAULT 0,
                    cleaned_count INTEGER DEFAULT 0,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                );

                -- Indexes for high performance
                CREATE INDEX IF NOT EXISTS idx_whitelist_user_chat ON whitelist (telegram_id, chat_id);
                CREATE INDEX IF NOT EXISTS idx_cleanup_items_job ON cleanup_items (job_id);
                CREATE INDEX IF NOT EXISTS idx_rejoin_manifest_user ON rejoin_manifest (telegram_id);
                CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log (telegram_id);
                CREATE INDEX IF NOT EXISTS idx_hygiene_user ON hygiene_score_history (telegram_id);
                """
            )
            await conn.commit()
        logger.info("Database schema successfully initialized.")

    # ---------------- USER MANAGEMENT ---------------- #

    async def get_or_create_user(self, telegram_id: int, salt: str, language: str = "ru") -> Dict[str, Any]:
        """Fetches existing user or creates a new user profile with salt."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)

            await conn.execute(
                "INSERT INTO users (telegram_id, salt, language) VALUES (?, ?, ?)",
                (telegram_id, salt, language)
            )
            await conn.execute(
                "INSERT OR IGNORE INTO settings (telegram_id) VALUES (?)",
                (telegram_id,)
            )
            await conn.commit()

            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            new_row = await cursor.fetchone()
            return dict(new_row) if new_row else {}

    async def update_user_phone(self, telegram_id: int, phone: str) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE users SET phone = ? WHERE telegram_id = ?",
                (phone, telegram_id)
            )
            await conn.commit()

    async def update_user_language(self, telegram_id: int, language: str) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE users SET language = ? WHERE telegram_id = ?",
                (language, telegram_id)
            )
            await conn.commit()

    # ---------------- AUDIT LOG HASH-CHAIN ---------------- #

    async def append_audit_log(
        self, telegram_id: int, action: str, job_id: Optional[int] = None, chat_id: Optional[int] = None
    ) -> str:
        """Appends a tamper-evident entry to the audit log linked by SHA256 hash-chain."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT current_hash FROM audit_log WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
                (telegram_id,)
            )
            last = await cursor.fetchone()
            prev_hash = last["current_hash"] if last else "GENESIS_ROOT_0000000000000000000000000000000000000000000000000000000000000000"
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            raw_payload = f"{prev_hash}|{telegram_id}|{job_id}|{action}|{chat_id}|{timestamp}"
            current_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

            await conn.execute(
                """
                INSERT INTO audit_log (telegram_id, job_id, action, chat_id, timestamp, prev_hash, current_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (telegram_id, job_id, action, chat_id, timestamp, prev_hash, current_hash)
            )
            await conn.commit()
            return current_hash


db = Database()
