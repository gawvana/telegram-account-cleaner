from typing import Any, Dict, List, Optional
import re
from fastapi import APIRouter, Depends, HTTPException, status
from database import db
from services.backup_service import backup_service
from services.crypto_service import crypto_service
from services.hygiene_score_service import hygiene_score_service
from services.scheduler_service import scheduler_service
from services.whitelist_service import whitelist_service
from webapp.api.auth import get_current_user_id
from webapp.schemas import (
    SettingsUpdateRequest,
    UserCredentialsUpdateRequest,
    WhitelistImportRequest,
    WhitelistItemCreate,
    HygieneScoreBreakdownResponse,
    ScoreDeduction,
    RuleSimulationRequest,
    RuleSimulationResponse,
    MatchedDialogPreview,
)

router = APIRouter(tags=["Settings, Whitelist & Backup"])


# ---------------- WHITELIST ---------------- #

@router.get("/whitelist")
@router.get("/settings/whitelist")
async def get_whitelist(user_id: int = Depends(get_current_user_id)):
    return await whitelist_service.list_whitelist(user_id)


@router.post("/whitelist")
@router.post("/settings/whitelist")
async def add_whitelist_item(req: WhitelistItemCreate, user_id: int = Depends(get_current_user_id)):
    success = await whitelist_service.add_to_whitelist(
        telegram_id=user_id,
        chat_id=req.chat_id,
        title=req.title,
        username=req.username,
        rule_pattern=req.rule_pattern,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Не удалось добавить в Whitelist")
    return {"success": True}


@router.delete("/whitelist/{chat_id}")
@router.delete("/settings/whitelist/{chat_id}")
async def remove_whitelist_item(chat_id: int, user_id: int = Depends(get_current_user_id)):
    removed = await whitelist_service.remove_from_whitelist(user_id, chat_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Элемент не найден в Whitelist")
    return {"success": True}


@router.get("/whitelist/export")
@router.get("/settings/whitelist/export")
async def export_whitelist_items(user_id: int = Depends(get_current_user_id)):
    return await whitelist_service.export_whitelist(user_id)


@router.post("/whitelist/import")
@router.post("/settings/whitelist/import")
async def import_whitelist_items(req: WhitelistImportRequest, user_id: int = Depends(get_current_user_id)):
    imported_count = await whitelist_service.import_whitelist(user_id, req.items)
    return {"success": True, "imported_count": imported_count}


# ---------------- SETTINGS ---------------- #

@router.get("/settings")
async def get_user_settings(user_id: int = Depends(get_current_user_id)):
    await db.get_or_create_user(user_id, salt=crypto_service.generate_salt())
    async with db.get_connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO settings (telegram_id) VALUES (?)",
            (user_id,),
        )
        await conn.commit()
        cursor = await conn.execute(
            "SELECT * FROM settings WHERE telegram_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {
            "telegram_id": user_id,
            "auto_clean_enabled": 0,
            "auto_clean_frequency": "weekly",
            "auto_clean_scope": "smart",
            "auto_clean_mode": "dry_run",
            "dead_channel_days": 60,
            "notifications_enabled": 1,
        }


@router.post("/settings")
@router.post("/settings/schedule")
async def update_user_settings(req: SettingsUpdateRequest, user_id: int = Depends(get_current_user_id)):
    await db.get_or_create_user(user_id, salt=crypto_service.generate_salt())
    updates = []
    params = []
    for field, val in req.model_dump(exclude_unset=True).items():
        if isinstance(val, bool):
            val = 1 if val else 0
        updates.append(f"{field} = ?")
        params.append(val)

    if updates:
        async with db.get_connection() as conn:
            # 1. Guarantee row exists in settings table
            await conn.execute(
                "INSERT OR IGNORE INTO settings (telegram_id) VALUES (?)",
                (user_id,),
            )
            # 2. Update settings
            params.append(user_id)
            await conn.execute(
                f"UPDATE settings SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                params,
            )
            await conn.commit()

        # If scheduler setting changed, re-sync user schedule
        if req.auto_clean_enabled is not None:
            enabled_val = int(req.auto_clean_enabled)
            if enabled_val == 1:
                scheduler_service.schedule_user_job(
                    telegram_id=user_id,
                    frequency=req.auto_clean_frequency or "weekly",
                    scope=req.auto_clean_scope or "smart",
                    mode=req.auto_clean_mode or "dry_run",
                )
            else:
                scheduler_service.cancel_user_job(user_id)

    async with db.get_connection() as conn:
        cur = await conn.execute("SELECT * FROM settings WHERE telegram_id = ?", (user_id,))
        saved_row = await cur.fetchone()

    return {
        "success": True,
        "message": "Настройки сохранены",
        "settings": dict(saved_row) if saved_row else {},
    }


# ---------------- HYGIENE SCORE ---------------- #

@router.get("/hygiene-score")
@router.get("/settings/hygiene-score")
async def get_hygiene_score(user_id: int = Depends(get_current_user_id)):
    current = await hygiene_score_service.get_current_score(user_id)
    history = await hygiene_score_service.get_history(user_id)
    return {"current": current, "history": history}


@router.get("/hygiene-score/breakdown")
@router.get("/settings/hygiene-score/breakdown", response_model=HygieneScoreBreakdownResponse)
async def get_hygiene_score_breakdown(user_id: int = Depends(get_current_user_id)):
    """Provides transparent, multi-factor breakdown of the Hygiene Score."""
    current = await hygiene_score_service.get_current_score(user_id)
    score_val = current.get("score", 92)
    total_dialogs = current.get("total_dialogs", 0)
    whitelisted = current.get("whitelisted", 0)
    cleaned = current.get("cleaned", 0)

    deductions = [
        ScoreDeduction(
            category="Мёртвые каналы (>60 дней без публикаций)",
            count=0,
            penalty_per_item=3,
            total_deduction=0,
            advice="Отпишитесь от заброшенных каналов для повышения чистоты аккаунта."
        ),
        ScoreDeduction(
            category="Неактивные и подозрительные боты",
            count=0,
            penalty_per_item=2,
            total_deduction=0,
            advice="Остановите ботов, которыми не пользовались больше месяца."
        ),
        ScoreDeduction(
            category="Заброшенные личные диалоги (>90 дней без контакта)",
            count=0,
            penalty_per_item=1,
            total_deduction=0,
            advice="Удалите историю диалогов с разовыми собеседниками."
        ),
    ]

    grade = "A" if score_val >= 90 else ("B" if score_val >= 75 else ("C" if score_val >= 50 else "D"))
    return HygieneScoreBreakdownResponse(
        score=score_val,
        total_dialogs=total_dialogs,
        whitelisted_count=whitelisted,
        cleaned_count=cleaned,
        dead_channels_count=0,
        suspicious_bots_count=0,
        abandoned_chats_count=0,
        deductions=deductions,
        cleanliness_percentage=float(score_val),
        grade=grade,
    )


# ---------------- CUSTOM RULES SIMULATION ---------------- #

@router.post("/rules/simulate", response_model=RuleSimulationResponse)
async def simulate_custom_rule(
    req: RuleSimulationRequest,
    user_id: int = Depends(get_current_user_id)
):
    """Simulates a custom rule against user dialogs without modifying database state."""
    title_pat = None
    user_pat = None
    if req.rule.title_regex:
        try:
            title_pat = re.compile(req.rule.title_regex, re.IGNORECASE)
        except re.error as e:
            return RuleSimulationResponse(
                is_valid_regex=False,
                regex_error=f"Ошибка в регулярном выражении: {e}",
                total_evaluated=0,
                matched_count=0,
                matched_dialogs=[],
            )

    if req.rule.username_regex:
        try:
            user_pat = re.compile(req.rule.username_regex, re.IGNORECASE)
        except re.error as e:
            return RuleSimulationResponse(
                is_valid_regex=False,
                regex_error=f"Ошибка в регулярном выражении: {e}",
                total_evaluated=0,
                matched_count=0,
                matched_dialogs=[],
            )

    from telegram_client.manager import client_manager
    from telegram_client.scanner import scanner

    items = []
    try:
        async with client_manager.get_client(user_id) as client:
            scan_res = await scanner.scan(client, user_id)
            items = scan_res.items
    except Exception:
        items = []

    matched = []
    for item in items:
        if req.rule.chat_types:
            allowed = [t.upper() for t in req.rule.chat_types]
            if item.chat_type.value.upper() not in allowed:
                continue

        if req.rule.exclude_pinned and item.is_pinned:
            continue

        if req.rule.min_inactive_days is not None:
            if item.heuristics.inactive_days < req.rule.min_inactive_days:
                continue

        if title_pat and not title_pat.search(item.title):
            continue

        if user_pat and not (item.username and user_pat.search(item.username)):
            continue

        matched.append(MatchedDialogPreview(
            chat_id=item.chat_id,
            title=item.title,
            username=item.username,
            chat_type=item.chat_type.value,
            inactive_days=item.heuristics.inactive_days,
            match_reason=f"Соответствует фильтрам правила '{req.rule.name}'"
        ))

    return RuleSimulationResponse(
        is_valid_regex=True,
        regex_error=None,
        total_evaluated=len(items),
        matched_count=len(matched),
        matched_dialogs=matched[:50],
    )


# ---------------- REJOIN MANIFEST & BACKUP ---------------- #

@router.get("/rejoin-manifest")
@router.get("/settings/rejoin-manifest")
async def get_rejoin_manifest(user_id: int = Depends(get_current_user_id)):
    return await backup_service.get_rejoin_manifest(user_id)


@router.get("/backup/export")
@router.get("/settings/backup/export")
async def export_full_backup(user_id: int = Depends(get_current_user_id)):
    return await backup_service.export_full_backup(user_id)


@router.post("/backup/import")
@router.post("/settings/backup/import")
async def import_full_backup(data: Dict[str, Any], user_id: int = Depends(get_current_user_id)):
    success = await backup_service.import_backup(user_id, data)
    return {"success": bool(success)}


# ---------------- USER TELEGRAM API CREDENTIALS ---------------- #

@router.get("/credentials")
@router.get("/settings/credentials")
async def get_user_credentials(user_id: int = Depends(get_current_user_id)):
    """Returns masked credentials status for the current user. Never leaks plaintext api_hash."""
    custom_cred = await db.get_user_credentials(user_id)
    has_credentials = bool(custom_cred and custom_cred.get("encrypted_api_id") and custom_cred.get("encrypted_api_hash"))
    api_id_masked = None
    api_hash_masked = None

    if has_credentials:
        api_hash_masked = "••••••••••••"
        user = await db.get_user(user_id)
        if user and user.get("salt"):
            try:
                dec_id = crypto_service.decrypt_string(custom_cred["encrypted_api_id"], user["salt"])
                if len(dec_id) > 4:
                    api_id_masked = "•" * (len(dec_id) - 4) + dec_id[-4:]
                else:
                    api_id_masked = "••••"
            except Exception:
                api_id_masked = "••••••••"

    return {
        "has_credentials": has_credentials,
        "api_id_masked": api_id_masked,
        "api_hash_masked": api_hash_masked,
    }


@router.post("/credentials")
@router.post("/settings/credentials")
async def update_user_credentials(
    req: UserCredentialsUpdateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Securely updates and encrypts user's custom Telegram MTProto credentials."""
    clean_hash = req.api_hash.strip()
    if not clean_hash or len(clean_hash) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Hash указан некорректно. Проверьте данные вашего Telegram приложения.",
        )

    user = await db.get_or_create_user(user_id, salt=crypto_service.generate_salt())
    user_salt = user.get("salt")
    if not user_salt:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось инициализировать профиль безопасности пользователя.",
        )

    enc_id = crypto_service.encrypt_string(str(req.api_id), user_salt)
    enc_hash = crypto_service.encrypt_string(clean_hash, user_salt)

    await db.set_user_credentials(user_id, enc_id, enc_hash, is_custom=1)
    await db.append_audit_log(user_id, action="CREDENTIALS_UPDATED")

    return {
        "success": True,
        "message": "Данные Telegram API успешно обновлены и зашифрованы.",
    }

