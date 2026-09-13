from fastapi import APIRouter, Depends
from typing import List
from auth.dependencies import get_current_user_id
from features.fonts.models import FontStyleItem, FontTransformRequest, FontTransformResponse
from features.fonts.service import fonts_service

router = APIRouter(prefix="/api/features/fonts", tags=["fonts"])

@router.get("/styles", response_model=List[FontStyleItem])
async def get_styles(user_id: int = Depends(get_current_user_id)):
    styles = fonts_service.get_available_styles()
    return [FontStyleItem(**s) for s in styles]

@router.post("/transform", response_model=FontTransformResponse)
async def transform_text(req: FontTransformRequest, user_id: int = Depends(get_current_user_id)):
    result = fonts_service.transform(req.text, req.style)
    return FontTransformResponse(
        original_text=req.text,
        transformed_text=result,
        style=req.style
    )
