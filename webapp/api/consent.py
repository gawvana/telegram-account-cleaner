from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from typing import Optional

from services.consent_service import consent_service
from webapp.api.auth import get_current_user_id
from utils.logger import logger

router = APIRouter(prefix="/consent", tags=["Consent"])


class ConsentAcceptRequest(BaseModel):
    agreement_version: Optional[int] = None
    privacy_version: Optional[int] = None


@router.get("/status")
async def get_consent_status(
    user_id: int = Depends(get_current_user_id),
):
    """Returns current user's versioned consent state."""
    status = await consent_service.get_consent_status(user_id)
    return {"success": True, "data": status}


@router.post("/accept")
async def accept_consent(
    request: Request,
    body: ConsentAcceptRequest = ConsentAcceptRequest(),
    user_id: int = Depends(get_current_user_id),
):
    """Explicitly accepts current terms and privacy agreement."""
    ip_addr = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    result = await consent_service.record_user_consent(
        telegram_id=user_id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    return {"success": True, "data": result}


@router.post("/withdraw")
async def withdraw_consent(
    user_id: int = Depends(get_current_user_id),
):
    """Revokes consent, halts active cleanups, and erases encrypted session."""
    withdrawn = await consent_service.withdraw_user_consent(user_id)
    return {"success": True, "data": {"withdrawn": withdrawn}}
