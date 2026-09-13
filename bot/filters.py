from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from typing import Union


class UserContextFilter(BaseFilter):
    """Ensures incoming update has a valid user context."""

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = event.from_user
        if not user or user.is_bot:
            return False
        return True
