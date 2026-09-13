from pydantic import BaseModel

class TranslateRequest(BaseModel):
    text: str
    source_language: str = "auto"
    target_language: str = "ru"

class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_source: str
    target_language: str

class TranslateStatsDTO(BaseModel):
    total_translations: int
    characters_translated: int
