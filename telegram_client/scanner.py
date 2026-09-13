import datetime
from typing import Dict, List, Optional, Set
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User, ChannelForbidden, ChatForbidden

from database import db
from telegram_client.heuristics import heuristics_engine
from telegram_client.models import ChatType, DialogItem, ScanResult
from utils.logger import logger


class AccountScanner:
    """Discovers and classifies all user dialogs with permission and heuristic checks."""

    async def scan(self, client: TelegramClient, telegram_id: int) -> ScanResult:
        logger.info(f"Starting account scan for user {telegram_id}")

        # Fetch whitelist chat_ids and patterns for user
        whitelisted_ids: Set[int] = set()
        rules: List[str] = []
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT chat_id, rule_pattern FROM whitelist WHERE telegram_id = ?",
                (telegram_id,),
            )
            for row in await cursor.fetchall():
                whitelisted_ids.add(row["chat_id"])
                if row["rule_pattern"]:
                    rules.append(row["rule_pattern"])

        # Fetch user settings for dead channel threshold
        dead_channel_days = 60
        async with db.get_connection() as conn:
            s_cursor = await conn.execute(
                "SELECT dead_channel_days FROM settings WHERE telegram_id = ?",
                (telegram_id,),
            )
            s_row = await s_cursor.fetchone()
            if s_row and s_row["dead_channel_days"]:
                dead_channel_days = s_row["dead_channel_days"]

        heuristics_engine.dead_channel_threshold_days = dead_channel_days

        now = datetime.datetime.now(datetime.timezone.utc)
        items: List[DialogItem] = []

        dialogs = await client.get_dialogs(limit=None)
        total_dialogs = len(dialogs)

        private_count = 0
        bot_count = 0
        group_count = 0
        channel_count = 0
        whitelisted_count = 0
        recommended_count = 0
        actionable_count = 0
        special_rights_count = 0
        inaccessible_count = 0

        for d in dialogs:
            entity = d.entity
            chat_id = d.id
            title = d.name or "Unnamed Dialog"
            username = getattr(entity, "username", None)
            is_pinned = bool(d.pinned)
            is_archived = bool(d.archived)
            unread_count = d.unread_count or 0
            last_date = d.date

            chat_type = ChatType.OTHER
            is_creator = bool(getattr(entity, "creator", False))
            is_admin = bool(getattr(entity, "admin_rights", None) or getattr(entity, "admin", False))

            # Determine Chat Type
            if isinstance(entity, User):
                if entity.bot:
                    chat_type = ChatType.BOT
                    bot_count += 1
                else:
                    chat_type = ChatType.PRIVATE
                    private_count += 1
            elif isinstance(entity, Channel):
                if entity.megagroup or entity.gigagroup:
                    chat_type = ChatType.SUPERGROUP
                    group_count += 1
                else:
                    chat_type = ChatType.CHANNEL
                    channel_count += 1
            elif isinstance(entity, Chat):
                chat_type = ChatType.GROUP
                group_count += 1
            elif isinstance(entity, (ChannelForbidden, ChatForbidden)):
                chat_type = ChatType.CHANNEL if isinstance(entity, ChannelForbidden) else ChatType.GROUP
                inaccessible_count += 1

            # Check Whitelist
            is_whitelisted = chat_id in whitelisted_ids

            # Dynamic rule patterns check (e.g. "admin_groups")
            if not is_whitelisted and "admin_groups" in rules and (is_creator or is_admin):
                is_whitelisted = True

            # Hard safety protection: Saved Messages & Telegram Service notifications
            is_self = bool(getattr(entity, "is_self", False)) or (isinstance(entity, User) and entity.id == telegram_id)
            is_telegram_service = (chat_id == 777000) or (isinstance(entity, User) and entity.id == 777000)

            if is_self or is_telegram_service:
                is_whitelisted = True

            if is_whitelisted:
                whitelisted_count += 1

            # Permissions Check
            requires_special_rights = False
            can_leave = True
            can_delete = True

            if is_self or is_telegram_service:
                can_delete = False
                can_leave = False

            if is_creator and chat_type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                # Creator cannot leave own group/channel; needs ownership transfer or deletion
                requires_special_rights = True
                can_leave = False
                can_delete = False
                special_rights_count += 1

            # Evaluate Heuristics (advisory only!)
            # Check user participation if available
            heuristics = heuristics_engine.evaluate(
                chat_type=chat_type,
                last_message_date=last_date,
                username=username,
                title=title,
                user_sent_messages=True,  # Default safe assumption
                is_pinned=is_pinned,
                now=now,
            )

            if heuristics.recommended_for_cleanup and not is_whitelisted:
                recommended_count += 1

            if not is_whitelisted:
                actionable_count += 1

            dialog_item = DialogItem(
                chat_id=chat_id,
                title=title,
                username=username,
                chat_type=chat_type,
                unread_count=unread_count,
                is_pinned=is_pinned,
                is_archived=is_archived,
                is_creator=is_creator,
                is_admin=is_admin,
                is_whitelisted=is_whitelisted,
                can_leave=can_leave,
                can_delete=can_delete,
                requires_special_rights=requires_special_rights,
                last_message_date=last_date,
                heuristics=heuristics,
            )
            items.append(dialog_item)

        logger.info(
            f"User {telegram_id} scan finished: {total_dialogs} dialogs "
            f"(Private: {private_count}, Bots: {bot_count}, Groups: {group_count}, Channels: {channel_count})"
        )

        return ScanResult(
            total_dialogs=total_dialogs,
            private_chats=private_count,
            bot_chats=bot_count,
            group_chats=group_count,
            channel_chats=channel_count,
            private_count=private_count,
            bots_count=bot_count,
            groups_count=group_count,
            channels_count=channel_count,
            whitelisted_count=whitelisted_count,
            recommended_count=recommended_count,
            actionable_count=actionable_count,
            special_rights_count=special_rights_count,
            inaccessible_count=inaccessible_count,
            items=items,
        )


scanner = AccountScanner()
