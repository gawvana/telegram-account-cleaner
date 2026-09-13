import random
import re

def zalgo(text: str) -> str:
    marks = [chr(i) for i in range(0x0300, 0x036F + 1)]
    result = []
    for char in text:
        result.append(char)
        if char.isalnum():
            result.extend(random.choices(marks, k=random.randint(1, 3)))
    return "".join(result)

def reverse(text: str) -> str:
    return text[::-1]

def leet(text: str) -> str:
    mapping = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7'}
    return "".join(mapping.get(c.lower(), c) for c in text)

def scramble(text: str) -> str:
    def _scramble_word(word: str) -> str:
        if len(word) <= 3:
            return word
        inner = list(word[1:-1])
        random.shuffle(inner)
        return word[0] + "".join(inner) + word[-1]
    
    return re.sub(r'[A-Za-z]+', lambda m: _scramble_word(m.group(0)), text)

def vaporwave(text: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else c for c in text)

EFFECTS = {
    "zalgo": zalgo,
    "reverse": reverse,
    "leet": leet,
    "scramble": scramble,
    "vaporwave": vaporwave
}
