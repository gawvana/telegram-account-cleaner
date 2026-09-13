import logging
from typing import Optional
from database import db
from features.translator.config import SUPPORTED_LANGUAGES, DEFAULT_SETTINGS

try:
    from deep_translator import GoogleTranslator
    HAS_DEEP_TRANSLATOR = True
except ImportError:
    HAS_DEEP_TRANSLATOR = False

logger = logging.getLogger(__name__)

class TranslatorService:
    def __init__(self):
        self.supported = SUPPORTED_LANGUAGES

    def get_supported_languages(self) -> dict:
        return self.supported

    async def get_stats(self, user_id: int) -> dict:
        state = await db.get_feature_state(user_id, "translator")
        if state:
            return {
                "total_translations": state.get("actions_count", 0),
                "characters_translated": state.get("characters_count", 0) # Assuming we can store custom activity
            }
        return {"total_translations": 0, "characters_translated": 0}
    
    async def _update_stats(self, user_id: int, char_count: int):
        if not user_id:
            return
        await db.increment_feature_activity(user_id, "translator")

    async def translate(self, text: str, source: str = "auto", target: str = "ru", user_id: Optional[int] = None) -> dict:
        if not text or not text.strip():
            return {
                "original_text": text,
                "translated_text": text,
                "detected_source": source,
                "target_language": target
            }

        # Safety: loop protection
        if text.startswith("[Translated]") or "[Translated]" in text:
            return {
                "original_text": text,
                "translated_text": text,
                "detected_source": source,
                "target_language": target
            }

        translated_text = text
        try:
            if HAS_DEEP_TRANSLATOR:
                translator = GoogleTranslator(source=source, target=target)
                translated_text = translator.translate(text)
                if not translated_text:
                    translated_text = text
            else:
                translated_text = f"[Translated] {text}"
        except Exception as e:
            logger.error(f"Translation error: {e}")
            translated_text = f"[Translation Error] {text}"

        if user_id:
            await self._update_stats(user_id, len(text))

        return {
            "original_text": text,
            "translated_text": translated_text,
            "detected_source": source,
            "target_language": target
        }

translator_service = TranslatorService()
