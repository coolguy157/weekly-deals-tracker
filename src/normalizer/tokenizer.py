"""
tokenizer.py
Lexical tokenizer scanning grocery circular item names into typed semantic tokens.
Replaces character-level sequential regex re-writing with structured token streams.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional
import re

from .vocabulary import STORE_BRANDS, NATIONAL_BRANDS


class TokenType(Enum):
    BRAND = auto()
    HEAD_NOUN = auto()
    COORD = auto()
    COMMA = auto()
    UNIT_SPEC = auto()
    WORD = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    start: int = 0
    end: int = 0


ALL_BRANDS = sorted(
    STORE_BRANDS + [b for b in NATIONAL_BRANDS if b not in STORE_BRANDS],
    key=len,
    reverse=True,
)
BRAND_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in ALL_BRANDS) + r")\b",
    re.IGNORECASE,
)

HEAD_NOUN_PATTERNS = [
    r"Greenhouse\s+Grown\s+(?:Salad\s+(?:Blends?|Kits?|Bowls?))",
    r"Salad\s+(?:Blends?|Kits?|Bowls?)(?:\s+or\s+(?:Salad\s+)?(?:Blends?|Kits?|Bowls?))?",
    r"(?:Baby\s+Bella\s+|White\s+|Portabella\s+|Button\s+)?Mushrooms?",
    r"(?:Chicken\s+)?Breasts?",
    r"Whole\s+Chickens?",
    r"Chicken\s+(?:Thighs|Drumsticks|Wings|Tenders|Cutlets)",
    r"Pork\s+(?:Chops|Loin\s+Chops|Spare\s+Ribs)",
    r"Cheese|Cheddar|Mozzarella|Swiss|Provolone|Parmesan\s+Cheese",
    r"Squash|Pumpkin(?:s)?|Potato(?:es)?|Apple(?:s)?|Grape(?:s)?|Pear(?:s)?|Melon(?:s)?",
    r"Pepper(?:s)?|Onion(?:s)?|Tomato(?:es)?|Orange(?:s)?|Citrus|Peach(?:es)?|Plum(?:s)?",
    r"Berries|Berry|Parfaits?|Tortillas?|Pizza\s+Crusts?|Crusts?",
    r"Bread|Buns|Rolls|Butter|Yogurt|Milk|Eggs",
    r"Sausage\s+(?:Links|Patties|Rolls)|Sausage|Bacon",
    r"Dressing",
]
HEAD_NOUN_PATTERN = re.compile(
    r"\b(" + "|".join(HEAD_NOUN_PATTERNS) + r")\b",
    re.IGNORECASE,
)

UNIT_SPEC_PATTERN = re.compile(
    r"\b(?:Half\s+Gallon|(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?\s*(?:oz|ounce|lb|pound|ct|count|pk|pack|qt|quart|pt|pint|gal|gallon|ltr|liter|ml)\.?)\b",
    re.IGNORECASE,
)


def tokenize(text: str) -> List[Token]:
    """Tokenize a grocery title into typed semantic tokens."""
    tokens: List[Token] = []
    pos = 0
    text_len = len(text)

    while pos < text_len:
        if text[pos].isspace():
            pos += 1
            continue

        if text[pos] == ",":
            tokens.append(Token(TokenType.COMMA, ",", pos, pos + 1))
            pos += 1
            continue

        bm = BRAND_PATTERN.match(text, pos)
        if bm:
            tokens.append(Token(TokenType.BRAND, bm.group(1), pos, bm.end()))
            pos = bm.end()
            continue

        hn = HEAD_NOUN_PATTERN.match(text, pos)
        if hn:
            tokens.append(Token(TokenType.HEAD_NOUN, hn.group(1), pos, hn.end()))
            pos = hn.end()
            continue

        um = UNIT_SPEC_PATTERN.match(text, pos)
        if um:
            tokens.append(Token(TokenType.UNIT_SPEC, um.group(0), pos, um.end()))
            pos = um.end()
            continue

        cm = re.match(r"\b(or|and)\b", text[pos:], re.IGNORECASE)
        if cm:
            tokens.append(Token(TokenType.COORD, cm.group(1), pos, pos + len(cm.group(1))))
            pos += len(cm.group(1))
            continue

        wm = re.match(r"[A-Za-z0-9'\-]+", text[pos:])
        if wm:
            tokens.append(Token(TokenType.WORD, wm.group(0), pos, pos + len(wm.group(0))))
            pos += len(wm.group(0))
            continue

        pos += 1

    return tokens
