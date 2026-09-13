import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from services.cleanup_service import cleanup_service
from telegram_client.models import ChatType, CleanupPlan
from webapp.api.auth import get_current_user_id
from webapp.schemas import CleanupStartRequest
from utils.logger import logger

router = APIRouter(prefix="/cleanup", tags=["Cleanup"])


@router.post("/start")
async def start_cleanup_job(req: CleanupStartRequest, user_id: int = Depends(get_current_user_id)):
    """Initiates an asynchronous cleanup job for the user."""
    # Convert string types to ChatType enum
    target_enums = []
    for t_str in req.target_types:
        try:
            target_enums.append(ChatType(t_str.upper()))
        except ValueError:
            pass

    plan = CleanupPlan(
        is_max_clean=req.is_max_clean,
        is_smart_clean=req.is_smart_clean,
        target_types=target_enums,
        target_chat_ids=req.target_chat_ids,
        dry_run=req.dry_run,
    )

    # Launch background task for execution
    async def _execute_bg():
        try:
            await cleanup_service.run_cleanup(user_id, plan)
        except Exception as e:
            logger.error(f"Background cleanup failed for {user_id}: {e}")

    asyncio.create_task(_execute_bg())
    return {"success": True, "message": "Процесс очистки запущен"}


@router.post("/stop")
async def stop_cleanup_job(user_id: int = Depends(get_current_user_id)):
    """Signals immediate cooperative cancellation of user's active cleanup job."""
    stopped = await cleanup_service.stop_cleanup(user_id)
    if not stopped:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нет активной задачи для отмены")
    return {"success": True, "message": "Остановка задачи запрошена"}


@router.get("/status")
async def get_cleanup_status(user_id: int = Depends(get_current_user_id)):
    """Returns the current state of any active cleanup job."""
    tracker = cleanup_service.get_active_tracker(user_id)
    if not tracker:
        return {"is_active": False}
    return {"is_active": True, "progress": tracker.to_dict()}


@router.get("/stream")
async def stream_cleanup_progress(user_id: int = Depends(get_current_user_id)):
    """Server-Sent Events (SSE) endpoint providing live, real-time progress updates."""
    async def event_generator():
        tracker = cleanup_service.get_active_tracker(user_id)
        if not tracker:
            yield f"data: {json.dumps({'is_active': False})}\n\n"
            return

        while True:
            current_tracker = cleanup_service.get_active_tracker(user_id)
            if not current_tracker or current_tracker.is_finished:
                last_data = current_tracker.to_dict() if current_tracker else {"is_active": False}
                yield f"data: {json.dumps(last_data)}\n\n"
                break

            data = current_tracker.to_dict()
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
