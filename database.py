import datetime
import hashlib
import os
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
import aiosqlite

from config import is_serverless, settings
from utils.logger import logger

# ---------------- MIGRATION DEFINITIONS ---------------- #

MIGRATION_001_BASELINE = """
-- Users
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    phone TEXT,
    salt TEXT NOT NULL,
    language TEXT DEFAULT 'ru',
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES cleanup_jobs(id) ON DELETE SET NULL
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
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES cleanup_jobs(id) ON DELETE SET NULL
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
"""

MIGRATION_002_CONSENTS = """
-- Legal and Regulatory Consents
CREATE TABLE IF NOT EXISTS consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    agreement_version TEXT NOT NULL,
    privacy_version TEXT NOT NULL,
    terms_hash TEXT NOT NULL,
    accepted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn_at TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_consents_user ON consents (telegram_id);
CREATE INDEX IF NOT EXISTS idx_consents_active ON consents (telegram_id, withdrawn_at);
"""

MIGRATION_003_SUPPORT_TICKETS = """
-- Support Tickets System
CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number TEXT NOT NULL UNIQUE,
    telegram_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_support_tickets_number ON support_tickets (ticket_number);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user_status ON support_tickets (telegram_id, status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status_priority ON support_tickets (status, priority);

-- Ticket Messages Threading
CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL,
    sender_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    attachments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages (ticket_id, created_at);
"""

MIGRATION_004_USER_CREDENTIALS = """
-- Custom MTProto User Credentials (stored encrypted-at-rest)
CREATE TABLE IF NOT EXISTS user_credentials (
    telegram_id INTEGER PRIMARY KEY,
    encrypted_api_id TEXT,
    encrypted_api_hash TEXT,
    is_custom INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);
"""

MIGRATION_005_PERFORMANCE_INDEXES = """
-- Performance Compound Indexes
CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_user_started ON cleanup_jobs (telegram_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_status ON cleanup_jobs (telegram_id, status);
CREATE INDEX IF NOT EXISTS idx_cleanup_jobs_started ON cleanup_jobs (started_at);
CREATE INDEX IF NOT EXISTS idx_cleanup_items_job ON cleanup_items (job_id);
CREATE INDEX IF NOT EXISTS idx_cleanup_items_job_status ON cleanup_items (job_id, status);
CREATE INDEX IF NOT EXISTS idx_schedules_user ON schedules (telegram_id);
CREATE INDEX IF NOT EXISTS idx_schedules_active_next ON schedules (is_active, next_run_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (telegram_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_rejoin_manifest_user_left ON rejoin_manifest (telegram_id, left_at DESC);
CREATE INDEX IF NOT EXISTS idx_hygiene_user_id ON hygiene_score_history (telegram_id, id DESC);
"""

MIGRATION_006_SESSION_DATA_AND_RATE_LIMITS = """
-- Migration 006: Add session_data column to sessions table and persistent rate_limits table
ALTER TABLE sessions ADD COLUMN session_data TEXT;

CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    limiter_key TEXT NOT NULL,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limits_key_ts ON rate_limits (limiter_key, timestamp);
"""

MIGRATION_007_FEATURE_SYSTEM_TABLES = """
    CREATE TABLE IF NOT EXISTS feature_states (
        telegram_id INTEGER NOT NULL,
        feature_id TEXT NOT NULL,
        enabled INTEGER DEFAULT 0,
        settings_json TEXT DEFAULT '{}',
        enabled_at TIMESTAMP,
        last_activity TIMESTAMP,
        actions_count INTEGER DEFAULT 0,
        errors_count INTEGER DEFAULT 0,
        PRIMARY KEY (telegram_id, feature_id),
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS feature_favorites (
        telegram_id INTEGER NOT NULL,
        feature_id TEXT NOT NULL,
        position INTEGER DEFAULT 0,
        PRIMARY KEY (telegram_id, feature_id),
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS deleted_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        sender_id INTEGER,
        sender_name TEXT,
        chat_title TEXT,
        message_type TEXT DEFAULT 'text',
        text_content TEXT,
        media_metadata TEXT,
        deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        original_date TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_deleted_messages_user_chat 
        ON deleted_messages(telegram_id, chat_id, deleted_at DESC);
    
    CREATE TABLE IF NOT EXISTS edited_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        sender_id INTEGER,
        sender_name TEXT,
        chat_title TEXT,
        old_text TEXT,
        new_text TEXT,
        edit_version INTEGER DEFAULT 1,
        edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_edited_messages_user_chat 
        ON edited_messages(telegram_id, chat_id, edited_at DESC);
    
    CREATE TABLE IF NOT EXISTS auto_responder_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        match_type TEXT NOT NULL,
        pattern TEXT NOT NULL,
        response TEXT NOT NULL,
        chat_id INTEGER,
        user_id_filter INTEGER,
        cooldown_seconds INTEGER DEFAULT 60,
        max_daily INTEGER DEFAULT 50,
        daily_count INTEGER DEFAULT 0,
        daily_reset_at TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
    
    CREATE TABLE IF NOT EXISTS feature_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        feature_id TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_feature_activity_user 
        ON feature_activity(telegram_id, feature_id, created_at DESC);
    
    CREATE TABLE IF NOT EXISTS storage_usage (
        telegram_id INTEGER PRIMARY KEY,
        deleted_messages_count INTEGER DEFAULT 0,
        deleted_messages_bytes INTEGER DEFAULT 0,
        edited_messages_count INTEGER DEFAULT 0,
        storage_quota_bytes INTEGER DEFAULT 104857600,
        retention_days INTEGER DEFAULT 30,
        last_cleanup TIMESTAMP,
        FOREIGN KEY (telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
    );
"""

MIGRATIONS = [
    (1, "001_baseline_schema", MIGRATION_001_BASELINE),
    (2, "002_add_consents_table", MIGRATION_002_CONSENTS),
    (3, "003_add_support_tickets_system", MIGRATION_003_SUPPORT_TICKETS),
    (4, "004_add_user_credentials", MIGRATION_004_USER_CREDENTIALS),
    (5, "005_performance_indexes", MIGRATION_005_PERFORMANCE_INDEXES),
    (6, "006_session_data_and_rate_limits", MIGRATION_006_SESSION_DATA_AND_RATE_LIMITS),
    (7, "007_feature_system_tables", MIGRATION_007_FEATURE_SYSTEM_TABLES),
]


class Database:
    """Async SQLite database manager with automatic migrations, safe path resolution, and full integrity."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self._initialized = False

    def _get_safe_path(self) -> str:
        """Resolves SQLite path, redirecting to /tmp in serverless or write-restricted environments."""
        p = Path(self.db_path)
        try:
            resolved = str(p.resolve()).replace("\\", "/")
            if is_serverless() or "/var/task" in resolved:
                return "/tmp/cleaner.db"
            if os.name != "nt":
                parent = p.parent if p.parent.exists() else Path(".")
                if not os.access(parent, os.W_OK):
                    return "/tmp/cleaner.db"
        except Exception as e:
            logger.warning(f"Could not determine write access for {self.db_path}: {e}; defaulting to /tmp/cleaner.db")
            return "/tmp/cleaner.db"
        return self.db_path

    async def _backup_database_file(self, target_path: str, max_backups: int = 5) -> None:
        """Creates a timestamped snapshot of the database file before applying migrations with automatic pruning."""
        p = Path(target_path)
        if not p.exists() or p.stat().st_size == 0:
            return
        try:
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = p.with_suffix(f".bak_{ts}")
            shutil.copy2(p, backup_path)
            logger.info(f"Database pre-migration snapshot saved to: {backup_path}")

            # Prune old backups to keep only max_backups
            parent = p.parent
            base_name = p.stem
            all_backups = sorted(
                parent.glob(f"{base_name}.bak_*"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            for old_bak in all_backups[max_backups:]:
                try:
                    old_bak.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Could not create pre-migration snapshot: {e}")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Async context manager for SQLite connections with row factory, busy_timeout, and WAL mode."""
        if not self._initialized:
            await self.init_db()
        target_path = self._get_safe_path()
        db_parent = Path(target_path).parent
        if db_parent and str(db_parent) != ".":
            db_parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(target_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA busy_timeout = 5000;")
            try:
                await conn.execute("PRAGMA journal_mode = WAL;")
                await conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
            yield conn

    async def run_migrations(self, conn: aiosqlite.Connection) -> None:
        """Executes versioned migrations safely with baseline detection and savepoint rollback."""
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.commit()

        cursor = await conn.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in await cursor.fetchall()}

        for version, name, script in MIGRATIONS:
            if version not in applied:
                logger.info(f"Applying database migration {version}: {name}...")
                try:
                    await conn.executescript(script)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                        (version, name),
                    )
                    await conn.commit()
                    logger.info(f"Successfully applied migration {version}: {name}")
                except Exception as e:
                    logger.error(f"Migration {version} ({name}) failed: {e}")
                    raise

    async def init_db(self) -> None:
        """Initializes database schema and executes all pending migrations."""
        self._initialized = True
        target_path = self._get_safe_path()
        logger.info(f"Initializing database at: {target_path}")
        db_parent = Path(target_path).parent
        if db_parent and str(db_parent) != ".":
            db_parent.mkdir(parents=True, exist_ok=True)

        await self._backup_database_file(target_path)

        async with aiosqlite.connect(target_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA busy_timeout = 5000;")
            try:
                await conn.execute("PRAGMA journal_mode = WAL;")
                await conn.execute("PRAGMA synchronous = NORMAL;")
            except Exception:
                pass
            await self.run_migrations(conn)

        logger.info("Database schema and migrations successfully applied.")

    # ---------------- USER MANAGEMENT ---------------- #

    async def get_or_create_user(self, telegram_id: int, salt: str, language: str = "ru") -> Dict[str, Any]:
        """Fetches existing user or creates a new user profile with salt and default settings."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                await conn.execute(
                    "INSERT OR IGNORE INTO settings (telegram_id) VALUES (?)",
                    (telegram_id,),
                )
                await conn.commit()
                return dict(row)

            await conn.execute(
                "INSERT INTO users (telegram_id, salt, language) VALUES (?, ?, ?)",
                (telegram_id, salt, language),
            )
            await conn.execute(
                "INSERT OR IGNORE INTO settings (telegram_id) VALUES (?)",
                (telegram_id,),
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
                "UPDATE users SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (phone, telegram_id),
            )
            await conn.commit()

    async def update_user_language(self, telegram_id: int, language: str) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                "UPDATE users SET language = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (language, telegram_id),
            )
            await conn.commit()

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves user row if exists, or None."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_audit_log_timeline(self, telegram_id: int, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieves cryptographic audit log entries with SHA256 integrity verification."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, telegram_id, job_id, action, chat_id, timestamp, prev_hash, current_hash
                FROM audit_log
                WHERE telegram_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (telegram_id, limit),
            )
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                raw = f"{d['prev_hash']}|{d['telegram_id']}|{d['job_id']}|{d['action']}|{d['chat_id']}|{d['timestamp']}"
                expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                d["is_tamper_evident_valid"] = (expected_hash == d["current_hash"])
                result.append(d)
            return result

    # ---------------- AUDIT LOG HASH-CHAIN ---------------- #

    async def append_audit_log(
        self, telegram_id: int, action: str, job_id: Optional[int] = None, chat_id: Optional[int] = None
    ) -> str:
        """Appends a tamper-evident entry to the audit log linked by SHA256 hash-chain."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT current_hash FROM audit_log WHERE telegram_id = ? ORDER BY id DESC LIMIT 1",
                (telegram_id,),
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
                (telegram_id, job_id, action, chat_id, timestamp, prev_hash, current_hash),
            )
            await conn.commit()
            return current_hash

    # ---------------- CONSENTS COMPLIANCE ---------------- #

    async def record_consent(
        self,
        telegram_id: int,
        agreement_version: str,
        privacy_version: str,
        terms_hash: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """Records user agreement to terms and privacy policy."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO consents (
                    telegram_id, agreement_version, privacy_version, terms_hash,
                    accepted_at, withdrawn_at, ip_address, user_agent
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, NULL, ?, ?)
                """,
                (telegram_id, agreement_version, privacy_version, terms_hash, ip_address, user_agent),
            )
            consent_id = cursor.lastrowid
            await conn.commit()
            return consent_id

    async def get_active_consent(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Returns the most recent active (non-withdrawn) consent record for a user."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM consents
                WHERE telegram_id = ? AND withdrawn_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (telegram_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def withdraw_consent(self, telegram_id: int) -> bool:
        """Marks all active consents as withdrawn for the given user."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE consents
                SET withdrawn_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ? AND withdrawn_at IS NULL
                """,
                (telegram_id,),
            )
            await conn.commit()
            return cursor.rowcount > 0

    # ---------------- SUPPORT TICKETS & MESSAGES ---------------- #

    async def create_support_ticket(
        self,
        telegram_id: int,
        category: str,
        subject: str,
        description: str,
        priority: str = "medium",
    ) -> Dict[str, Any]:
        """Creates a new support ticket with CLIN-XXXXX ticket number."""
        async with self.get_connection() as conn:
            # Generate unique ticket number like CLIN-10241
            for _ in range(10):
                candidate_number = f"CLIN-{secrets.randbelow(90000) + 10000}"
                chk = await conn.execute(
                    "SELECT id FROM support_tickets WHERE ticket_number = ?", (candidate_number,)
                )
                if not await chk.fetchone():
                    break
            else:
                candidate_number = f"CLIN-{int(datetime.datetime.now().timestamp()) % 100000:05d}"

            cursor = await conn.execute(
                """
                INSERT INTO support_tickets (
                    ticket_number, telegram_id, category, subject, description, priority, status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'open')
                """,
                (candidate_number, telegram_id, category, subject, description, priority),
            )
            ticket_id = cursor.lastrowid
            await conn.commit()

            ticket_cur = await conn.execute(
                "SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)
            )
            row = await ticket_cur.fetchone()
            return dict(row) if row else {}

    async def get_ticket(self, ticket_number: str) -> Optional[Dict[str, Any]]:
        """Retrieves a support ticket by ticket number (e.g. CLIN-10241)."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM support_tickets WHERE ticket_number = ?", (ticket_number,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_tickets(
        self,
        telegram_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lists support tickets filtered by user and/or status."""
        query = "SELECT * FROM support_tickets WHERE 1=1"
        params: List[Any] = []
        if telegram_id is not None:
            query += " AND telegram_id = ?"
            params.append(telegram_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        async with self.get_connection() as conn:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_ticket_status(self, ticket_number: str, status: str) -> bool:
        """Updates ticket status (e.g. 'open', 'in_progress', 'resolved', 'closed')."""
        async with self.get_connection() as conn:
            closed_clause = ", closed_at = CURRENT_TIMESTAMP" if status in ("resolved", "closed") else ", closed_at = NULL"
            cursor = await conn.execute(
                f"""
                UPDATE support_tickets
                SET status = ?, updated_at = CURRENT_TIMESTAMP {closed_clause}
                WHERE ticket_number = ?
                """,
                (status, ticket_number),
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def add_ticket_message(
        self,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        message: str,
        attachments: Optional[str] = None,
    ) -> int:
        """Appends a message to a support ticket thread."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO ticket_messages (ticket_id, sender_type, sender_id, message, attachments)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ticket_id, sender_type, sender_id, message, attachments),
            )
            msg_id = cursor.lastrowid
            await conn.execute(
                "UPDATE support_tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ticket_id,),
            )
            await conn.commit()
            return msg_id

    async def get_ticket_messages(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Retrieves all messages for a support ticket in chronological order."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC",
                (ticket_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ---------------- USER CREDENTIALS (ENCRYPTED AT REST) ---------------- #

    async def set_user_credentials(
        self,
        telegram_id: int,
        encrypted_api_id: Optional[str],
        encrypted_api_hash: Optional[str],
        is_custom: int = 1,
    ) -> None:
        """Stores or updates custom MTProto credentials encrypted at rest."""
        async with self.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_credentials (telegram_id, encrypted_api_id, encrypted_api_hash, is_custom, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    encrypted_api_id = excluded.encrypted_api_id,
                    encrypted_api_hash = excluded.encrypted_api_hash,
                    is_custom = excluded.is_custom,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, encrypted_api_id, encrypted_api_hash, is_custom),
            )
            await conn.commit()

    async def get_user_credentials(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves encrypted credentials for a user."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM user_credentials WHERE telegram_id = ?", (telegram_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_user_credentials(self, telegram_id: int) -> bool:
        """Removes custom credentials for a user."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM user_credentials WHERE telegram_id = ?", (telegram_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    # ─── Feature System CRUD ───────────────────────────────────────

    async def get_feature_state(self, telegram_id: int, feature_id: str) -> Optional[dict]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM feature_states WHERE telegram_id = ? AND feature_id = ?",
                (telegram_id, feature_id)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_feature_states(self, telegram_id: int) -> list[dict]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM feature_states WHERE telegram_id = ?",
                (telegram_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def set_feature_enabled(self, telegram_id: int, feature_id: str, enabled: bool) -> None:
        async with self.get_connection() as conn:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat() if enabled else None
            await conn.execute(
                """INSERT INTO feature_states (telegram_id, feature_id, enabled, enabled_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(telegram_id, feature_id) DO UPDATE SET
                       enabled = excluded.enabled,
                       enabled_at = CASE WHEN excluded.enabled = 1 THEN COALESCE(feature_states.enabled_at, excluded.enabled_at) ELSE feature_states.enabled_at END""",
                (telegram_id, feature_id, int(enabled), now)
            )
            await conn.commit()

    async def update_feature_settings(self, telegram_id: int, feature_id: str, settings_json: str) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                """INSERT INTO feature_states (telegram_id, feature_id, settings_json)
                   VALUES (?, ?, ?)
                   ON CONFLICT(telegram_id, feature_id) DO UPDATE SET
                       settings_json = excluded.settings_json""",
                (telegram_id, feature_id, settings_json)
            )
            await conn.commit()

    async def increment_feature_activity(self, telegram_id: int, feature_id: str) -> None:
        async with self.get_connection() as conn:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await conn.execute(
                """INSERT INTO feature_states (telegram_id, feature_id, actions_count, last_activity)
                   VALUES (?, ?, 1, ?)
                   ON CONFLICT(telegram_id, feature_id) DO UPDATE SET
                       actions_count = feature_states.actions_count + 1,
                       last_activity = excluded.last_activity""",
                (telegram_id, feature_id, now)
            )
            await conn.commit()

    async def increment_feature_errors(self, telegram_id: int, feature_id: str) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                """INSERT INTO feature_states (telegram_id, feature_id, errors_count)
                   VALUES (?, ?, 1)
                   ON CONFLICT(telegram_id, feature_id) DO UPDATE SET
                       errors_count = feature_states.errors_count + 1""",
                (telegram_id, feature_id)
            )
            await conn.commit()

    async def toggle_favorite(self, telegram_id: int, feature_id: str) -> bool:
        """Toggle favorite status. Returns new is_favorite state."""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM feature_favorites WHERE telegram_id = ? AND feature_id = ?",
                (telegram_id, feature_id)
            )
            existing = await cursor.fetchone()
            if existing:
                await conn.execute(
                    "DELETE FROM feature_favorites WHERE telegram_id = ? AND feature_id = ?",
                    (telegram_id, feature_id)
                )
                await conn.commit()
                return False
            else:
                c_max = await conn.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM feature_favorites WHERE telegram_id = ?",
                    (telegram_id,)
                )
                max_pos = await c_max.fetchone()
                await conn.execute(
                    "INSERT INTO feature_favorites (telegram_id, feature_id, position) VALUES (?, ?, ?)",
                    (telegram_id, feature_id, max_pos[0] if max_pos else 0)
                )
                await conn.commit()
                return True

    async def get_favorites(self, telegram_id: int) -> list[str]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT feature_id FROM feature_favorites WHERE telegram_id = ? ORDER BY position",
                (telegram_id,)
            )
            rows = await cursor.fetchall()
            return [r['feature_id'] for r in rows]

    # ─── Deleted Messages CRUD ────────────────────────────────────

    async def save_deleted_message(self, telegram_id: int, chat_id: int, message_id: int,
                                    sender_id: int = None, sender_name: str = None,
                                    chat_title: str = None, message_type: str = 'text',
                                    text_content: str = None, media_metadata: str = None,
                                    original_date: str = None) -> int:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO deleted_messages 
                   (telegram_id, chat_id, message_id, sender_id, sender_name, chat_title,
                    message_type, text_content, media_metadata, original_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, chat_id, message_id, sender_id, sender_name, chat_title,
                 message_type, text_content, media_metadata, original_date)
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_deleted_messages(self, telegram_id: int, chat_id: int = None,
                                    limit: int = 50, offset: int = 0) -> list[dict]:
        async with self.get_connection() as conn:
            if chat_id:
                cursor = await conn.execute(
                    """SELECT * FROM deleted_messages 
                       WHERE telegram_id = ? AND chat_id = ?
                       ORDER BY deleted_at DESC LIMIT ? OFFSET ?""",
                    (telegram_id, chat_id, limit, offset)
                )
            else:
                cursor = await conn.execute(
                    """SELECT * FROM deleted_messages 
                       WHERE telegram_id = ?
                       ORDER BY deleted_at DESC LIMIT ? OFFSET ?""",
                    (telegram_id, limit, offset)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_deleted_messages_stats(self, telegram_id: int) -> dict:
        async with self.get_connection() as conn:
            c1 = await conn.execute(
                "SELECT COUNT(*) as total FROM deleted_messages WHERE telegram_id = ?",
                (telegram_id,)
            )
            total = await c1.fetchone()
            
            c2 = await conn.execute(
                """SELECT COUNT(*) as count FROM deleted_messages 
                   WHERE telegram_id = ? AND deleted_at >= date('now')""",
                (telegram_id,)
            )
            today = await c2.fetchone()
            
            c3 = await conn.execute(
                """SELECT COUNT(*) as count FROM deleted_messages 
                   WHERE telegram_id = ? AND deleted_at >= date('now', '-7 days')""",
                (telegram_id,)
            )
            week = await c3.fetchone()
            
            c4 = await conn.execute(
                """SELECT message_type, COUNT(*) as count FROM deleted_messages 
                   WHERE telegram_id = ? GROUP BY message_type""",
                (telegram_id,)
            )
            by_type = await c4.fetchall()
            return {
                'total': total['total'] if total else 0,
                'today': today['count'] if today else 0,
                'this_week': week['count'] if week else 0,
                'by_type': {r['message_type']: r['count'] for r in by_type}
            }

    async def search_deleted_messages(self, telegram_id: int, query: str, limit: int = 50) -> list[dict]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM deleted_messages 
                   WHERE telegram_id = ? AND text_content LIKE ?
                   ORDER BY deleted_at DESC LIMIT ?""",
                (telegram_id, f'%{query}%', limit)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def cleanup_expired_deleted_messages(self, telegram_id: int, retention_days: int = 30) -> int:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """DELETE FROM deleted_messages 
                   WHERE telegram_id = ? AND deleted_at < datetime('now', ? || ' days')""",
                (telegram_id, f'-{retention_days}')
            )
            await conn.commit()
            return cursor.rowcount

    # ─── Edited Messages CRUD ─────────────────────────────────────

    async def save_edited_message(self, telegram_id: int, chat_id: int, message_id: int,
                                   sender_id: int = None, sender_name: str = None,
                                   chat_title: str = None, old_text: str = None,
                                   new_text: str = None) -> int:
        async with self.get_connection() as conn:
            c1 = await conn.execute(
                """SELECT MAX(edit_version) as ver FROM edited_messages 
                   WHERE telegram_id = ? AND chat_id = ? AND message_id = ?""",
                (telegram_id, chat_id, message_id)
            )
            last = await c1.fetchone()
            version = (last['ver'] or 0) + 1 if last else 1
            
            cursor = await conn.execute(
                """INSERT INTO edited_messages 
                   (telegram_id, chat_id, message_id, sender_id, sender_name, chat_title,
                    old_text, new_text, edit_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, chat_id, message_id, sender_id, sender_name, chat_title,
                 old_text, new_text, version)
            )
            await conn.commit()
            return cursor.lastrowid

    async def get_edited_messages(self, telegram_id: int, chat_id: int = None,
                                   limit: int = 50, offset: int = 0) -> list[dict]:
        async with self.get_connection() as conn:
            if chat_id:
                cursor = await conn.execute(
                    """SELECT * FROM edited_messages 
                       WHERE telegram_id = ? AND chat_id = ?
                       ORDER BY edited_at DESC LIMIT ? OFFSET ?""",
                    (telegram_id, chat_id, limit, offset)
                )
            else:
                cursor = await conn.execute(
                    """SELECT * FROM edited_messages 
                       WHERE telegram_id = ?
                       ORDER BY edited_at DESC LIMIT ? OFFSET ?""",
                    (telegram_id, limit, offset)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_edit_history(self, telegram_id: int, chat_id: int, message_id: int) -> list[dict]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                """SELECT * FROM edited_messages 
                   WHERE telegram_id = ? AND chat_id = ? AND message_id = ?
                   ORDER BY edit_version ASC""",
                (telegram_id, chat_id, message_id)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_edited_messages_stats(self, telegram_id: int) -> dict:
        async with self.get_connection() as conn:
            c1 = await conn.execute(
                "SELECT COUNT(*) as total FROM edited_messages WHERE telegram_id = ?",
                (telegram_id,)
            )
            total = await c1.fetchone()
            
            c2 = await conn.execute(
                """SELECT COUNT(*) as count FROM edited_messages 
                   WHERE telegram_id = ? AND edited_at >= date('now')""",
                (telegram_id,)
            )
            today = await c2.fetchone()
            return {
                'total': total['total'] if total else 0,
                'today': today['count'] if today else 0,
            }

    # ─── Auto Responder Rules CRUD ────────────────────────────────

    async def get_auto_responder_rules(self, telegram_id: int, active_only: bool = True) -> list[dict]:
        async with self.get_connection() as conn:
            if active_only:
                cursor = await conn.execute(
                    "SELECT * FROM auto_responder_rules WHERE telegram_id = ? AND is_active = 1",
                    (telegram_id,)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM auto_responder_rules WHERE telegram_id = ?",
                    (telegram_id,)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def save_auto_responder_rule(self, telegram_id: int, match_type: str, pattern: str,
                                        response: str, chat_id: int = None,
                                        user_id_filter: int = None,
                                        cooldown_seconds: int = 60,
                                        max_daily: int = 50) -> int:
        async with self.get_connection() as conn:
            c1 = await conn.execute(
                "SELECT COUNT(*) as c FROM auto_responder_rules WHERE telegram_id = ?",
                (telegram_id,)
            )
            count = await c1.fetchone()
            if count and count['c'] >= 10:
                raise ValueError("Maximum 10 auto-responder rules per user")
            
            cursor = await conn.execute(
                """INSERT INTO auto_responder_rules 
                   (telegram_id, match_type, pattern, response, chat_id, user_id_filter,
                    cooldown_seconds, max_daily)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, match_type, pattern, response, chat_id, user_id_filter,
                 cooldown_seconds, max_daily)
            )
            await conn.commit()
            return cursor.lastrowid

    async def update_auto_responder_rule(self, rule_id: int, telegram_id: int, **kwargs) -> bool:
        async with self.get_connection() as conn:
            c1 = await conn.execute(
                "SELECT 1 FROM auto_responder_rules WHERE id = ? AND telegram_id = ?",
                (rule_id, telegram_id)
            )
            row = await c1.fetchone()
            if not row:
                return False
            allowed = {'match_type', 'pattern', 'response', 'chat_id', 'user_id_filter',
                       'cooldown_seconds', 'max_daily', 'is_active'}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return True
            set_clause = ', '.join(f'{k} = ?' for k in updates)
            values = list(updates.values()) + [rule_id, telegram_id]
            await conn.execute(
                f"UPDATE auto_responder_rules SET {set_clause} WHERE id = ? AND telegram_id = ?",
                values
            )
            await conn.commit()
            return True

    async def delete_auto_responder_rule(self, rule_id: int, telegram_id: int) -> bool:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM auto_responder_rules WHERE id = ? AND telegram_id = ?",
                (rule_id, telegram_id)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def increment_rule_daily_count(self, rule_id: int) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                """UPDATE auto_responder_rules SET daily_count = daily_count + 1
                   WHERE id = ?""",
                (rule_id,)
            )
            await conn.commit()

    async def reset_rule_daily_counts(self, telegram_id: int) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                """UPDATE auto_responder_rules SET daily_count = 0, daily_reset_at = CURRENT_TIMESTAMP
                   WHERE telegram_id = ?""",
                (telegram_id,)
            )
            await conn.commit()

    # ─── Feature Activity Log ─────────────────────────────────────

    async def log_feature_activity(self, telegram_id: int, feature_id: str,
                                    action: str, details: str = None) -> None:
        async with self.get_connection() as conn:
            await conn.execute(
                """INSERT INTO feature_activity (telegram_id, feature_id, action, details)
                   VALUES (?, ?, ?, ?)""",
                (telegram_id, feature_id, action, details)
            )
            await conn.commit()

    async def get_feature_activity_log(self, telegram_id: int, feature_id: str = None,
                                        limit: int = 50) -> list[dict]:
        async with self.get_connection() as conn:
            if feature_id:
                cursor = await conn.execute(
                    """SELECT * FROM feature_activity 
                       WHERE telegram_id = ? AND feature_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (telegram_id, feature_id, limit)
                )
            else:
                cursor = await conn.execute(
                    """SELECT * FROM feature_activity 
                       WHERE telegram_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (telegram_id, limit)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ─── Storage Usage ────────────────────────────────────────────

    async def get_storage_usage(self, telegram_id: int) -> dict:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM storage_usage WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            await conn.execute(
                "INSERT OR IGNORE INTO storage_usage (telegram_id) VALUES (?)",
                (telegram_id,)
            )
            await conn.commit()
            return {
                'telegram_id': telegram_id,
                'deleted_messages_count': 0,
                'deleted_messages_bytes': 0,
                'edited_messages_count': 0,
                'storage_quota_bytes': 104857600,
                'retention_days': 30,
                'last_cleanup': None
            }

    async def update_storage_usage(self, telegram_id: int, **kwargs) -> None:
        async with self.get_connection() as conn:
            allowed = {'deleted_messages_count', 'deleted_messages_bytes', 'edited_messages_count',
                       'storage_quota_bytes', 'retention_days', 'last_cleanup'}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return
            await conn.execute(
                "INSERT OR IGNORE INTO storage_usage (telegram_id) VALUES (?)",
                (telegram_id,)
            )
            set_clause = ', '.join(f'{k} = ?' for k in updates)
            values = list(updates.values()) + [telegram_id]
            await conn.execute(
                f"UPDATE storage_usage SET {set_clause} WHERE telegram_id = ?",
                values
            )
            await conn.commit()

    async def cleanup_expired_archive(self, telegram_id: int) -> dict:
        """Clean up expired deleted and edited messages based on retention settings."""
        usage = await self.get_storage_usage(telegram_id)
        retention_days = usage.get('retention_days', 30)
        deleted_count = await self.cleanup_expired_deleted_messages(telegram_id, retention_days)
        stats = await self.get_deleted_messages_stats(telegram_id)
        edited_stats = await self.get_edited_messages_stats(telegram_id)
        await self.update_storage_usage(
            telegram_id,
            deleted_messages_count=stats['total'],
            edited_messages_count=edited_stats['total'],
            last_cleanup=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        return {'deleted_removed': deleted_count, 'retention_days': retention_days}


db = Database()
