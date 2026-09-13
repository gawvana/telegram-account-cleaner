from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import settings
from utils.i18n import t


def get_main_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Constructs main menu inline keyboard matching specification Section 7."""
    buttons = [
        [
            InlineKeyboardButton(text=t("btn_scan", lang), callback_data="cb:scan"),
            InlineKeyboardButton(text=t("btn_preview", lang), callback_data="cb:preview"),
        ],
        [
            InlineKeyboardButton(
                text=t("btn_webapp", lang),
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        ],
        [
            InlineKeyboardButton(text=t("btn_private", lang), callback_data="cb:cat_prompt:PRIVATE"),
            InlineKeyboardButton(text=t("btn_bots", lang), callback_data="cb:cat_prompt:BOT"),
        ],
        [
            InlineKeyboardButton(text=t("btn_groups", lang), callback_data="cb:cat_prompt:GROUP"),
            InlineKeyboardButton(text=t("btn_channels", lang), callback_data="cb:cat_prompt:CHANNEL"),
        ],
        [
            InlineKeyboardButton(text=t("btn_smart_clean", lang), callback_data="cb:smart_clean_prompt"),
        ],
        [
            InlineKeyboardButton(text=t("btn_max_clean", lang), callback_data="cb:max_clean_prompt"),
            InlineKeyboardButton(text=t("btn_schedule", lang), callback_data="cb:schedule"),
        ],
        [
            InlineKeyboardButton(text=t("btn_whitelist", lang), callback_data="cb:whitelist_menu"),
            InlineKeyboardButton(text=t("btn_history", lang), callback_data="cb:history"),
        ],
        [
            InlineKeyboardButton(text=t("btn_hygiene", lang), callback_data="cb:hygiene"),
            InlineKeyboardButton(text=t("btn_export", lang), callback_data="cb:export_menu"),
        ],
        [
            InlineKeyboardButton(text=t("btn_account", lang), callback_data="cb:account"),
            InlineKeyboardButton(text=t("btn_lang", lang), callback_data="cb:lang_menu"),
            InlineKeyboardButton(text=t("btn_help", lang), callback_data="cb:help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_whitelist_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить", callback_data="cb:wl_add"),
                InlineKeyboardButton(text="📋 Список", callback_data="cb:wl_list"),
            ],
            [
                InlineKeyboardButton(text="📤 Экспорт JSON", callback_data="cb:wl_export"),
                InlineKeyboardButton(text="🔙 В главное меню", callback_data="cb:main_menu"),
            ],
        ]
    )


def get_account_keyboard(is_authorized: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    if not is_authorized:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔐 Подключить безопасно (Mini App)",
                        web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#tab-login"),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💬 Подключить через чат (Fallback)",
                        callback_data="cb:chat_login_start",
                    )
                ],
                [InlineKeyboardButton(text=t("btn_back", lang), callback_data="cb:main_menu")],
            ]
        )
    else:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚪 Завершить сессию (Logout)", callback_data="cb:logout")],
                [InlineKeyboardButton(text=t("btn_back", lang), callback_data="cb:main_menu")],
            ]
        )


def get_category_confirm_keyboard(cat_name: str, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⚠️ Очистить {cat_name}", callback_data=f"cb:cat_run:{cat_name}"
                )
            ],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cb:main_menu")],
        ]
    )


def get_smart_clean_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Запустить Smart Clean", callback_data="cb:smart_clean_run")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cb:main_menu")],
        ]
    )


def get_max_clean_confirm_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cb:main_menu")],
        ]
    )


def get_running_job_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛔ Остановить процесс", callback_data="cb:stop_job")],
        ]
    )


def get_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="cb:set_lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="cb:set_lang:en"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="cb:main_menu")],
        ]
    )
