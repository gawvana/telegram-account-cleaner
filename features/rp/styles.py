import re

def transform_formal(text: str) -> str:
    replacements = {
        r"\b(hi|hello|hey)\b": "Greetings",
        r"\b(thanks|thx)\b": "I express my gratitude",
        r"\b(pls|please)\b": "if you would be so kind",
        r"\b(yeah|yep|yea)\b": "indeed",
        r"\b(nah|nope)\b": "I must decline",
        r"\b(sorry)\b": "my sincerest apologies"
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return text

def transform_casual(text: str) -> str:
    replacements = {
        r"\b(hello|greetings)\b": "hey",
        r"\b(how are you)\b": "what's up",
        r"\b(yes|indeed)\b": "yeah",
        r"\b(no)\b": "nah",
        r"\b(because)\b": "cuz",
        r"\b(going to)\b": "gonna",
        r"\b(want to)\b": "wanna"
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    text = re.sub(r"\.$", "", text)
    return text

def transform_pirate(text: str) -> str:
    replacements = {
        r"\b(hello|hi|hey)\b": "Ahoy",
        r"\b(friend|buddy|pal)\b": "matey",
        r"\b(you)\b": "ye",
        r"\b(your)\b": "yer",
        r"\b(yes)\b": "aye",
        r"\b(my)\b": "me",
        r"\b(wow|oh my)\b": "shiver me timbers",
        r"\b(is)\b": "be",
        r"\b(are)\b": "be"
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return text

def transform_old_style(text: str) -> str:
    replacements = {
        r"\b(you)\b": "thou",
        r"\b(your)\b": "thy",
        r"\b(yours)\b": "thine",
        r"\b(does)\b": "doth",
        r"\b(has)\b": "hath",
        r"\b(truly|really)\b": "verily",
        r"\b(listen|hear)\b": "hark"
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return text

def transform_fantasy(text: str) -> str:
    replacements = {
        r"\b(wow|omg)\b": "By the stars",
        r"\b(friend)\b": "companion",
        r"\b(country|place)\b": "realm",
        r"\b(good)\b": "noble",
        r"\b(promise)\b": "swear on my honor",
        r"\b(king|boss)\b": "lord"
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return text

def transform_robot(text: str) -> str:
    replacements = {
        r"\b(yes|yeah|yep)\b": "AFFIRMATIVE",
        r"\b(no|nah|nope)\b": "NEGATIVE",
        r"\b(hello|hi)\b": "BEEP BOOP. GREETINGS",
        r"\b(i understand|got it)\b": "QUERY PROCESSED",
        r"\b(error|wrong)\b": "MALFUNCTION"
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags=re.IGNORECASE)
    return text.upper()

RP_STYLES_MAP = {
    "formal": {"name": "Formal", "func": transform_formal, "sample": "Greetings, I express my gratitude."},
    "casual": {"name": "Casual", "func": transform_casual, "sample": "hey, what's up cuz"},
    "pirate": {"name": "Pirate", "func": transform_pirate, "sample": "Ahoy matey, shiver me timbers!"},
    "old_style": {"name": "Old-style", "func": transform_old_style, "sample": "Hark! Thou doth verily speak."},
    "fantasy": {"name": "Fantasy", "func": transform_fantasy, "sample": "By the stars, this realm is noble."},
    "robot": {"name": "Robot", "func": transform_robot, "sample": "BEEP BOOP. AFFIRMATIVE."}
}

def transform_text(text: str, style: str) -> str:
    style_info = RP_STYLES_MAP.get(style)
    if not style_info:
        return text
    return style_info["func"](text)
