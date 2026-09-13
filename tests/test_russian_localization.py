import pytest
from features.__init__ import auto_discover_features
from features.registry import feature_registry
import os

def test_feature_modules_russian():
    auto_discover_features()
    features = feature_registry.get_all()
    assert len(features) == 12, "Should have 12 features"
    english_words = ["Deleted", "Messages", "Auto", "Responder", "Edited", "Anti", "Spam", "Mute"]
    for feat in features:
        for word in english_words:
            assert word not in feat.name, f"English word '{word}' found in feature name '{feat.name}'"
            assert word not in feat.description, f"English word '{word}' found in feature description '{feat.description}'"

def test_public_index_html_russian_labels():
    path = os.path.join("public", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert "Очистка" in content
    assert "Функции" in content
    assert "Система" in content
    assert "Все функции" in content
    assert "Обзор" in content

def test_public_app_js_russian_labels():
    path = os.path.join("public", "app.js")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # We will just assert that Russian labels exist, maybe check for some specific mappings
    assert "Очистка" in content or "Функции" in content or "Активен" in content or "работает" in content
