import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.handlers import router as bot_router
from config import settings
from database import db
from services.scheduler_service import scheduler_service
from utils.logger import logger


async def register_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Запустить CLIN"),
        BotCommand(command="help", description="Помощь и руководство"),
        BotCommand(command="scan", description="Сканировать диалоги"),
        BotCommand(command="clean", description="Очистка аккаунта"),
        BotCommand(command="history", description="История и статистика"),
        BotCommand(command="support", description="Служба поддержки тикетов"),
        BotCommand(command="settings", description="Настройки и аккаунт"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Registered bot slash commands with Telegram.")
    except Exception as e:
        logger.warning(f"Could not register bot commands: {e}")


async def main():
    logger.info("Initializing CLIN — Telegram Account Cleaner v2.1...")

    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in configuration or .env file! Exiting.")
        return

    # Initialize Database
    await db.init_db()

    # Initialize Bot & Dispatcher
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_router)

    # Register Bot Slash Commands
    await register_bot_commands(bot)

    # Wire notification callback for APScheduler
    async def _send_notification(telegram_id: int, text: str):
        try:
            await bot.send_message(chat_id=telegram_id, text=text)
        except Exception as e:
            logger.error(f"Failed to deliver scheduled report to {telegram_id}: {e}")

    scheduler_service.set_bot_callback(_send_notification)

    # Start Scheduler
    if settings.SCHEDULER_ENABLED:
        scheduler_service.start()
        await scheduler_service.sync_all_schedules()

    logger.info("CLIN Bot starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down CLIN Bot...")
        scheduler_service.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot process exited.")
