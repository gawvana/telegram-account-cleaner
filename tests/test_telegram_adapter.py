import pytest
from domain.models import ChatType, RawDialogDTO
from telegram_client.base import ITelegramClientAdapter
from telegram_client.exceptions import (
    AuthRequiredException,
    InvalidCodeError,
    InvalidPasswordError,
    PasswordRequiredError,
)
from telegram_client.mock_adapter import MockTelegramClientAdapter


@pytest.mark.asyncio
async def test_mock_adapter_contract():
    adapter: ITelegramClientAdapter = MockTelegramClientAdapter(is_authorized=True, user_id=555666)

    # 1. Connection and auth state
    assert await adapter.is_connected() is True
    assert await adapter.is_user_authorized() is True

    me = await adapter.get_me()
    assert me is not None
    assert me["id"] == 555666

    # 2. Dialog retrieval
    dialogs = await adapter.fetch_dialogs()
    assert len(dialogs) >= 3
    assert all(isinstance(d, RawDialogDTO) for d in dialogs)

    # 3. Dialog actions
    deleted = await adapter.delete_dialog(101)
    assert deleted is True

    left = await adapter.leave_chat(103)
    assert left is True

    blocked = await adapter.block_bot(102)
    assert blocked is True

    remaining = await adapter.fetch_dialogs()
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_mock_adapter_auth_errors():
    adapter = MockTelegramClientAdapter(is_authorized=False, require_2fa=True)

    # Fetching without authorization raises AuthRequiredException
    with pytest.raises(AuthRequiredException):
        await adapter.fetch_dialogs()

    # Request code
    p_hash = await adapter.send_code_request("+1234567890")
    assert p_hash is not None

    # Invalid code
    with pytest.raises(InvalidCodeError):
        await adapter.sign_in_code("+1234567890", "00000", p_hash)

    # 2FA needed
    with pytest.raises(PasswordRequiredError):
        await adapter.sign_in_code("+1234567890", "12345", p_hash)

    # Incorrect 2FA password
    with pytest.raises(InvalidPasswordError):
        await adapter.sign_in_password("wrong_password")

    # Correct 2FA password
    success = await adapter.sign_in_password("correct_password")
    assert success is True
    assert await adapter.is_user_authorized() is True
