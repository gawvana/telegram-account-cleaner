"""
Telegram Bot Profile Configuration for CLIN.
Registers bot name, short description, description, slash commands, and WebApp menu button
across multiple languages (RU, EN, default).
"""
import asyncio
from aiogram import Bot
from aiogram.types import (
    BotCommand,
    MenuButtonWebApp,
    WebAppInfo,
)
from config import settings
from utils.logger import logger


RU_NAME = "CLIN — Очистка Telegram"
EN_NAME = "CLIN — Telegram Account Cleaner"

RU_SHORT_DESC = "Умная и безопасная очистка Telegram: каналы, группы, боты и удалённые аккаунты."
EN_SHORT_DESC = "Smart & secure Telegram cleaner: inactive channels, dead groups, bots, and deleted accounts."

RU_DESC = (
    "🧹 CLIN — Telegram Account Cleaner\n\n"
    "Безопасная утилита для очистки и управления вашим Telegram-аккаунтом.\n\n"
    "✨ Возможности:\n"
    "• Анализ диалогов: неактивные каналы, группы и боты\n"
    "• Защита важных чатов: Whitelist и закреплённые диалоги\n"
    "• Безопасность: сквозное шифрование сессий (Fernet)\n"
    "• Оценка гигиены аккаунта и журнал действий\n"
    "• Mini App в стиле Apple Liquid Glass\n\n"
    "Нажмите «Запустить» или «Открыть CLIN»!"
)

EN_DESC = (
    "🧹 CLIN — Telegram Account Cleaner\n\n"
    "Secure utility for cleaning and managing your Telegram account.\n\n"
    "✨ Features:\n"
    "• Dialog Analysis: inactive channels, groups & bots\n"
    "• Whitelist: protect important chats & pinned dialogs\n"
    "• Security: local session encryption (Fernet)\n"
    "• Account Hygiene Score and audit history\n"
    "• Modern Apple Liquid Glass Mini App\n\n"
    "Tap Start or Open CLIN to begin!"
)

COMMANDS_RU = [
    BotCommand(command="start", description="Запустить бота и открыть Mini App"),
    BotCommand(command="clean", description="Очистка неактивных чатов и каналов"),
    BotCommand(command="scan", description="Экспресс-сканирование диалогов"),
    BotCommand(command="account", description="Статус подключения и сессии"),
    BotCommand(command="history", description="История и статистика очисток"),
    BotCommand(command="support", description="Служба поддержки и тикеты"),
    BotCommand(command="help", description="Возможности и безопасность"),
]

COMMANDS_EN = [
    BotCommand(command="start", description="Launch bot and open Mini App"),
    BotCommand(command="clean", description="Clean inactive chats and channels"),
    BotCommand(command="scan", description="Scan and analyze dialogs"),
    BotCommand(command="account", description="Account and session status"),
    BotCommand(command="history", description="Cleanup history and logs"),
    BotCommand(command="support", description="Support service and tickets"),
    BotCommand(command="help", description="Guide and security"),
]


async def setup_bot_profile(bot: Bot) -> dict:
    """Configures name, descriptions, commands, and menu button in Telegram."""
    results = {}

    # 1. Names
    try:
        await bot.set_my_name(name=EN_NAME)
        await bot.set_my_name(name=RU_NAME, language_code="ru")
        await bot.set_my_name(name=EN_NAME, language_code="en")
        results["name"] = "ok"
    except Exception as e:
        logger.warning(f"Failed to set bot name: {e}")
        results["name"] = str(e)

    # 2. Short Descriptions (0-120 chars)
    try:
        await bot.set_my_short_description(short_description=EN_SHORT_DESC)
        await bot.set_my_short_description(short_description=RU_SHORT_DESC, language_code="ru")
        await bot.set_my_short_description(short_description=EN_SHORT_DESC, language_code="en")
        results["short_description"] = "ok"
    except Exception as e:
        logger.warning(f"Failed to set bot short description: {e}")
        results["short_description"] = str(e)

    # 3. Full Descriptions (0-512 chars)
    try:
        await bot.set_my_description(description=EN_DESC)
        await bot.set_my_description(description=RU_DESC, language_code="ru")
        await bot.set_my_description(description=EN_DESC, language_code="en")
        results["description"] = "ok"
    except Exception as e:
        logger.warning(f"Failed to set bot full description: {e}")
        results["description"] = str(e)

    # 4. Commands
    try:
        await bot.set_my_commands(commands=COMMANDS_EN)
        await bot.set_my_commands(commands=COMMANDS_RU, language_code="ru")
        await bot.set_my_commands(commands=COMMANDS_EN, language_code="en")
        results["commands"] = "ok"
    except Exception as e:
        logger.warning(f"Failed to set bot commands: {e}")
        results["commands"] = str(e)

    # 5. Chat Menu Button (WebApp)
    if settings.WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="CLIN",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL.rstrip("/") + "/"),
                )
            )
            results["menu_button"] = "ok"
        except Exception as e:
            logger.warning(f"Failed to set chat menu button: {e}")
            results["menu_button"] = str(e)

    logger.info(f"Bot profile setup complete: {results}")
    return results


if __name__ == "__main__":
    async def _cli_main():
        if not settings.BOT_TOKEN:
            print("ERROR: BOT_TOKEN is not set.")
            return
        async with Bot(token=settings.BOT_TOKEN) as b:
            res = await setup_bot_profile(b)
            print("Profile setup result:", res)

    asyncio.run(_cli_main())
