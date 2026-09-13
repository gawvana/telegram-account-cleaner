import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.models import AuthState, AuthStatus
from telegram_client.auth import AuthManager, PendingAuthSession


@pytest.mark.asyncio
async def test_auth_status_enum_completeness():
    expected_statuses = {
        "DISCONNECTED",
        "CONNECTING",
        "WAITING_FOR_CODE",
        "WAITING_FOR_2FA",
        "AUTHENTICATING",
        "CONNECTED",
        "RECONNECTING",
        "SESSION_EXPIRED",
        "ERROR",
    }
    actual_statuses = {s.value for s in AuthStatus}
    assert expected_statuses == actual_statuses, "AuthStatus must contain all required specification states"


@pytest.mark.asyncio
async def test_initial_state_disconnected():
    auth_mgr = AuthManager()
    user_id = 123456789
    state = await auth_mgr.get_auth_state(user_id)
    assert state.status == AuthStatus.DISCONNECTED
    assert state.is_authorized is False
    assert state.step == "PHONE"


@pytest.mark.asyncio
async def test_pending_session_expiration():
    auth_mgr = AuthManager()
    user_id = 987654321

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.disconnect = AsyncMock()

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+1234567890",
        phone_code_hash="test_hash",
    )
    pending.created_at = time.time() - 350
    assert pending.is_expired is True

    auth_mgr._pending_sessions[user_id] = pending

    state = await auth_mgr.get_auth_state(user_id)
    assert state.status == AuthStatus.DISCONNECTED
    assert user_id not in auth_mgr._pending_sessions
    mock_client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_cancel_cleans_resources():
    auth_mgr = AuthManager()
    user_id = 555444333

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.disconnect = AsyncMock()

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+1234567890",
        phone_code_hash="test_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    await auth_mgr.cancel_auth(user_id)
    assert user_id not in auth_mgr._pending_sessions
    mock_client.disconnect.assert_awaited_once()

    state = await auth_mgr.get_auth_state(user_id)
    assert state.status == AuthStatus.DISCONNECTED
