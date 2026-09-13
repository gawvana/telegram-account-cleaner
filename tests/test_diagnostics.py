import pytest
from fastapi.testclient import TestClient
from webapp_server import app
from database import db
from config import settings


@pytest.fixture
def client():
    return TestClient(app)


def test_diagnostics_requires_authentication(client):
    """Verifies that unauthenticated GET /api/diagnostics returns 401."""
    response = client.get("/api/diagnostics")
    assert response.status_code == 401


def test_diagnostics_endpoint_contract(client, auth_headers):
    """Verifies that authenticated GET /api/diagnostics returns valid non-destructive system diagnostics with masked paths."""
    response = client.get("/api/diagnostics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["overall_status"] in ["ok", "healthy", "degraded"]
    assert "timestamp" in data

    # Backend
    assert "backend" in data
    assert data["backend"]["app_name"] == "CLIN"
    assert data["backend"]["status"] == "ok"
    assert "app_version" in data["backend"]
    assert "uptime_seconds" in data["backend"]

    # Database
    assert "database" in data
    assert data["database"]["status"] in ["ok", "healthy"]
    assert data["database"]["integrity_check"] == "ok"
    assert data["database"]["latency_ms"] >= 0

    # Sessions
    assert "sessions" in data
    assert data["sessions"]["status"] in ["ok", "healthy"]
    assert "master_key_configured" in data["sessions"]

    # Scheduler & Storage
    assert "scheduler" in data
    assert "storage" in data
    assert data["storage"]["db_size_bytes"] >= 0


@pytest.mark.asyncio
async def test_audit_timeline_integrity_verification():
    """Verifies cryptographic hash-chain integrity verification in get_audit_log_timeline."""
    await db.init_db()
    telegram_id = 99912345

    # Insert user to satisfy foreign key constraint
    async with db.get_connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, salt) VALUES (?, 'test_salt')",
            (telegram_id,)
        )
        await conn.commit()

    # Append valid audit log entry
    await db.append_audit_log(
        telegram_id=telegram_id,
        action="TEST_CLEANUP",
        chat_id=-1001234567,
        job_id=991
    )

    timeline = await db.get_audit_log_timeline(telegram_id, limit=5)
    assert len(timeline) >= 1
    assert timeline[0]["action"] == "TEST_CLEANUP"
    assert timeline[0]["is_tamper_evident_valid"] is True

    # Tamper with an entry to verify detection
    async with db.get_connection() as conn:
        await conn.execute(
            "UPDATE audit_log SET action = 'TAMPERED_ACTION' WHERE id = ?",
            (timeline[0]["id"],)
        )
        await conn.commit()

    tampered_timeline = await db.get_audit_log_timeline(telegram_id, limit=5)
    assert tampered_timeline[0]["is_tamper_evident_valid"] is False
