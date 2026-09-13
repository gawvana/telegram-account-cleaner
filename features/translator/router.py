from fastapi import APIRouter, Depends, HTTPException
from webapp.api.auth import get_current_user_id
from features.translator.models import TranslateRequest, TranslateResponse, TranslateStatsDTO
from features.translator.service import translator_service
from features.translator.config import SUPPORTED_LANGUAGES

router = APIRouter(prefix="/api/features/translator", tags=["translator"])

@router.post("/translate", response_model=TranslateResponse)
async def translate_text(request: TranslateRequest, user_id: int = Depends(get_current_user_id)):
    if request.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported target language")
    
    result = await translator_service.translate(
        text=request.text,
        source=request.source_language,
        target=request.target_language,
        user_id=user_id
    )
    return TranslateResponse(**result)

@router.get("/languages")
async def get_languages(user_id: int = Depends(get_current_user_id)):
    return translator_service.get_supported_languages()

@router.get("/stats", response_model=TranslateStatsDTO)
async def get_translation_stats(user_id: int = Depends(get_current_user_id)):
    stats = await translator_service.get_stats(user_id)
    return TranslateStatsDTO(**stats)
