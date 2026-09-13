from typing import List, Dict
from .effects import EFFECTS

class PrankService:
    def get_effects(self) -> List[Dict]:
        return [
            {"id": "zalgo", "name": "Zalgo", "description": "Lightweight zalgo text"},
            {"id": "reverse", "name": "Reverse", "description": "Reverse words/characters"},
            {"id": "leet", "name": "Leet", "description": "1337 speak transform"},
            {"id": "scramble", "name": "Scramble", "description": "Inner letter scrambler"},
            {"id": "vaporwave", "name": "Vaporwave", "description": "Spaced fullwidth text"}
        ]
        
    def apply_effect(self, text: str, effect: str) -> str:
        if effect in EFFECTS:
            return EFFECTS[effect](text)
        return text

prank_service = PrankService()
