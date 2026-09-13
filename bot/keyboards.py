from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import settings
from utils.i18n import t


def get_consent_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Consent gate keyboard for terms and privacy acceptance."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять и продолжить", callback_data="cb:consent_accept")
            ]
        ]
    )


def get_minimal_start_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Minimalist Apple-style launch keyboard with a single prominent Mini App action button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть CLIN",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL),
                )
            ]
        ]
    )


def get_main_menu_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Constructs main menu inline keyboard."""
    buttons = [
        [
            InlineKeyboardButton(
                text="🚀 Открыть Mini App",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        ],
        [
            InlineKeyboardButton(text=t("btn_scan", lang), callback_data="cb:scan"),
            InlineKeyboardButton(text=t("btn_preview", lang), callback_data="cb:preview"),
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
            InlineKeyboardButton(text="💬 Поддержка", callback_data="cb:support_menu"),
        ],
        [
            InlineKeyboardButton(text=t("btn_account", lang), callback_data="cb:account"),
            InlineKeyboardButton(text=t("btn_lang", lang), callback_data="cb:lang_menu"),
            InlineKeyboardButton(text=t("btn_help", lang), callback_data="cb:help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_support_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Support options keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Открыть тикет в Mini App",
                    web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#screen-support"),
                )
            ],
            [
                InlineKeyboardButton(text="🔙 В главное меню", callback_data="cb:main_menu"),
            ],
        ]
    )


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
                        web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#screen-settings"),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📱 Подключить через чат",
                        callback_data="cb:chat_login_start"
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


def get_auth_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cb:auth_cancel")]
        ]
    )


def get_api_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Где взять API ID и API Hash?", callback_data="cb:api_help")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cb:auth_cancel")]
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
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="cb:set_lang:uz"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="cb:main_menu")],
        ]
    )
