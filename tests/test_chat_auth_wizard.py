import pytest
from bot.states import AuthStates
from bot.keyboards import get_account_keyboard, get_api_help_keyboard, get_auth_cancel_keyboard
from bot.filters import UserContextFilter
from bot import handlers
from aiogram.types import Chat, Message
from unittest.mock import AsyncMock, MagicMock, patch

def test_auth_states():
    assert hasattr(AuthStates, "waiting_api_id")
    assert hasattr(AuthStates, "waiting_api_hash")
    assert hasattr(AuthStates, "waiting_phone")
    assert hasattr(AuthStates, "waiting_code")
    assert hasattr(AuthStates, "waiting_2fa")

def test_keyboards():
    kb = get_account_keyboard(False)
    # Convert to dict or string to check contents easily, let's assume aiogram ReplyKeyboardMarkup or InlineKeyboardMarkup
    kb_str = str(kb.model_dump() if hasattr(kb, "model_dump") else kb)
    assert "Подключить через чат" in kb_str

    api_help_kb = get_api_help_keyboard()
    assert api_help_kb is not None

    cancel_kb = get_auth_cancel_keyboard()
    assert cancel_kb is not None

@pytest.mark.asyncio
async def test_user_context_filter():
    filter_instance = UserContextFilter()
    
    from aiogram.types import User
    user = User(id=1, is_bot=False, first_name="Test")
    private_chat = Chat(id=1, type="private")
    private_msg = Message(message_id=1, date=0, chat=private_chat, from_user=user)
    assert await filter_instance(private_msg) == True
    
    group_chat = Chat(id=2, type="group")
    group_msg = Message(message_id=2, date=0, chat=group_chat, from_user=user)
    assert await filter_instance(group_msg) == False

@pytest.mark.asyncio
async def test_step1_api_id_validation():
    # Valid
    msg = AsyncMock()
    msg.text = "123456"
    state = AsyncMock()
    await handlers.process_chat_login_api_id(msg, state)
    state.update_data.assert_called_once_with(api_id=123456)
    
    # Invalid
    msg = AsyncMock()
    msg.text = "123abc"
    state = AsyncMock()
    await handlers.process_chat_login_api_id(msg, state)
    state.update_data.assert_not_called()

@pytest.mark.asyncio
async def test_step2_api_hash_validation():
    # Valid
    msg = AsyncMock()
    msg.text = "a" * 32
    state = AsyncMock()
    await handlers.process_chat_login_api_hash(msg, state)
    state.update_data.assert_called_once_with(api_hash="a"*32)
    
    # Invalid length
    msg = AsyncMock()
    msg.text = "a" * 15
    state = AsyncMock()
    await handlers.process_chat_login_api_hash(msg, state)
    state.update_data.assert_not_called()

@pytest.mark.asyncio
async def test_cb_auth_cancel():
    from bot.handlers import cb_auth_cancel
    callback_query = AsyncMock()
    callback_query.from_user.id = 123
    state = AsyncMock()
    with patch('bot.handlers.auth_manager.cancel_auth', new_callable=AsyncMock) as mock_cancel:
        await cb_auth_cancel(callback_query, state)
        mock_cancel.assert_called_once_with(123)
        state.clear.assert_called_once()
