from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from database import db
from services.backup_service import backup_service
from services.hygiene_score_service import hygiene_score_service
from services.scheduler_service import scheduler_service
from services.whitelist_service import whitelist_service
from webapp.api.auth import get_current_user_id
from webapp.schemas import (
    SettingsUpdateRequest,
    WhitelistImportRequest,
    WhitelistItemCreate,
)

router = APIRouter(tags=["Settings, Whitelist & Backup"])


# ---------------- WHITELIST ---------------- #

@router.get("/whitelist")
async def get_whitelist(user_id: int = Depends(get_current_user_id)):
    return await whitelist_service.list_whitelist(user_id)


@router.post("/whitelist")
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
async def remove_whitelist_item(chat_id: int, user_id: int = Depends(get_current_user_id)):
    removed = await whitelist_service.remove_from_whitelist(user_id, chat_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Элемент не найден в Whitelist")
    return {"success": True}


@router.get("/whitelist/export")
async def export_whitelist_items(user_id: int = Depends(get_current_user_id)):
    return await whitelist_service.export_whitelist(user_id)


@router.post("/whitelist/import")
async def import_whitelist_items(req: WhitelistImportRequest, user_id: int = Depends(get_current_user_id)):
    imported = await whitelist_service.import_whitelist(user_id, req.items)
    return {"success": True, "imported_count": imported}


# ---------------- SETTINGS & SCHEDULES ---------------- #

@router.get("/settings")
async def get_user_settings(user_id: int = Depends(get_current_user_id)):
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM settings WHERE telegram_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}


@router.post("/settings")
async def update_user_settings(req: SettingsUpdateRequest, user_id: int = Depends(get_current_user_id)):
    updates = []
    params = []
    for field, val in req.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ?")
        params.append(val)

    if updates:
        params.append(user_id)
        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE settings SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                params,
            )
            await conn.commit()

        # If scheduler setting changed, re-sync user schedule
        if req.auto_clean_enabled is not None:
            if req.auto_clean_enabled == 1:
                scheduler_service.schedule_user_job(
                    telegram_id=user_id,
                    frequency=req.auto_clean_frequency or "weekly",
                    scope=req.auto_clean_scope or "smart",
                    mode=req.auto_clean_mode or "dry_run",
                )

    return {"success": True, "message": "Настройки сохранены"}


# ---------------- HYGIENE SCORE ---------------- #

@router.get("/hygiene-score")
async def get_hygiene_score(user_id: int = Depends(get_current_user_id)):
    current = await hygiene_score_service.get_current_score(user_id)
    history = await hygiene_score_service.get_history(user_id)
    return {"current": current, "history": history}


# ---------------- REJOIN MANIFEST & BACKUP ---------------- #

@router.get("/rejoin-manifest")
async def get_rejoin_manifest(user_id: int = Depends(get_current_user_id)):
    return await backup_service.get_rejoin_manifest(user_id)


@router.get("/backup/export")
async def export_all_backup(user_id: int = Depends(get_current_user_id)):
    return await backup_service.export_full_backup(user_id)


@router.post("/backup/import")
async def import_all_backup(payload: Dict[str, Any], user_id: int = Depends(get_current_user_id)):
    result = await backup_service.import_backup(user_id, payload)
    return {"success": True, "result": result}
