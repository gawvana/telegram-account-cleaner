import datetime
from pathlib import Path
import shutil
import sys
import time
from fastapi import APIRouter, Depends
import aiosqlite

from config import is_serverless, settings
from database import db, MIGRATIONS
from services.scheduler_service import scheduler_service
from utils.logger import logger
from webapp.api.auth import get_current_user_id
from webapp.schemas import (
    BackendDiagnostics,
    DatabaseDiagnostics,
    DiagnosticsResponse,
    SchedulerDiagnostics,
    SessionStoreDiagnostics,
    StorageDiagnostics,
)

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])

_START_TIME = time.time()


@router.get("", response_model=DiagnosticsResponse)
@router.get("/", response_model=DiagnosticsResponse)
async def get_system_diagnostics(user_id: int = Depends(get_current_user_id)):
    """Non-destructive diagnostic verification of backend, database, sessions, scheduler, and storage (Requires authentication)."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    overall_status = "healthy"

    # Check if user is admin for detail levels
    user = await db.get_user(user_id)
    is_admin = bool(user and user.get("is_admin"))

    # 1. Backend Diagnostics
    uptime = round(time.time() - _START_TIME, 2)
    backend_info = BackendDiagnostics(
        status="ok",
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
        uptime_seconds=uptime,
        server_time=now_iso,
        python_version=sys.version.split()[0],
        serverless_mode=is_serverless(),
    )

    # 2. Database Diagnostics (Non-destructive)
    t0 = time.perf_counter()
    db_path = db._get_safe_path()
    db_status = "healthy"
    journal_mode = "unknown"
    integrity = "ok"
    applied_version = 0
    table_counts = {}

    try:
        async with db.get_connection() as conn:
            await conn.execute("SELECT 1")
            cur = await conn.execute("PRAGMA journal_mode;")
            row = await cur.fetchone()
            if row:
                journal_mode = str(row[0]).lower()

            cur = await conn.execute("PRAGMA quick_check(1);")
            row = await cur.fetchone()
            integrity = str(row[0]) if row else "unknown"
            if integrity.lower() != "ok":
                db_status = "degraded"
                overall_status = "degraded"

            cur = await conn.execute("SELECT MAX(version) FROM schema_migrations")
            row = await cur.fetchone()
            applied_version = row[0] if (row and row[0] is not None) else 0

            for tbl in ["users", "sessions", "whitelist", "cleanup_jobs", "audit_log", "settings"]:
                try:
                    c = await conn.execute(f"SELECT COUNT(*) FROM {tbl}")
                    r = await c.fetchone()
                    table_counts[tbl] = r[0] if r else 0
                except Exception:
                    table_counts[tbl] = -1
    except Exception as e:
        logger.error(f"Diagnostics DB ping error: {e}")
        db_status = "error"
        integrity = str(e)
        overall_status = "critical"

    db_latency = round((time.perf_counter() - t0) * 1000, 2)
    latest_migration = MIGRATIONS[-1][0] if MIGRATIONS else 0

    display_db_path = db_path if is_admin else Path(db_path).name
    database_info = DatabaseDiagnostics(
        status=db_status,
        path=display_db_path,
        journal_mode=journal_mode,
        integrity_check=integrity,
        current_migration_version=applied_version,
        latest_migration_version=latest_migration,
        table_counts=table_counts,
        latency_ms=db_latency,
    )

    # 3. Session Store Diagnostics
    sess_path = Path(settings.SESSION_DIR)
    dir_exists = sess_path.exists()
    is_writable = False
    active_count = 0

    if dir_exists:
        try:
            probe = sess_path / ".probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            is_writable = True
        except Exception:
            is_writable = False

        for p in sess_path.glob("**/*"):
            if p.is_file() and not p.name.startswith("."):
                active_count += 1
    else:
        try:
            sess_path.mkdir(parents=True, exist_ok=True)
            dir_exists = True
            is_writable = True
        except Exception:
            is_writable = False

    session_status = "healthy"
    if not is_writable:
        session_status = "error"
        overall_status = "critical"
    elif not settings.ENCRYPTION_MASTER_KEY:
        session_status = "warning"

    display_sess_path = str(sess_path) if is_admin else Path(sess_path).name
    session_info = SessionStoreDiagnostics(
        status=session_status,
        directory=display_sess_path,
        directory_exists=dir_exists,
        is_writable=is_writable,
        active_sessions_count=active_count,
        master_key_configured=bool(settings.ENCRYPTION_MASTER_KEY),
    )

    # 4. Scheduler Diagnostics
    sched = scheduler_service.scheduler
    sched_status = "disabled"
    job_count = 0
    if settings.SCHEDULER_ENABLED:
        if sched and sched.running:
            sched_status = "running"
            job_count = len(sched.get_jobs())
        else:
            sched_status = "stopped"

    scheduler_info = SchedulerDiagnostics(
        status=sched_status,
        enabled=settings.SCHEDULER_ENABLED,
        timezone=settings.SCHEDULER_TIMEZONE,
        registered_jobs_count=job_count,
    )

    # 5. Storage Diagnostics
    db_file = Path(db_path)
    db_bytes = db_file.stat().st_size if db_file.exists() else 0
    parent_dir = db_file.parent if db_file.parent.exists() else Path(".")
    backup_count = len(list(parent_dir.glob("cleaner.bak_*")))

    try:
        disk = shutil.disk_usage(str(parent_dir.resolve()))
        disk_total = disk.total
        disk_free = disk.free
        disk_pct = round(((disk.total - disk.free) / disk.total) * 100, 2)
    except Exception:
        disk_total, disk_free, disk_pct = 0, 0, 0.0

    storage_status = "healthy"
    if disk_pct > 95:
        storage_status = "critical"
        overall_status = "critical"
    elif disk_pct > 85:
        storage_status = "warning"

    storage_info = StorageDiagnostics(
        status=storage_status,
        db_size_bytes=db_bytes,
        backup_snapshots_count=backup_count,
        disk_total_bytes=disk_total,
        disk_free_bytes=disk_free,
        disk_used_percent=disk_pct,
    )

    return DiagnosticsResponse(
        overall_status=overall_status,
        timestamp=now_iso,
        backend=backend_info,
        database=database_info,
        sessions=session_info,
        scheduler=scheduler_info,
        storage=storage_info,
    )
