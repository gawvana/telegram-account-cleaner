from fastapi import APIRouter, Depends
from typing import List
from auth.dependencies import get_current_user_id
from features.rp.models import RPStyleItem, RPTransformRequest, RPTransformResponse
from features.rp.service import rp_service

router = APIRouter(prefix="/api/features/rp", tags=["rp"])

@router.get("/styles", response_model=List[RPStyleItem])
async def get_styles(user_id: int = Depends(get_current_user_id)):
    styles = rp_service.get_styles()
    return [RPStyleItem(**s) for s in styles]

@router.post("/transform", response_model=RPTransformResponse)
async def transform_text(req: RPTransformRequest, user_id: int = Depends(get_current_user_id)):
    result = rp_service.transform(req.text, req.style)
    return RPTransformResponse(
        original_text=req.text,
        styled_text=result,
        style=req.style
    )
