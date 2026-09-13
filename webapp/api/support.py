from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from services.support_service import support_service
from utils.rate_limiter import support_rate_limiter
from webapp.api.auth import get_current_user_id
from utils.logger import logger

router = APIRouter(prefix="/support", tags=["Support"])


class TicketCreateRequest(BaseModel):
    category: str = Field(default="other", description="Ticket category")
    subject: str = Field(..., min_length=3, max_length=120, description="Brief subject")
    description: str = Field(..., min_length=10, max_length=2000, description="Detailed description")
    priority: str = Field(default="medium", description="Priority level")


class TicketReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Reply content")


@router.get("/faq")
async def get_faq():
    """Returns knowledge base FAQ questions and answers."""
    return {"success": True, "data": support_service.get_faq()}


@router.get("/tickets")
async def list_tickets(
    user_id: int = Depends(get_current_user_id),
):
    """Lists all support tickets opened by the current user."""
    tickets = await support_service.get_user_tickets(user_id)
    return {"success": True, "data": tickets}


@router.post("/tickets")
async def create_ticket(
    body: TicketCreateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Creates a new support ticket and sends initial message."""
    await support_rate_limiter.check(str(user_id))
    ticket = await support_service.create_ticket(
        telegram_id=user_id,
        category=body.category,
        subject=body.subject,
        description=body.description,
        priority=body.priority,
    )
    return {"success": True, "data": ticket}


@router.get("/tickets/{ticket_number}")
async def get_ticket(
    ticket_number: str,
    user_id: int = Depends(get_current_user_id),
):
    """Retrieves ticket thread details. Strictly prevents cross-user IDOR."""
    detail = await support_service.get_ticket_details(ticket_number, telegram_id=user_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Тикет не найден или доступ к нему ограничен.",
        )
    return {"success": True, "data": detail}


@router.post("/tickets/{ticket_number}/reply")
async def add_reply(
    ticket_number: str,
    body: TicketReplyRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Appends a user reply to an existing support ticket thread."""
    result = await support_service.add_reply(
        ticket_number=ticket_number,
        sender_type="user",
        sender_id=user_id,
        message=body.message,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Не удалось добавить ответ. Тикет не найден или принадлежит другому пользователю.",
        )
    return {"success": True, "data": result}
