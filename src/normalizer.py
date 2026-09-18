"""
Product entity normalizer and multi-item deal disaggregator.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import re
from .fetcher import FlyerItem


@dataclass
class NormalizedDeal:
    raw_deal_id: int
    flyer_id: int
    page_number: int
    is_front_page: bool
    canonical_name: str
    brand: Optional[str]
    advertised_price: Optional[float]
    unit_size: Optional[float]
    unit_type: Optional[str]
    unit_price: Optional[float]
    raw_title: str
    image_url: Optional[str]
    promo_type: str = "standard"
    is_trusted: bool = True
    source_type: str = "flipp_api"


class ProductNormalizer:
    """Parses raw circular text into normalized product entities with unit sizes and brands."""

    # Common grocery units
    UNIT_PATTERN = re.compile(
        r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon)\b|"
        r"(\d+(?:\.\d+)?)\s*(oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon)\b",
        re.IGNORECASE,
    )

    # Disaggregation delimiters (e.g. "Item A, Item B or Item C")
    SPLIT_PATTERN = re.compile(r"\s+or\s+|\s*,\s*(?=[A-Z0-9])", re.IGNORECASE)

    # Clean punctuation and trademark symbols
    CLEAN_SYMBOLS = re.compile(r"[®™©]")

    def normalize_text(self, text: str) -> str:
        """Strip special symbols and extra whitespace."""
        cleaned = self.CLEAN_SYMBOLS.sub("", text)
        return " ".join(cleaned.split()).strip()

    def extract_unit_info(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract numeric size and unit of measure from product text."""
        match = self.UNIT_PATTERN.search(text)
        if not match:
            return None, None

        if match.group(1) and match.group(2):
            # Range like 12-14 oz -> use average
            size = (float(match.group(1)) + float(match.group(2))) / 2.0
            unit = match.group(3).lower()
        else:
            size = float(match.group(4))
            unit = match.group(5).lower()

        # Standardize unit abbreviations
        unit_map = {
            "ounce": "oz",
            "pound": "lb",
            "count": "ct",
            "pack": "pk",
            "liter": "ltr",
            "quart": "qt",
            "pint": "pt",
            "gallon": "gal",
        }
        std_unit = unit_map.get(unit, unit)
        return size, std_unit

    def disaggregate_and_normalize(self, item: FlyerItem) -> List[NormalizedDeal]:
        """Split bundled multi-item deal strings into discrete normalized deal entries."""
        raw_name = self.normalize_text(item.name)
        if not raw_name:
            return []

        # If brand field contains multiple brands joined by '|', split them
        item_brands = [b.strip() for b in (item.brand or "").split("|") if b.strip()]

        # Check if the title represents a compound list of products
        sub_items = [s.strip() for s in self.SPLIT_PATTERN.split(raw_name) if len(s.strip()) > 3]
        if not sub_items:
            sub_items = [raw_name]

        normalized_deals: List[NormalizedDeal] = []

        for idx, sub_name in enumerate(sub_items):
            size, unit = self.extract_unit_info(sub_name)

            # Match brand if available
            brand = None
            if idx < len(item_brands):
                brand = item_brands[idx]
            elif item_brands:
                brand = item_brands[0]

            # Calculate unit price if size and price are present
            unit_price = None
            if item.price and size and size > 0:
                unit_price = round(item.price / size, 4)

            # Clean sub_name for canonical representation
            canonical = sub_name
            # Remove trailing sizes from canonical name if desired, or retain full descriptor
            canonical = " ".join(canonical.split()).strip(" ,.-")

            image = item.clean_image_url or item.cutout_image_url

            normalized_deals.append(
                NormalizedDeal(
                    raw_deal_id=item.id,
                    flyer_id=item.flyer_id,
                    page_number=item.page_number,
                    is_front_page=item.is_front_page,
                    canonical_name=canonical,
                    brand=brand,
                    advertised_price=item.price,
                    unit_size=size,
                    unit_type=unit,
                    unit_price=unit_price,
                    raw_title=item.name,
                    image_url=image,
                )
            )

        return normalized_deals
