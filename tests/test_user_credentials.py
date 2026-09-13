import io
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from telethon.errors import ApiIdInvalidError

from config import settings
from database import Database, db
from services.crypto_service import crypto_service
from telegram_client.auth import AuthManager
from telegram_client.exceptions import AuthRequiredException
from telegram_client.manager import client_manager
from webapp_server import app


@pytest.mark.asyncio
async def test_user_api_credentials_are_isolated():
    """Verifies credentials of User A are strictly isolated from User B."""
    await db.init_db()
    user_a = 91001
    user_b = 92002

    salt_a = crypto_service.generate_salt()
    salt_b = crypto_service.generate_salt()

    await db.get_or_create_user(user_a, salt=salt_a)
    await db.get_or_create_user(user_b, salt=salt_b)

    enc_id_a = crypto_service.encrypt_string("111111", salt_a)
    enc_hash_a = crypto_service.encrypt_string("hash_a_secret_key_111", salt_a)
    await db.set_user_credentials(user_a, enc_id_a, enc_hash_a, is_custom=1)

    enc_id_b = crypto_service.encrypt_string("222222", salt_b)
    enc_hash_b = crypto_service.encrypt_string("hash_b_secret_key_222", salt_b)
    await db.set_user_credentials(user_b, enc_id_b, enc_hash_b, is_custom=1)

    # User A's credentials
    creds_a = await db.get_user_credentials(user_a)
    assert creds_a is not None
    assert creds_a["telegram_id"] == user_a

    # User B's salt cannot decrypt User A's credentials
    with pytest.raises(Exception):
        crypto_service.decrypt_string(creds_a["encrypted_api_hash"], salt_b)

    # Decrypt with User A's salt works
    dec_hash_a = crypto_service.decrypt_string(creds_a["encrypted_api_hash"], salt_a)
    assert dec_hash_a == "hash_a_secret_key_111"


@pytest.mark.asyncio
async def test_api_hash_is_not_logged(caplog):
    """Verifies that API Hash is never printed or logged anywhere."""
    await db.init_db()
    auth_mgr = AuthManager()
    user_id = 93003
    secret_hash = "super_secret_api_hash_xyz_789"

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.connect = AsyncMock()
    mock_code_obj = MagicMock()
    mock_code_obj.phone_code_hash = "test_hash"
    mock_client.send_code_request = AsyncMock(return_value=mock_code_obj)
    mock_client.disconnect = AsyncMock()

    with patch("telegram_client.auth.TelegramClient", return_value=mock_client):
        with caplog.at_level(logging.DEBUG):
            await auth_mgr.request_phone_code(
                telegram_id=user_id,
                phone="+1234567890",
                api_id=123456,
                api_hash=secret_hash,
            )

    # Ensure secret hash is not in any log records
    for record in caplog.records:
        assert secret_hash not in record.message
        assert secret_hash not in str(record)


def test_api_hash_not_in_url():
    """Verifies that GET requests with credentials in URL query parameters are rejected (405 Method Not Allowed)."""
    client = TestClient(app)
    res = client.get("/api/login/send-code?api_hash=my_secret_hash")
    # GET is not allowed on POST-only endpoints
    assert res.status_code in (404, 405)


@pytest.mark.asyncio
async def test_invalid_api_id():
    """Verifies that non-positive integers or invalid API IDs are rejected."""
    await db.init_db()
    auth_mgr = AuthManager()
    user_id = 94004

    # Negative API ID
    with pytest.raises(AuthRequiredException) as exc_neg:
        await auth_mgr.request_phone_code(
            telegram_id=user_id,
            phone="+1234567890",
            api_id=-5,
            api_hash="valid_hash_12345",
        )
    assert "API ID должен быть положительным числом" in str(exc_neg.value)

    # Zero API ID
    with pytest.raises(AuthRequiredException) as exc_zero:
        await auth_mgr.request_phone_code(
            telegram_id=user_id,
            phone="+1234567890",
            api_id=0,
            api_hash="valid_hash_12345",
        )
    assert "API ID должен быть положительным числом" in str(exc_zero.value)


@pytest.mark.asyncio
async def test_invalid_api_hash():
    """Verifies that empty or whitespace API Hash is rejected."""
    await db.init_db()
    auth_mgr = AuthManager()
    user_id = 95005

    # Empty string
    with pytest.raises(AuthRequiredException) as exc_empty:
        await auth_mgr.request_phone_code(
            telegram_id=user_id,
            phone="+1234567890",
            api_id=12345,
            api_hash="",
        )
    assert "API Hash указан некорректно" in str(exc_empty.value)

    # Whitespace string
    with pytest.raises(AuthRequiredException) as exc_ws:
        await auth_mgr.request_phone_code(
            telegram_id=user_id,
            phone="+1234567890",
            api_id=12345,
            api_hash="    ",
        )
    assert "API Hash указан некорректно" in str(exc_ws.value)


@pytest.mark.asyncio
async def test_missing_api_credentials():
    """Verifies that missing credentials raise AuthRequiredException when no defaults or stored records exist."""
    await db.init_db()
    auth_mgr = AuthManager()
    user_id = 96006

    with patch.object(settings, "TELEGRAM_API_ID", None):
        with patch.object(settings, "API_ID", None):
            with patch.dict("os.environ", {"PYTEST_CURRENT_TEST": "", "TESTING": ""}, clear=False):
                with pytest.raises(AuthRequiredException) as exc:
                    await auth_mgr.request_phone_code(
                        telegram_id=user_id,
                        phone="+1234567890",
                        api_id=None,
                        api_hash=None,
                    )
                assert "укажите API ID и API Hash" in str(exc.value)


@pytest.mark.asyncio
async def test_reconnect_requires_credentials_when_needed():
    """Verifies that client loading fails gracefully if user credentials are absent."""
    await db.init_db()
    user_id = 97007
    salt = crypto_service.generate_salt()
    user = await db.get_or_create_user(user_id, salt=salt)
    user_salt = user.get("salt") or salt

    # Create dummy session file
    from pathlib import Path
    user_session_dir = Path(settings.SESSION_DIR) / "users" / str(user_id)
    user_session_dir.mkdir(parents=True, exist_ok=True)
    session_file = user_session_dir / "session.enc"
    encrypted_session = crypto_service.encrypt_string("dummy_string_session", user_salt)
    session_file.write_text(encrypted_session, encoding="utf-8")

    async with db.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (telegram_id, session_path, is_active) VALUES (?, ?, 1)
            ON CONFLICT(telegram_id) DO UPDATE SET session_path = excluded.session_path, is_active = 1
            """,
            (user_id, str(session_file)),
        )
        await conn.commit()

    # Ensure no credentials exist in DB for user
    await db.delete_user_credentials(user_id)

    with patch.object(settings, "TELEGRAM_API_ID", None):
        with patch.object(settings, "API_ID", None):
            with patch.dict("os.environ", {"PYTEST_CURRENT_TEST": "", "TESTING": ""}, clear=False):
                with pytest.raises(AuthRequiredException) as exc:
                    await client_manager.load_client(user_id)
                assert "введите API ID и API Hash" in str(exc.value)


@pytest.mark.asyncio
async def test_api_credentials_are_encrypted_if_persisted():
    """Verifies that credentials stored in SQLite are encrypted ciphertext, never plaintext."""
    await db.init_db()
    user_id = 98008
    salt = crypto_service.generate_salt()
    await db.get_or_create_user(user_id, salt=salt)

    plain_hash = "32charplaintexthashabcdef12345678"
    enc_hash = crypto_service.encrypt_string(plain_hash, salt)
    enc_id = crypto_service.encrypt_string("999888", salt)

    await db.set_user_credentials(user_id, enc_id, enc_hash, is_custom=1)

    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT encrypted_api_id, encrypted_api_hash FROM user_credentials WHERE telegram_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()

    assert row is not None
    # Raw value in database MUST NOT equal plaintext
    assert row["encrypted_api_hash"] != plain_hash
    assert plain_hash not in row["encrypted_api_hash"]
    assert "999888" not in row["encrypted_api_id"]


@pytest.mark.asyncio
async def test_telethon_api_id_invalid_handling():
    """Verifies that Telethon ApiIdInvalidError is caught and converted to a user-friendly error without traceback."""
    await db.init_db()
    auth_mgr = AuthManager()
    user_id = 99009

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.connect = AsyncMock()
    mock_client.send_code_request = AsyncMock(side_effect=ApiIdInvalidError(request=None))
    mock_client.disconnect = AsyncMock()

    with patch("telegram_client.auth.TelegramClient", return_value=mock_client):
        with pytest.raises(AuthRequiredException) as exc:
            await auth_mgr.request_phone_code(
                telegram_id=user_id,
                phone="+1234567890",
                api_id=99999999,
                api_hash="invalid_hash_abc",
            )
        assert "API ID или API Hash недействительны" in str(exc.value)
        # Client was safely disconnected
        mock_client.disconnect.assert_awaited_once()
