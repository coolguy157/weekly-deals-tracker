"""
normalizer package.
Provides ProductNormalizer and NormalizedDeal for circular text parsing and entity normalization.
"""

from .models import NormalizedDeal
from .normalizer import ProductNormalizer
from .categories import COMMODITY_PATTERNS, infer_category
from .units import UNIT_PATTERN, extract_unit_info
from .cleaner import normalize_text, clean_sales_notes, GENERIC_PLACEHOLDER_NAMES

__all__ = [
    "NormalizedDeal",
    "ProductNormalizer",
    "COMMODITY_PATTERNS",
    "infer_category",
    "UNIT_PATTERN",
    "extract_unit_info",
    "normalize_text",
    "clean_sales_notes",
    "GENERIC_PLACEHOLDER_NAMES",
]
