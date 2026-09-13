import datetime
import re
from typing import Any, Dict, List, Optional
from telegram_client.models import ChatType, HeuristicTags


# Regex patterns commonly found in disposable or spam bot usernames
SPAM_BOT_PATTERNS = [
    re.compile(r".*(crypto|invest|trade|giveaway|bonus|claim|airdrop|casino|bet|porn|xxx|dating).*", re.IGNORECASE),
    re.compile(r"^[a-z]{3,}\d{5,}bot$", re.IGNORECASE),
    re.compile(r"bot_\d{4,}$", re.IGNORECASE),
]


class HeuristicsEngine:
    """Calculates non-destructive advisory recommendation tags for dialogs."""

    def __init__(self, dead_channel_threshold_days: int = 60, inactive_chat_threshold_days: int = 90):
        self.dead_channel_threshold_days = dead_channel_threshold_days
        self.inactive_chat_threshold_days = inactive_chat_threshold_days

    def evaluate(
        self,
        chat_type: ChatType,
        last_message_date: Optional[datetime.datetime] = None,
        username: Optional[str] = None,
        title: str = "",
        user_sent_messages: bool = True,
        is_pinned: bool = False,
        now: Optional[datetime.datetime] = None,
    ) -> HeuristicTags:
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        # Make sure timezone aware
        if last_message_date and last_message_date.tzinfo is None:
            last_message_date = last_message_date.replace(tzinfo=datetime.timezone.utc)

        tags: List[str] = []
        inactive_days = 0

        if last_message_date:
            delta = now - last_message_date
            inactive_days = max(int(delta.total_seconds() // 86400), 0)
        else:
            # If no date available, consider inactive
            inactive_days = 365

        likely_dead_channel = False
        likely_spam_bot = False
        zero_interaction = not user_sent_messages

        # Rule 1: Dead channel detection
        if chat_type == ChatType.CHANNEL and inactive_days >= self.dead_channel_threshold_days:
            likely_dead_channel = True
            tags.append(f"Мёртвый канал ({inactive_days} дн. без постов)")

        # Rule 2: Likely spam bot detection
        if chat_type == ChatType.BOT:
            is_suspicious_name = False
            check_str = f"{username or ''} {title}"
            for pat in SPAM_BOT_PATTERNS:
                if pat.search(check_str):
                    is_suspicious_name = True
                    break

            if is_suspicious_name or (inactive_days >= 30 and not is_pinned):
                likely_spam_bot = True
                tags.append("Подозрительный/неактивный бот")

        # Rule 3: Zero interaction in private chats
        if chat_type == ChatType.PRIVATE and zero_interaction and inactive_days >= self.inactive_chat_threshold_days:
            tags.append(f"Нет взаимодействия ({inactive_days} дн.)")

        # Rule 4: Deeply inactive chats
        if inactive_days >= 180 and not is_pinned:
            tags.append(f"Неактивен > 6 мес ({inactive_days} дн.)")

        # Recommendation: solely advisory! Never executes anything on its own.
        recommended = (
            not is_pinned
            and (
                likely_dead_channel
                or likely_spam_bot
                or (zero_interaction and inactive_days >= self.inactive_chat_threshold_days)
                or (chat_type in [ChatType.BOT, ChatType.CHANNEL] and inactive_days >= 120)
            )
        )

        return HeuristicTags(
            inactive_days=inactive_days,
            likely_dead_channel=likely_dead_channel,
            likely_spam_bot=likely_spam_bot,
            zero_interaction=zero_interaction,
            recommended_for_cleanup=recommended,
            tags=tags,
        )


heuristics_engine = HeuristicsEngine()
