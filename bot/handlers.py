import asyncio
from pathlib import Path
from typing import Optional
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, Message

from bot.filters import UserContextFilter
from bot.keyboards import (
    get_account_keyboard,
    get_category_confirm_keyboard,
    get_consent_keyboard,
    get_lang_keyboard,
    get_main_menu_keyboard,
    get_max_clean_confirm_keyboard,
    get_minimal_start_keyboard,
    get_running_job_keyboard,
    get_smart_clean_keyboard,
    get_support_keyboard,
    get_whitelist_keyboard,
)
from bot.states import AuthStates, ConfirmStates, WhitelistStates
from config import settings
from database import db
from services.backup_service import backup_service
from services.cleanup_service import cleanup_service
from services.consent_service import consent_service
from services.crypto_service import crypto_service
from services.hygiene_score_service import hygiene_score_service
from services.preview_service import preview_service
from services.statistics_service import statistics_service
from services.support_service import support_service
from services.whitelist_service import whitelist_service
from telegram_client.auth import auth_manager
from telegram_client.manager import client_manager
from telegram_client.models import ChatType, CleanupPlan
from telegram_client.scanner import scanner
from utils.helpers import mask_phone, safe_json_dumps
from utils.i18n import t
from utils.logger import logger
from utils.progress import ProgressTracker

router = Router()
router.message.filter(UserContextFilter())
router.callback_query.filter(UserContextFilter())


async def _get_user_lang(telegram_id: int) -> str:
    user = await db.get_or_create_user(telegram_id, salt=crypto_service.generate_salt())
    return user.get("language") or "ru"


# ---------------- START VIDEO HELPER ---------------- #

_cached_video_file_id: Optional[str] = None


async def _send_start_video_message(
    message: Message,
    caption: str,
    reply_markup=None,
    parse_mode: str = "Markdown",
) -> Message:
    """Sends start video with text caption, auto-caching file_id for instant subsequent deliveries."""
    global _cached_video_file_id

    # 1. Try file_id from settings or cache
    file_id = settings.START_VIDEO_FILE_ID or _cached_video_file_id
    if file_id:
        try:
            return await message.answer_video(
                video=file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        except Exception as e:
            logger.warning(f"Failed to send video using file_id ({file_id}): {e}")

    # 2. Try local video file
    video_path = Path(settings.START_VIDEO_PATH)
    if not video_path.is_absolute():
        video_path = Path(__file__).resolve().parent.parent / video_path

    if video_path.exists():
        try:
            sent_msg = await message.answer_video(
                video=FSInputFile(str(video_path)),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            if sent_msg.video and sent_msg.video.file_id:
                _cached_video_file_id = sent_msg.video.file_id
                logger.info(f"Cached start video file_id: {_cached_video_file_id}")
            return sent_msg
        except Exception as e:
            logger.warning(f"Failed to send start video from path ({video_path}): {e}")

    # 3. Fallback to standard text answer if video is unavailable
    return await message.answer(
        text=caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


# ---------------- COMMANDS ---------------- #

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await _get_user_lang(message.from_user.id)
    has_consent = await consent_service.has_valid_consent(message.from_user.id)
    if not has_consent:
        if lang == "uz":
            consent_text = (
                "⚖️ **CLIN — Telegram Account Cleaner**\n\n"
                "Ishni boshlashdan oldin xizmat ko'rsatish qoidalari va maxfiylik siyosati bilan tanishing:\n\n"
                "1. **Xavfsizlik**: Sessiya ma'lumotlari mahalliy ravishda AES-128 (Fernet) bilan shifrlanadi. Parollar va kodlar ochiq holda saqlanmaydi.\n"
                "2. **Nazorat**: O'chiriladigan har qanday dialog sizning tasdiqlashingizni talab qiladi. Oq ro'yxatdagi chatlar hech qachon o'chirilmaydi.\n"
                "3. **Rozilikni bekor qilish**: Istalgan vaqtda rozilikni bekor qilib, barcha ma'lumotlarni o'chirishingiz mumkin.\n\n"
                "«Qabul qilish va davom etish» tugmasini bosish orqali qoidalarga rozilik bildirasiz."
            )
        elif lang == "en":
            consent_text = (
                "⚖️ **CLIN — Telegram Account Cleaner**\n\n"
                "Before proceeding, please review and accept our Terms of Service & Privacy Policy:\n\n"
                "1. **Security**: Your session data is encrypted locally using AES-128 (Fernet). Plaintext passwords or auth codes are never stored.\n"
                "2. **User Control**: Every destructive action requires explicit confirmation. Whitelisted chats are strictly preserved.\n"
                "3. **Revocation**: You can withdraw consent and instantly shred your session at any time.\n\n"
                "By clicking 'Accept & Continue', you agree to CLIN terms."
            )
        else:
            consent_text = (
                "⚖️ **CLIN — Telegram Account Cleaner**\n\n"
                "Перед началом работы, пожалуйста, ознакомьтесь с правилами использования и политикой конфиденциальности:\n\n"
                "1. **Безопасность**: Ваши данные сессии шифруются локально алгоритмом AES-128 (Fernet). Пароли и коды никогда не сохраняются в открытом виде.\n"
                "2. **Контроль**: Любые удаляемые диалоги требуют вашего подтверждения. Чаты из белого списка никогда не удаляются.\n"
                "3. **Отзыв согласия**: Вы можете отозвать согласие и мгновенно стереть сессию в любой момент в Настройках.\n\n"
                "Нажимая «Принять и продолжить», вы соглашаетесь с условиями сервиса."
            )
        await _send_start_video_message(message, caption=consent_text, reply_markup=get_consent_keyboard(lang))
        return

    await _send_start_video_message(
        message,
        caption=t("welcome_minimal", lang),
        reply_markup=get_minimal_start_keyboard(lang),
    )


@router.callback_query(F.data == "cb:consent_accept")
async def cb_consent_accept(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    await consent_service.record_user_consent(call.from_user.id)
    await call.answer("✅ Согласие принято!" if lang == "ru" else "✅ Consent accepted!")
    if call.message:
        if call.message.caption is not None:
            await call.message.edit_caption(
                caption=t("welcome_minimal", lang),
                reply_markup=get_minimal_start_keyboard(lang),
            )
        else:
            await call.message.edit_text(
                text=t("welcome_minimal", lang),
                reply_markup=get_minimal_start_keyboard(lang),
            )


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    await message.answer(t("welcome_minimal", lang), reply_markup=get_minimal_start_keyboard(lang))


@router.message(Command("support"))
async def cmd_support(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    text = (
        "💬 **Служба поддержки CLIN**\n\n"
        "Возникли сложности или нашли баг? Откройте раздел поддержки в Mini App, чтобы создать тикет с номером `CLIN-XXXXX`.\n\n"
        "⚠️ **Безопасность**: Служба поддержки CLIN никогда не запрашивает API Hash, Telegram код, 2FA-пароль или session string!"
    )
    await message.answer(text, reply_markup=get_support_keyboard(lang))


@router.message(Command("scan"))
async def cmd_scan(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    await message.answer("🔍 **Сканирование диалогов**\nЗапустите сканирование в Mini App для подробного анализа:", reply_markup=get_minimal_start_keyboard(lang))


@router.message(Command("clean"))
async def cmd_clean(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    await message.answer("🧹 **Очистка аккаунта CLIN**\nОткройте Mini App для выбора категорий и умной очистки:", reply_markup=get_minimal_start_keyboard(lang))


@router.message(Command("history"))
async def cmd_history_command(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    stats = await statistics_service.get_user_statistics(message.from_user.id)
    summary = stats.get("summary") or {}
    text = (
        f"📊 **История очисток CLIN**\n\n"
        f"Всего запусков: `{summary.get('total_jobs', 0)}`\n"
        f"Обработано: `{summary.get('total_processed', 0)}`\n"
        f"Пропущено (Whitelist): `{summary.get('total_skipped', 0)}`\n"
        f"Ошибок: `{summary.get('total_errors', 0)}`"
    )
    await message.answer(text, reply_markup=get_minimal_start_keyboard(lang))


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await cmd_account(message)


@router.message(Command("account"))
async def cmd_account(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    user_id = message.from_user.id
    is_auth = await client_manager.has_active_session(user_id)
    score_data = await hygiene_score_service.get_current_score(user_id)

    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT phone FROM users WHERE telegram_id = ?", (user_id,))
        row = await cursor.fetchone()
        phone = mask_phone(row["phone"]) if row and row["phone"] else "—"

    if is_auth:
        text = t("account_connected", lang, phone=phone, score=score_data["score"])
    else:
        text = t("account_not_connected", lang)

    await message.answer(text, reply_markup=get_account_keyboard(is_auth, lang))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    stopped = await cleanup_service.stop_cleanup(message.from_user.id)
    lang = await _get_user_lang(message.from_user.id)
    if stopped:
        await message.answer("🛑 Выполнявшаяся задача остановлена.", reply_markup=get_main_menu_keyboard(lang))
    else:
        await message.answer("Действие отменено.", reply_markup=get_main_menu_keyboard(lang))


@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT * FROM settings WHERE telegram_id = ?", (message.from_user.id,))
        row = await cursor.fetchone()
        s = dict(row) if row else {}

    status_str = "🟢 Включена" if s.get("auto_clean_enabled") else "⚪ Выключена"
    mode_str = "🧪 Dry-run (отчёт)" if s.get("auto_clean_mode") != "auto" else "⚠️ Авто-удаление"
    freq = s.get("auto_clean_frequency", "weekly")

    text = (
        "📅 **АВТООЧИСТКА ПО РАСПИСАНИЮ**\n\n"
        f"Статус: {status_str}\n"
        f"Частота: `{freq}`\n"
        f"Режим: `{mode_str}`\n\n"
        "💡 _Настроить расписание можно в Telegram Mini App._"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(lang))


@router.message(Command("export"))
async def cmd_export(message: Message):
    lang = await _get_user_lang(message.from_user.id)
    backup_data = await backup_service.export_full_backup(message.from_user.id)
    json_bytes = safe_json_dumps(backup_data).encode("utf-8")
    doc = BufferedInputFile(json_bytes, filename=f"cleaner_export_{message.from_user.id}.json")
    await message.answer_document(doc, caption="📤 **Экспорт данных пользователя**\n(Whitelist, настройки, история, Rejoin Manifest)")


@router.message(Command("lang"))
async def cmd_lang(message: Message):
    await message.answer("🌐 Выберите язык / Select language:", reply_markup=get_lang_keyboard())


# ---------------- NAVIGATION CALLBACKS ---------------- #

@router.callback_query(F.data == "cb:main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await _get_user_lang(call.from_user.id)
    await call.message.edit_text(t("main_menu_title", lang), reply_markup=get_main_menu_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:help")
async def cb_help(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    await call.message.edit_text(t("help_text", lang), reply_markup=get_main_menu_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:support_menu")
async def cb_support_menu(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    text = (
        "💬 **Служба поддержки CLIN**\n\n"
        "Вы можете отправить тикет, просмотреть историю обращений и ответы администраторов в Mini App.\n\n"
        "⚠️ **Безопасность**: Никогда не сообщайте коды авторизации или пароли!"
    )
    await call.message.edit_text(text, reply_markup=get_support_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:account")
async def cb_account(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    user_id = call.from_user.id
    is_auth = await client_manager.has_active_session(user_id)
    score_data = await hygiene_score_service.get_current_score(user_id)

    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT phone FROM users WHERE telegram_id = ?", (user_id,))
        row = await cursor.fetchone()
        phone = mask_phone(row["phone"]) if row and row["phone"] else "—"

    if is_auth:
        text = t("account_connected", lang, phone=phone, score=score_data["score"])
    else:
        text = t("account_not_connected", lang)

    await call.message.edit_text(text, reply_markup=get_account_keyboard(is_auth, lang))
    await call.answer()


@router.callback_query(F.data == "cb:lang_menu")
async def cb_lang_menu(call: CallbackQuery):
    await call.message.edit_text("🌐 Выберите язык / Select language:", reply_markup=get_lang_keyboard())
    await call.answer()


@router.callback_query(F.data.startswith("cb:set_lang:"))
async def cb_set_lang(call: CallbackQuery):
    lang = call.data.split(":")[-1]
    await db.update_user_language(call.from_user.id, lang)
    await call.answer(f"Language set: {lang.upper()}")
    await call.message.edit_text(t("main_menu_title", lang), reply_markup=get_main_menu_keyboard(lang))


# ---------------- SCAN & PREVIEW ---------------- #

@router.callback_query(F.data.in_(["cb:scan", "cb:preview"]))
async def cb_scan_and_preview(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    user_id = call.from_user.id

    if not await client_manager.has_active_session(user_id):
        await call.answer("Аккаунт не подключён!", show_alert=True)
        return

    status_msg = await call.message.edit_text("⏳ **Сканирование диалогов...**\nПожалуйста, подождите...")
    await call.answer()

    try:
        async with client_manager.get_client(user_id) as client:
            scan_res = await scanner.scan(client, user_id)
            preview_text = preview_service.format_bot_preview(scan_res)
            await status_msg.edit_text(preview_text, reply_markup=get_main_menu_keyboard(lang))
    except Exception as e:
        logger.error(f"Error scanning for {user_id}: {e}")
        await status_msg.edit_text(
            f"❌ Ошибка сканирования: {str(e)}", reply_markup=get_main_menu_keyboard(lang)
        )


# ---------------- HYGIENE & HISTORY ---------------- #

@router.callback_query(F.data == "cb:hygiene")
async def cb_hygiene(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    score_data = await hygiene_score_service.get_current_score(call.from_user.id)
    text = (
        f"🏆 **ACCOUNT HYGIENE SCORE: {score_data['score']}/100**\n\n"
        f"📊 Всего диалогов: `{score_data['total_dialogs']}`\n"
        f"⭐ В белом списке: `{score_data['whitelisted']}`\n"
        f"🧹 Очищено объектов: `{score_data['cleaned']}`\n\n"
        "💡 _Формула прозрачна: оценивает долю защищённых и вовремя очищенных диалогов без давления на пользователя._"
    )
    await call.message.edit_text(text, reply_markup=get_main_menu_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:history")
async def cb_history(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    stats = await statistics_service.get_user_statistics(call.from_user.id)
    summary = stats.get("summary") or {}
    jobs = stats.get("recent_jobs") or []

    lines = [
        "📊 **ИСТОРИЯ ОЧИСТОК**\n",
        f"Всего запусков: `{summary.get('total_jobs', 0)}`",
        f"Успешно обработано: `{summary.get('total_processed', 0)}`",
        f"Пропущено (Whitelist): `{summary.get('total_skipped', 0)}`",
        f"Ошибок: `{summary.get('total_errors', 0)}`\n",
        "**Последние операции:**",
    ]

    for j in jobs[:5]:
        status_icon = "✅" if j["status"] == "COMPLETED" else "❌"
        lines.append(f"{status_icon} `{j['job_type']}` — {j['processed_items']}/{j['total_items']} ({j['status']})")

    await call.message.edit_text("\n".join(lines), reply_markup=get_main_menu_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:export_menu")
async def cb_export_menu(call: CallbackQuery):
    await call.answer()
    backup_data = await backup_service.export_full_backup(call.from_user.id)
    json_bytes = safe_json_dumps(backup_data).encode("utf-8")
    doc = BufferedInputFile(json_bytes, filename=f"cleaner_export_{call.from_user.id}.json")
    await call.message.answer_document(doc, caption="📤 **Экспорт данных пользователя**")


# ---------------- WHITELIST MENU ---------------- #

@router.callback_query(F.data == "cb:whitelist_menu")
async def cb_whitelist_menu(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    items = await whitelist_service.list_whitelist(call.from_user.id)
    text = (
        f"⭐ **БЕЛЫЙ СПИСОК (WHITELIST)**\n\n"
        f"Защищённых объектов: `{len(items)}`\n\n"
        "Объекты из белого списка никогда не удаляются и не покидаются программой."
    )
    await call.message.edit_text(text, reply_markup=get_whitelist_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:wl_list")
async def cb_wl_list(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    items = await whitelist_service.list_whitelist(call.from_user.id)
    if not items:
        await call.message.edit_text("⭐ Белый список пуст.", reply_markup=get_whitelist_keyboard(lang))
        await call.answer()
        return

    lines = ["⭐ **СПИСОК WHITELIST:**\n"]
    for idx, it in enumerate(items[:25], 1):
        title = it.get("title") or "Без названия"
        username = f" (@{it['username']})" if it.get("username") else ""
        lines.append(f"{idx}. `{it['chat_id']}` — **{title}**{username}")

    await call.message.edit_text("\n".join(lines), reply_markup=get_whitelist_keyboard(lang))
    await call.answer()


@router.callback_query(F.data == "cb:wl_add")
async def cb_wl_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(WhitelistStates.waiting_chat_input)
    await call.message.edit_text(
        "➕ **Добавление в Whitelist**\n\nОтправьте в ответ числовой Chat ID (например `-100123456789`) или `@username` канала/бота:"
    )
    await call.answer()


@router.message(WhitelistStates.waiting_chat_input)
async def process_wl_chat_input(message: Message, state: FSMContext):
    await state.clear()
    raw = message.text.strip()
    lang = await _get_user_lang(message.from_user.id)

    try:
        chat_id = int(raw)
        await whitelist_service.add_to_whitelist(message.from_user.id, chat_id=chat_id, title=f"Chat {chat_id}")
        await message.answer(f"✅ Чат `{chat_id}` добавлен в Whitelist.", reply_markup=get_whitelist_keyboard(lang))
    except ValueError:
        await message.answer("❌ Неверный формат ID. Требуется числовой идентификатор.", reply_markup=get_whitelist_keyboard(lang))


# ---------------- CATEGORY CLEANUPS ---------------- #

@router.callback_query(F.data.startswith("cb:cat_prompt:"))
async def cb_category_prompt(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    cat_type = call.data.split(":")[-1]
    name_map = {
        "PRIVATE": "личных диалогов",
        "BOT": "диалогов с ботами",
        "GROUP": "групп",
        "CHANNEL": "каналов",
    }
    cat_name = name_map.get(cat_type, cat_type)
    text = (
        f"⚠️ **ПОДТВЕРЖДЕНИЕ ОЧИСТКИ**\n\n"
        f"Вы собираетесь запустить очистку категории: **{cat_name}**.\n\n"
        "⭐ Элементы из Whitelist будут пропущены.\n"
        "Продолжить?"
    )
    await call.message.edit_text(text, reply_markup=get_category_confirm_keyboard(cat_type, lang))
    await call.answer()


@router.callback_query(F.data.startswith("cb:cat_run:"))
async def cb_category_run(call: CallbackQuery):
    cat_type = call.data.split(":")[-1]
    lang = await _get_user_lang(call.from_user.id)
    user_id = call.from_user.id

    plan = CleanupPlan(target_types=[ChatType(cat_type)])
    await _execute_bot_cleanup(call.message, user_id, plan, lang)
    await call.answer()


# ---------------- SMART CLEAN ---------------- #

@router.callback_query(F.data == "cb:smart_clean_prompt")
async def cb_smart_clean_prompt(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    user_id = call.from_user.id

    if not await client_manager.has_active_session(user_id):
        await call.answer("Аккаунт не подключён!", show_alert=True)
        return

    status_msg = await call.message.edit_text("⏳ **Анализ рекомендаций...**")
    await call.answer()

    try:
        async with client_manager.get_client(user_id) as client:
            scan = await scanner.scan(client, user_id)
            recs_text = preview_service.format_recommendations_text(scan)
            await status_msg.edit_text(
                f"{recs_text}\n\nЗапустить очистку рекомендованных элементов?",
                reply_markup=get_smart_clean_keyboard(lang),
            )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}", reply_markup=get_main_menu_keyboard(lang))


@router.callback_query(F.data == "cb:smart_clean_run")
async def cb_smart_clean_run(call: CallbackQuery):
    lang = await _get_user_lang(call.from_user.id)
    plan = CleanupPlan(is_smart_clean=True)
    await _execute_bot_cleanup(call.message, call.from_user.id, plan, lang)
    await call.answer()


# ---------------- MAX CLEAN (TWO-STEP CONFIRMATION) ---------------- #

@router.callback_query(F.data == "cb:max_clean_prompt")
async def cb_max_clean_prompt(call: CallbackQuery, state: FSMContext):
    lang = await _get_user_lang(call.from_user.id)
    await state.set_state(ConfirmStates.waiting_max_clean_confirm)
    await call.message.edit_text(
        t("confirm_max_clean_warning", lang),
        reply_markup=get_max_clean_confirm_keyboard(lang),
    )
    await call.answer()


@router.message(ConfirmStates.waiting_max_clean_confirm)
async def process_max_clean_confirmation(message: Message, state: FSMContext):
    await state.clear()
    lang = await _get_user_lang(message.from_user.id)

    if message.text.strip().upper() == "MAX CLEAN":
        plan = CleanupPlan(is_max_clean=True)
        await _execute_bot_cleanup(message, message.from_user.id, plan, lang)
    else:
        await message.answer(
            "❌ Подтверждение не совпадает. Операция MAX CLEAN отменена.",
            reply_markup=get_main_menu_keyboard(lang),
        )


# ---------------- EXECUTION RUNNER WITH THROTTLED PROGRESS ---------------- #

async def _execute_bot_cleanup(msg_target: Message, user_id: int, plan: CleanupPlan, lang: str):
    progress_msg = await msg_target.answer("🚀 **Подготовка к очистке...**")

    async def _on_progress_update(tracker: ProgressTracker):
        try:
            await progress_msg.edit_text(
                tracker.render_telegram_text(),
                reply_markup=get_running_job_keyboard(lang),
            )
        except Exception:
            pass

    try:
        res = await cleanup_service.run_cleanup(
            telegram_id=user_id,
            plan=plan,
            progress_callback=_on_progress_update,
        )

        final_text = (
            f"{t('clean_completed', lang)}\n\n"
            f"📊 Всего обработано: `{res['processed']}`\n"
            f"✅ Успешно: `{res['success']}`\n"
            f"⏭ Пропущено (Whitelist): `{res['skipped']}`\n"
            f"❌ Ошибок: `{res['errors']}`\n"
            f"⏱ Время выполнения: `{res['duration']}`\n\n"
            f"📎 Rejoin Manifest сохранён в экспорт данных."
        )
        await progress_msg.edit_text(final_text, reply_markup=get_main_menu_keyboard(lang))

    except Exception as e:
        logger.error(f"Cleanup runner failed for {user_id}: {e}")
        await progress_msg.edit_text(
            f"❌ Ошибка выполнения: {str(e)}", reply_markup=get_main_menu_keyboard(lang)
        )


@router.callback_query(F.data == "cb:stop_job")
async def cb_stop_job(call: CallbackQuery):
    stopped = await cleanup_service.stop_cleanup(call.from_user.id)
    if stopped:
        await call.answer("🛑 Сигнал остановки отправлен. Завершение текущего шага...", show_alert=True)
    else:
        await call.answer("Нет активной задачи.", show_alert=True)


# ---------------- SECURE LOGIN VIA CHAT (FALLBACK) ---------------- #

@router.callback_query(F.data == "cb:chat_login_start")
async def cb_chat_login_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AuthStates.waiting_phone)
    await call.message.edit_text(
        "📱 **Подключение через чат (Fallback)**\n\n"
        "Отправьте ваш номер телефона в международном формате (например `+79991234567`):\n\n"
        "💡 _Для большей приватности рекомендуется использовать кнопку Mini App, где код не сохраняется в чате._"
    )
    await call.answer()


@router.message(AuthStates.waiting_phone)
async def process_chat_login_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    user_id = message.from_user.id
    try:
        auth_state = await auth_manager.request_phone_code(user_id, phone)
        await state.set_state(AuthStates.waiting_code)
        await message.answer("📩 Код подтверждения отправлен в ваш Telegram. Введите полученный код:")
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(AuthStates.waiting_code)
async def process_chat_login_code(message: Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id

    # Security: immediately delete message with code from chat history!
    try:
        await message.delete()
    except Exception:
        pass

    try:
        auth_state, session_file = await auth_manager.submit_auth_code(user_id, code)
        if auth_state.is_authorized:
            await state.clear()
            lang = await _get_user_lang(user_id)
            await message.answer("🟢 **Аккаунт успешно подключён!**", reply_markup=get_main_menu_keyboard(lang))
        elif auth_state.step == "2FA":
            await state.set_state(AuthStates.waiting_2fa)
            await message.answer("🔐 Введите ваш облачный 2FA пароль:")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(AuthStates.waiting_2fa)
async def process_chat_login_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    user_id = message.from_user.id

    # Security: immediately delete password message!
    try:
        await message.delete()
    except Exception:
        pass

    try:
        auth_state, session_file = await auth_manager.submit_2fa_password(user_id, password)
        await state.clear()
        lang = await _get_user_lang(user_id)
        await message.answer("🟢 **Аккаунт успешно подключён!**", reply_markup=get_main_menu_keyboard(lang))
    except Exception as e:
        await message.answer(f"❌ Ошибка 2FA: {str(e)}")


@router.callback_query(F.data == "cb:logout")
async def cb_logout(call: CallbackQuery):
    await client_manager.logout_user(call.from_user.id)
    lang = await _get_user_lang(call.from_user.id)
    await call.message.edit_text("🚪 Сессия успешно завершена и стёрта.", reply_markup=get_main_menu_keyboard(lang))
    await call.answer()
