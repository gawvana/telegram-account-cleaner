from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from typing import Union


class UserContextFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        user = event.from_user
        if not user or user.is_bot:
            return False
        if isinstance(event, Message) and event.chat.type != "private":
            return False
        if isinstance(event, CallbackQuery) and event.message and event.message.chat.type != "private":
            return False
        return True
