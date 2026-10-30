"""
units.py
Parsing and standardization of package units, numeric sizes, and measurement weights.
"""

from typing import Tuple, Optional
import re

# Common grocery unit regex (handles ranges like 12-14 oz as well as single values like 16 oz or .5 ltr)
UNIT_PATTERN = re.compile(
    r"((?:\d+(?:\.\d+)?|\.\d+))\s*-\s*((?:\d+(?:\.\d+)?|\.\d+))\s*(oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon|ml)\b|"
    r"((?:\d+(?:\.\d+)?|\.\d+))\s*(oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon|ml)\b",
    re.IGNORECASE,
)

UNIT_MAP = {
    "ounce": "oz",
    "pound": "lb",
    "count": "ct",
    "pack": "pk",
    "liter": "ltr",
    "quart": "qt",
    "pint": "pt",
    "gallon": "gal",
}


def extract_unit_info(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Extract numeric size and standardized unit of measure from product text."""
    # Check for seafood/meat count per pound (e.g., "31-40 ct per lb", "16-20 count/lb", "21-25 count per pound")
    # This denotes shrimp sizing grade, sold by the pound, NOT a fixed count package.
    if re.search(r"\b(?:\d+\s*-\s*\d+|\d+)\s*(?:ct|count)\s*(?:per\s+(?:lb|pound)|/\s*(?:lb|pound))\b", text, re.IGNORECASE):
        return 1.0, "lb"

    # Check for per-unit rate modifiers (e.g. "20% Off/lb.", "$2.00 Off/lb.", "5.00 Off/lb.", "$1.00 Off/ea.")
    m_rate = re.search(r"(?:per\s+|/\s*)(lb|pound|oz|ounce|ea|each|count|ct)\b", text, re.IGNORECASE)
    if m_rate:
        u_raw = m_rate.group(1).lower()
        std_u = UNIT_MAP.get(u_raw, u_raw)
        return 1.0, std_u

    match = UNIT_PATTERN.search(text)
    if not match:
        return None, None

    if match.group(1) and match.group(2):
        # Range like 12-14 oz -> use average
        size = round((float(match.group(1)) + float(match.group(2))) / 2.0, 3)
        unit = match.group(3).lower()
    else:
        size = round(float(match.group(4)), 3)
        unit = match.group(5).lower()

    std_unit = UNIT_MAP.get(unit, unit)
    return size, std_unit
