from fastapi import APIRouter, Depends, HTTPException, Response, status
from database import db
from services.backup_service import backup_service
from services.statistics_service import statistics_service
from webapp.api.auth import get_current_user_id

router = APIRouter(prefix="/history", tags=["History & Statistics"])


@router.get("")
async def get_history(user_id: int = Depends(get_current_user_id)):
    """Fetches user cleanup history, breakdown by chat types, and summary metrics."""
    return await statistics_service.get_user_statistics(user_id)


@router.get("/export/csv")
async def export_history_csv(user_id: int = Depends(get_current_user_id)):
    """Exports cleanup items history as a downloadable CSV."""
    csv_data = await backup_service.export_history_csv(user_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=cleanup_history_{user_id}.csv"},
    )


@router.get("/admin")
async def get_admin_stats(user_id: int = Depends(get_current_user_id)):
    """Returns strictly anonymized high-level metrics for instance health monitoring. Requires is_admin = 1."""
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT is_admin FROM users WHERE telegram_id = ?", (user_id,))
        row = await cursor.fetchone()
        if not row or not row["is_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещён. Требуются права администратора.",
            )
    return await statistics_service.get_anonymized_admin_stats()
