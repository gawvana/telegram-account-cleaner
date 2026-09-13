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


@pytest.mark.asyncio
async def test_expired_code_does_not_deadlock():
    from telethon.errors import PhoneCodeExpiredError
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 111222333

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.disconnect = AsyncMock()
    mock_client.sign_in = AsyncMock(side_effect=PhoneCodeExpiredError(request=None))

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="fake_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    # Must complete within 5.0 seconds without deadlock
    with pytest.raises(AuthRequiredException) as exc_info:
        await asyncio.wait_for(auth_mgr.submit_auth_code(user_id, "12345"), timeout=5.0)

    assert "истёк" in str(exc_info.value)
    assert user_id not in auth_mgr._pending_sessions
    mock_client.disconnect.assert_awaited_once()

    # Verify lock is released and subsequent calls work
    state = await asyncio.wait_for(auth_mgr.get_auth_state(user_id), timeout=5.0)
    assert state.status == AuthStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_invalid_code_does_not_deadlock():
    from telethon.errors import PhoneCodeInvalidError
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 222333444

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.disconnect = AsyncMock()
    mock_client.sign_in = AsyncMock(side_effect=PhoneCodeInvalidError(request=None))

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="fake_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    with pytest.raises(AuthRequiredException) as exc_info:
        await asyncio.wait_for(auth_mgr.submit_auth_code(user_id, "99999"), timeout=5.0)

    assert "Неверный код" in str(exc_info.value)
    assert user_id in auth_mgr._pending_sessions
    assert auth_mgr._pending_sessions[user_id].status == AuthStatus.WAITING_FOR_CODE

    # Verify lock is released
    state = await asyncio.wait_for(auth_mgr.get_auth_state(user_id), timeout=5.0)
    assert state.status == AuthStatus.WAITING_FOR_CODE


@pytest.mark.asyncio
async def test_invalid_2fa_does_not_deadlock():
    from telethon.errors import PasswordHashInvalidError
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 333444555

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.disconnect = AsyncMock()
    mock_client.sign_in = AsyncMock(side_effect=PasswordHashInvalidError(request=None))

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="fake_hash",
    )
    pending.status = AuthStatus.WAITING_FOR_2FA
    auth_mgr._pending_sessions[user_id] = pending

    with pytest.raises(AuthRequiredException) as exc_info:
        await asyncio.wait_for(auth_mgr.submit_2fa_password(user_id, "wrong_pw"), timeout=5.0)

    assert "Неверный 2FA пароль" in str(exc_info.value)
    assert auth_mgr._pending_sessions[user_id].status == AuthStatus.WAITING_FOR_2FA

    # Verify lock is released
    state = await asyncio.wait_for(auth_mgr.get_auth_state(user_id), timeout=5.0)
    assert state.status == AuthStatus.WAITING_FOR_2FA


@pytest.mark.asyncio
async def test_cancel_auth_does_not_deadlock():
    auth_mgr = AuthManager()
    user_id = 444555666

    mock_client = MagicMock()
    mock_client.is_connected.return_value = True
    mock_client.disconnect = AsyncMock()

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="fake_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    await asyncio.wait_for(auth_mgr.cancel_auth(user_id), timeout=5.0)
    assert user_id not in auth_mgr._pending_sessions
    mock_client.disconnect.assert_awaited_once()

    # Redundant cancel call should finish immediately without blocking
    await asyncio.wait_for(auth_mgr.cancel_auth(user_id), timeout=5.0)
    state = await asyncio.wait_for(auth_mgr.get_auth_state(user_id), timeout=5.0)
    assert state.status == AuthStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_login_can_restart_after_failed_auth():
    from telethon.errors import PhoneCodeExpiredError
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 555666777

    mock_client1 = MagicMock()
    mock_client1.is_connected.return_value = True
    mock_client1.disconnect = AsyncMock()
    mock_client1.sign_in = AsyncMock(side_effect=PhoneCodeExpiredError(request=None))

    pending1 = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client1,
        phone="+79991234567",
        phone_code_hash="first_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending1

    with pytest.raises(AuthRequiredException):
        await asyncio.wait_for(auth_mgr.submit_auth_code(user_id, "11111"), timeout=5.0)

    assert user_id not in auth_mgr._pending_sessions

    # User restarts auth cleanly
    mock_client2 = MagicMock()
    mock_client2.is_connected.return_value = True
    mock_client2.disconnect = AsyncMock()

    pending2 = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client2,
        phone="+79991234567",
        phone_code_hash="second_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending2

    state = await asyncio.wait_for(auth_mgr.get_auth_state(user_id), timeout=5.0)
    assert state.status == AuthStatus.WAITING_FOR_CODE
    assert state.phone_code_hash == "second_hash"


@pytest.mark.asyncio
async def test_duplicate_auth_attempt_is_safe():
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 666777888

    lock = await auth_mgr._get_user_lock(user_id)
    await lock.acquire()

    try:
        with pytest.raises(AuthRequiredException) as exc_info:
            await asyncio.wait_for(
                auth_mgr.request_phone_code(user_id, "+79991112233"),
                timeout=5.0,
            )
        assert "уже выполняется" in str(exc_info.value)
    finally:
        lock.release()


@pytest.mark.asyncio
async def test_auth_state_rolls_back_on_floodwait():
    from telethon.errors import FloodWaitError
    from telegram_client.exceptions import FloodWaitTimeoutException

    auth_mgr = AuthManager()
    user_id = 777888991

    mock_client = MagicMock()
    mock_client.sign_in = AsyncMock(side_effect=FloodWaitError(request=None, capture=0))
    mock_client.sign_in.side_effect.seconds = 45

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="test_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    with pytest.raises(FloodWaitTimeoutException):
        await asyncio.wait_for(auth_mgr.submit_auth_code(user_id, "12345"), timeout=5.0)

    assert pending.status == AuthStatus.WAITING_FOR_CODE


@pytest.mark.asyncio
async def test_auth_state_rolls_back_on_rpc_error():
    from telethon.errors import RPCError
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 777888992

    mock_client = MagicMock()
    mock_client.sign_in = AsyncMock(side_effect=RPCError(request=None, message="RPC_CALL_FAIL"))

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="test_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    with pytest.raises(AuthRequiredException):
        await asyncio.wait_for(auth_mgr.submit_auth_code(user_id, "12345"), timeout=5.0)

    assert pending.status == AuthStatus.WAITING_FOR_CODE


@pytest.mark.asyncio
async def test_auth_state_rolls_back_on_network_error():
    from telegram_client.exceptions import AuthRequiredException

    auth_mgr = AuthManager()
    user_id = 777888993

    mock_client = MagicMock()
    mock_client.sign_in = AsyncMock(side_effect=ConnectionResetError("Connection lost"))

    pending = PendingAuthSession(
        telegram_id=user_id,
        client=mock_client,
        phone="+79991234567",
        phone_code_hash="test_hash",
    )
    auth_mgr._pending_sessions[user_id] = pending

    with pytest.raises(AuthRequiredException):
        await asyncio.wait_for(auth_mgr.submit_auth_code(user_id, "12345"), timeout=5.0)

    assert pending.status == AuthStatus.WAITING_FOR_CODE


