import datetime
from telegram_client.heuristics import HeuristicsEngine
from telegram_client.models import ChatType


def test_dead_channel_heuristic():
    engine = HeuristicsEngine(dead_channel_threshold_days=60)
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Dead channel (last post 75 days ago)
    old_date = now - datetime.timedelta(days=75)
    tags_dead = engine.evaluate(
        chat_type=ChatType.CHANNEL,
        last_message_date=old_date,
        title="Old Tech News",
        now=now,
    )
    assert tags_dead.likely_dead_channel is True
    assert tags_dead.recommended_for_cleanup is True
    assert any("Мёртвый канал" in t for t in tags_dead.tags)

    # 2. Active channel (last post 2 days ago)
    recent_date = now - datetime.timedelta(days=2)
    tags_active = engine.evaluate(
        chat_type=ChatType.CHANNEL,
        last_message_date=recent_date,
        title="Daily Updates",
        now=now,
    )
    assert tags_active.likely_dead_channel is False
    assert tags_active.recommended_for_cleanup is False


def test_spam_bot_heuristic():
    engine = HeuristicsEngine()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Suspicious bot
    tags = engine.evaluate(
        chat_type=ChatType.BOT,
        last_message_date=now - datetime.timedelta(days=10),
        username="free_crypto_airdrop_bonus_bot",
        title="Crypto Free Claim Bot",
        now=now,
    )
    assert tags.likely_spam_bot is True
    assert tags.recommended_for_cleanup is True


def test_zero_interaction_heuristic():
    engine = HeuristicsEngine(inactive_chat_threshold_days=90)
    now = datetime.datetime.now(datetime.timezone.utc)

    # Private chat with 0 user messages and 100 days old
    tags = engine.evaluate(
        chat_type=ChatType.PRIVATE,
        last_message_date=now - datetime.timedelta(days=100),
        user_sent_messages=False,
        is_pinned=False,
        now=now,
    )
    assert tags.zero_interaction is True
    assert tags.recommended_for_cleanup is True


def test_pinned_chats_protected_from_recommendation():
    engine = HeuristicsEngine()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Pinned chat should not be recommended even if inactive
    tags = engine.evaluate(
        chat_type=ChatType.CHANNEL,
        last_message_date=now - datetime.timedelta(days=120),
        is_pinned=True,
        now=now,
    )
    assert tags.recommended_for_cleanup is False
