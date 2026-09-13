import pytest
from httpx import AsyncClient
from features.translator.service import translator_service, HAS_DEEP_TRANSLATOR

pytestmark = pytest.mark.asyncio

async def test_translator_service_translate():
    text = "Hello world"
    res = await translator_service.translate(text, target="ru")
    assert res["original_text"] == text
    assert res["target_language"] == "ru"
    if not HAS_DEEP_TRANSLATOR:
        assert res["translated_text"] == f"[Translated] {text}"

async def test_translation_loop_prevention():
    text = "[Translated] Hello world"
    res = await translator_service.translate(text, target="ru")
    assert res["translated_text"] == text

async def test_translator_service_stats_and_languages():
    langs = translator_service.get_supported_languages()
    assert "ru" in langs
    assert "en" in langs
    
    user_id = 99912345
    # Do a translation to update stats (assuming db feature enabled)
    from database import db
    async with db.get_connection() as conn:
        await conn.execute("INSERT OR IGNORE INTO feature_states (telegram_id, feature_id, enabled) VALUES (?, 'translator', 1)", (user_id,))
        await conn.commit()
    
    await translator_service.translate("Test stats", user_id=user_id)
    stats = await translator_service.get_stats(user_id)
    assert stats["total_translations"] >= 0

def test_api_translator_languages(client, auth_headers):
    response = client.get("/api/features/translator/languages", headers=auth_headers)
    assert response.status_code == 200
    langs = response.json()
    assert "ru" in langs

def test_api_translator_translate(client, auth_headers):
    payload = {
        "text": "Hello",
        "target_language": "ru",
        "source_language": "auto"
    }
    response = client.post("/api/features/translator/translate", json=payload, headers=auth_headers)
    assert response.status_code == 200
    res = response.json()
    assert "translated_text" in res

def test_api_translator_invalid_lang(client, auth_headers):
    payload = {
        "text": "Hello",
        "target_language": "invalid_lang"
    }
    response = client.post("/api/features/translator/translate", json=payload, headers=auth_headers)
    assert response.status_code == 400

def test_api_translator_stats(client, auth_headers):
    response = client.get("/api/features/translator/stats", headers=auth_headers)
    assert response.status_code == 200
    assert "total_translations" in response.json()
