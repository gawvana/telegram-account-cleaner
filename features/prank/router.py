from fastapi import APIRouter, Depends, HTTPException
from webapp.api.auth import get_current_user_id
from .models import PrankTransformRequest, PrankTransformResponse, PrankEffectItem
from .service import prank_service

router = APIRouter(prefix="/api/features/prank", tags=["prank"])

@router.get("/effects", response_model=list[PrankEffectItem])
async def get_effects(user_id: int = Depends(get_current_user_id)):
    return prank_service.get_effects()

@router.post("/transform", response_model=PrankTransformResponse)
async def transform_text(req: PrankTransformRequest, user_id: int = Depends(get_current_user_id)):
    result = prank_service.apply_effect(req.text, req.effect)
    return PrankTransformResponse(original_text=req.text, prank_text=result, effect=req.effect)
