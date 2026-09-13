import asyncio
from typing import Any, Dict, List, Optional
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserNotParticipantError,
)
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.contacts import BlockRequest

from config import settings
from database import db
from telegram_client.exceptions import FloodWaitTimeoutException, UserCancelledException
from telegram_client.models import ChatType, CleanupItemResult, DialogItem
from utils.logger import logger
from utils.progress import ProgressTracker


class AccountCleaner:
    """Executes safe and compliant cleanup operations over authorized Telegram account."""

    async def extract_rejoin_data(
        self, client: TelegramClient, entity: Any, item: DialogItem
    ) -> Optional[Dict[str, Any]]:
        """Captures public link or username for channels/groups before departure."""
        if item.chat_type not in [ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP]:
            return None

        username = getattr(entity, "username", None) or item.username
        invite_link = f"https://t.me/{username}" if username else None

        return {
            "chat_id": item.chat_id,
            "title": item.title,
            "username": username,
            "invite_link": invite_link,
            "chat_type": item.chat_type.value,
        }

    async def clean_single_item(
        self,
        client: TelegramClient,
        item: DialogItem,
        dry_run: bool = False,
    ) -> CleanupItemResult:
        """Processes a single dialog item with retries, FloodWait handling, and safety checks."""
        # Hard Whitelist Guarantee
        if item.is_whitelisted:
            return CleanupItemResult(
                chat_id=item.chat_id,
                title=item.title,
                chat_type=item.chat_type,
                action="SKIP",
                status="SKIPPED",
                error_message="Защищено белым списком (Whitelist)",
            )

        # Creator / Special Rights Hard Safety Guarantee
        if item.is_creator or item.requires_special_rights:
            return CleanupItemResult(
                chat_id=item.chat_id,
                title=item.title,
                chat_type=item.chat_type,
                action="SKIP",
                status="SKIPPED",
                error_message="Защищено: вы являетесь создателем/владельцем этого диалога.",
            )

        # System Dialogs and Saved Messages Protection
        if item.chat_id == 777000 or (not item.can_delete and not item.can_leave):
            return CleanupItemResult(
                chat_id=item.chat_id,
                title=item.title,
                chat_type=item.chat_type,
                action="SKIP",
                status="SKIPPED",
                error_message="Защищено: системный диалог или Избранное.",
            )

        if dry_run:
            action = "LEAVE" if item.chat_type in [ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP] else "DELETE"
            return CleanupItemResult(
                chat_id=item.chat_id,
                title=item.title,
                chat_type=item.chat_type,
                action=action,
                status="SUCCESS",
                error_message=None,
            )

        retries = 0
        while retries <= settings.MAX_RETRIES:
            try:
                entity = await client.get_input_entity(item.chat_id)
                rejoin_data = await self.extract_rejoin_data(client, entity, item)

                if item.chat_type == ChatType.BOT:
                    # Stop/block bot and delete dialog history
                    try:
                        await client(BlockRequest(id=entity))
                    except Exception:
                        pass
                    await client.delete_dialog(entity)
                    return CleanupItemResult(
                        chat_id=item.chat_id,
                        title=item.title,
                        chat_type=item.chat_type,
                        action="STOP_BOT",
                        status="SUCCESS",
                    )

                elif item.chat_type in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
                    # Leave channel or supergroup
                    await client(LeaveChannelRequest(channel=entity))
                    return CleanupItemResult(
                        chat_id=item.chat_id,
                        title=item.title,
                        chat_type=item.chat_type,
                        action="LEAVE_CHANNEL",
                        status="SUCCESS",
                        rejoin_data=rejoin_data,
                    )

                elif item.chat_type == ChatType.GROUP:
                    # Leave basic group
                    await client.delete_dialog(entity)
                    return CleanupItemResult(
                        chat_id=item.chat_id,
                        title=item.title,
                        chat_type=item.chat_type,
                        action="LEAVE_GROUP",
                        status="SUCCESS",
                        rejoin_data=rejoin_data,
                    )

                else:
                    # Private chat: delete dialog (revoke=False to respect recipient privacy/rules)
                    await client.delete_dialog(entity)
                    return CleanupItemResult(
                        chat_id=item.chat_id,
                        title=item.title,
                        chat_type=item.chat_type,
                        action="DELETE_CHAT",
                        status="SUCCESS",
                    )

            except FloodWaitError as e:
                logger.warning(f"Telegram FloodWait encountered: {e.seconds} seconds required")
                if e.seconds <= settings.FLOOD_WAIT_MAX_SLEEP:
                    await asyncio.sleep(e.seconds + 1)
                    retries += 1
                    continue
                else:
                    raise FloodWaitTimeoutException(e.seconds)

            except (UserNotParticipantError, ChannelPrivateError):
                # Already left or inaccessible
                return CleanupItemResult(
                    chat_id=item.chat_id,
                    title=item.title,
                    chat_type=item.chat_type,
                    action="LEAVE",
                    status="SKIPPED",
                    error_message="Уже покинут или недоступен",
                )

            except ChatAdminRequiredError:
                return CleanupItemResult(
                    chat_id=item.chat_id,
                    title=item.title,
                    chat_type=item.chat_type,
                    action="LEAVE",
                    status="ERROR",
                    error_message="Требуются права администратора",
                )

            except Exception as ex:
                retries += 1
                if retries > settings.MAX_RETRIES:
                    logger.error(f"Failed to process chat {item.chat_id} after {settings.MAX_RETRIES} retries: {ex}")
                    return CleanupItemResult(
                        chat_id=item.chat_id,
                        title=item.title,
                        chat_type=item.chat_type,
                        action="CLEANUP",
                        status="ERROR",
                        error_message="Telegram API вернул временную ошибку.",
                    )
                await asyncio.sleep(2 ** retries)

        return CleanupItemResult(
            chat_id=item.chat_id,
            title=item.title,
            chat_type=item.chat_type,
            action="CLEANUP",
            status="ERROR",
            error_message="Превышено число попыток.",
        )

    async def execute_plan(
        self,
        client: TelegramClient,
        telegram_id: int,
        job_id: int,
        items: List[DialogItem],
        dry_run: bool = False,
        cancel_event: Optional[asyncio.Event] = None,
        progress_tracker: Optional[ProgressTracker] = None,
    ) -> List[CleanupItemResult]:
        """Iterates through planned dialogs, adhering to rate limits and cooperative cancellation."""
        results: List[CleanupItemResult] = []

        for item in items:
            # Check for instant cooperative cancellation
            if cancel_event and cancel_event.is_set():
                logger.info(f"Cleanup job {job_id} for user {telegram_id} stopped via cancel event.")
                raise UserCancelledException("Операция остановлена пользователем.")

            res = await self.clean_single_item(client, item, dry_run=dry_run)
            results.append(res)

            # Store result in cleanup_items DB table
            async with db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO cleanup_items (job_id, chat_id, chat_title, chat_type, action, status, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        res.chat_id,
                        res.title,
                        res.chat_type.value if hasattr(res.chat_type, "value") else str(res.chat_type),
                        res.action,
                        res.status,
                        res.error_message,
                    ),
                )

                # Save to Rejoin Manifest if applicable
                if res.rejoin_data and res.status == "SUCCESS" and not dry_run:
                    rd = res.rejoin_data
                    await conn.execute(
                        """
                        INSERT INTO rejoin_manifest (telegram_id, job_id, chat_id, title, username, invite_link, chat_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            telegram_id,
                            job_id,
                            rd["chat_id"],
                            rd["title"],
                            rd["username"],
                            rd["invite_link"],
                            rd["chat_type"],
                        ),
                    )

                await conn.commit()

            # Record in tamper-evident audit log
            if not dry_run and res.status == "SUCCESS":
                await db.append_audit_log(
                    telegram_id=telegram_id,
                    action=f"{res.action}:{res.status}",
                    job_id=job_id,
                    chat_id=res.chat_id,
                )

            # Advance progress tracker
            if progress_tracker:
                await progress_tracker.advance(
                    item_title=item.title,
                    action=res.action,
                    skipped=(res.status == "SKIPPED"),
                    error=(res.status == "ERROR"),
                )

            # Rate limit pause only on executed operations
            if not dry_run and res.status in ("SUCCESS", "ERROR"):
                await asyncio.sleep(settings.RATE_LIMIT_DELAY)

        return results


cleaner = AccountCleaner()
