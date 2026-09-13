import json
from pathlib import Path
from typing import Dict
from config import settings

_TRANSLATIONS: Dict[str, Dict[str, str]] = {}


def load_translations() -> None:
    i18n_dir = Path(__file__).parent.parent / "i18n"
    for lang_file in i18n_dir.glob("*.json"):
        lang = lang_file.stem
        try:
            _TRANSLATIONS[lang] = json.loads(lang_file.read_text(encoding="utf-8"))
        except Exception:
            pass


load_translations()


def t(key: str, lang: str = "", **kwargs) -> str:
    """Translates a message key, interpolating keyword arguments."""
    selected_lang = lang or settings.DEFAULT_LANGUAGE
    strings = _TRANSLATIONS.get(selected_lang) or _TRANSLATIONS.get("ru", {})
    text = strings.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text
