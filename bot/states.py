from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    """FSM states for chat-based Telegram authentication fallback."""
    waiting_phone = State()
    waiting_code = State()
    waiting_2fa = State()


class ConfirmStates(StatesGroup):
    """FSM states for two-step explicit text confirmation."""
    waiting_max_clean_confirm = State()
    waiting_category_confirm = State()


class WhitelistStates(StatesGroup):
    """FSM states for adding chat to whitelist via chat."""
    waiting_chat_input = State()
