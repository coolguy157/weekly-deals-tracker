"""
cleaner.py
Text cleaning, punctuation normalization, sales noise removal, and store brand registries.
"""

from typing import List, Set
import re

CLEAN_SYMBOLS = re.compile(r"[®™©]")

STORE_BRANDS: List[str] = [
    "Signature SELECT",
    "Signature Farms",
    "Lucerne",
    "Open Nature",
    "O Organics",
    "Waterfront BISTRO",
    "Primo Taglio",
    "Signature Cafe",
    "Nature's Promise",
    "Our Brand",
    "Giant",
    "Martin's",
    "Taste of Inspirations",
    "Guiding Stars",
]

DEPARTMENT_BANNERS: Set[str] = {
    "groceries", "wine", "beer", "produce", "meat", "seafood",
    "deli", "bakery", "floral", "pharmacy", "general merchandise", "dairy", "freshpass",
    "from your full service butcher block",
    "full service butcher block",
    "butcher block",
    "service butcher block",
    "from our service butcher block",
    "from your butcher block",
    "from our butcher block",
    "full service meat counter",
    "service seafood counter",
    "from our bakery",
    "from our deli",
}

GENERIC_PLACEHOLDER_NAMES: Set[str] = {
    "assorted products",
    "assorted product",
    "assorted varieties",
    "select varieties",
    "selected varieties",
    "mix or match",
}

# Packaging, portioning, and promotional sales patterns to clean from canonical names
PACKAGING_SALES_PATTERNS: List[re.Pattern] = [
    re.compile(r",?\s*Sold in (?:a|the) \d+(?:\.\d+)?\s*(?:lb|oz|ct|bag)\.?\s*bag(?:\s+for\s+\$\d+(?:\.\d+)?)?(?:\s*each)?(?:\s*Limit\s*\d+)?", re.IGNORECASE),
    re.compile(r",?\s*Sold in (?:a|the) bag", re.IGNORECASE),
    re.compile(r",?\s*Sold by the (?:ea|lb|each|pound)", re.IGNORECASE),
    re.compile(r"\bLimit\s+\d+\b", re.IGNORECASE),
    re.compile(r",?\s*(?:or\s+)?Seasoned(?:\s+\$?\d+(?:\.\d+)?)?(?:\s*(?:lb|each))?\.?", re.IGNORECASE),
    re.compile(r",?\s*(?:Select|Selected)\s+Varieties\b", re.IGNORECASE),
    re.compile(r",?\s*Grade\s+AA?\b", re.IGNORECASE),
    re.compile(r",?\s*-\s*Each(?:\.{2,}.*|\s*\(.*?\))?", re.IGNORECASE),
    re.compile(r"\s*\((?:traditionally\s+comes|approx|locally\s+grown)[^\)]*\)", re.IGNORECASE),
    re.compile(r"\.{2,}.*$", re.IGNORECASE),
    re.compile(r",?\s*\bBUY\s+\d+\s+GET\s+\d+\s+(?:OF\s+EQUAL\s+OR\s+LESSER\s+VALUE\s+)?FREE\b", re.IGNORECASE),
    re.compile(r",?\s*\bBUY\s+(?:ONE|TWO)\s+GET\s+(?:ONE|TWO)\s+FREE\b", re.IGNORECASE),
    re.compile(r",?\s*\bBOGO\s+FREE\b", re.IGNORECASE),
    re.compile(r",?\s*\bBUY\s+\d+\s+GET\s+\d+\s+(?:\d+%\s*OFF|HALF\s+OFF|50%\s*OFF)\b", re.IGNORECASE),
    re.compile(r",?\s*\b(?:MUST\s+BUY|WHEN\s+YOU\s+BUY)\s+\d+(?:\s+OR\s+MORE)?(?:\s*@\s*\$?\d+(?:\.\d{2})?)?(?:\s*(?:EA|EACH))?\b", re.IGNORECASE),
    re.compile(r",?\s*\b(?:WITH\s+)?(?:DIGITAL\s+COUPON|FOR\s*U\s*COUPON|FOR\s*U|JUST\s*FOR\s*U|MEMBER\s+PRICE|WITH\s+CARD)(?:\s*\$?\d+(?:\.\d{2})?)?\b", re.IGNORECASE),
    re.compile(r",?\s*\b(?:SAVE|\$)\s*\d+(?:\.\d{2})?\s+(?:OFF\s+)?(?:WITH\s+)?(?:DIGITAL\s+COUPON|FOR\s*U)\b", re.IGNORECASE),
    re.compile(r",?\s*-\s*\$\d+(?:\.\d{2})?(?:\s*/\s*(?:lb|ea|count|oz|pkg))?\.?\s*(?:DIGITAL\s+COUPON|FOR\s*U|WITH\s+CARD|MEMBER\s+PRICE)?\b", re.IGNORECASE),
    re.compile(r",?\s*(?:-\s*)?\$?\d+(?:\.\d{2})?\s*/\s*(?:lb|ea|count|oz|pkg)\.?\s*(?:DIGITAL\s+COUPON|FOR\s*U|WITH\s+CARD|MEMBER\s+PRICE)\b", re.IGNORECASE),
    re.compile(r",?\s*(?:-\s*)?(?:\d+[-\s]+POINT\s+FREEBIE|FREE\s+(?:.*?\s+)?when\s+you\s+redeem\s+\d+\s+(?:CHOICE\s+)?points?)(?:,?\s*Save\s+(?:at\s+least|up\s+to)?\s*\$?\d+(?:\.\d{2})?)?.*$", re.IGNORECASE),
    re.compile(r",?\s*(?:-\s*)?Save\s+(?:at\s+least|up\s+to)?\s*\$?\d+(?:\.\d{2})?\s*(?:with\s+this\s+week['’]?s\s+meal\s+deal)?.*$", re.IGNORECASE),
]

DISCARD_CHUNK_PATTERN = re.compile(
    r"^(Sold in|Sold by|Limit \d+|Seasoned \$|\$\d+|for \$|each Limit|Select Varieties|Selected Varieties|\d+[-\s]+POINT\s+FREEBIE|Save at least|Save up to)",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Strip special symbols and extra whitespace."""
    cleaned = CLEAN_SYMBOLS.sub("", text)
    return " ".join(cleaned.split()).strip()


def clean_sales_notes(text: str) -> str:
    """Strip packaging notes, quantity limits, and variant price clauses."""
    cleaned = text
    for pat in PACKAGING_SALES_PATTERNS:
        cleaned = pat.sub("", cleaned)
    return " ".join(cleaned.split()).strip(" ,.-")
