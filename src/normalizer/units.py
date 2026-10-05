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
    match = UNIT_PATTERN.search(text)
    if not match:
        return None, None

    if match.group(1) and match.group(2):
        # Range like 12-14 oz -> use average
        size = (float(match.group(1)) + float(match.group(2))) / 2.0
        unit = match.group(3).lower()
    else:
        size = float(match.group(4))
        unit = match.group(5).lower()

    std_unit = UNIT_MAP.get(unit, unit)
    return size, std_unit
