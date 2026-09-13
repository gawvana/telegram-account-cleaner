from fastapi import APIRouter, Depends, HTTPException, status
from services.preview_service import preview_service
from telegram_client.manager import client_manager
from telegram_client.scanner import scanner
from webapp.api.auth import get_current_user_id
from utils.logger import logger

router = APIRouter(prefix="/scan", tags=["Scan & Preview"])


@router.get("")
@router.get("/preview")
async def get_scan_preview(user_id: int = Depends(get_current_user_id)):
    """Scans authorized user's Telegram dialogs and returns structured preview with heuristics."""
    try:
        async with client_manager.get_client(user_id) as client:
            scan_result = await scanner.scan(client, user_id)
            return preview_service.to_webapp_dict(scan_result)
    except Exception as e:
        logger.error(f"Error scanning dialogs for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or "Не удалось получить список диалогов.",
        )
