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

    # Coordinated meat/poultry cut patterns where a shared prefix/suffix applies to both
    COORD_PATTERN = re.compile(
        r"^(.*?)\b(Breasts|Thighs|Drumsticks|Wings|Pork Chops|Pork Loin Chops|Pork Spare Ribs|Whole Chickens)\s+or\s+(Breasts|Thighs|Drumsticks|Wings|Pork Chops|Pork Loin Chops|Pork Spare Ribs|Whole Chickens)\b(.*)$",
        re.IGNORECASE,
    )

    # Clean punctuation and trademark symbols
    CLEAN_SYMBOLS = re.compile(r"[®™©]")

    STORE_BRANDS = [
        "Signature SELECT",
        "Signature Farms",
        "Lucerne",
        "Open Nature",
        "O Organics",
        "Waterfront BISTRO",
        "Primo Taglio",
        "Signature Cafe",
    ]

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

    def _expand_chunk(self, chunk: str) -> List[str]:
        """Expand a single chunk, handling coordinated patterns like 'Breasts or Thighs' or simple 'or' splits."""
        chunk = chunk.strip()
        if not chunk:
            return []

        coord_match = self.COORD_PATTERN.match(chunk)
        if coord_match:
            prefix = coord_match.group(1).strip()
            opt1 = coord_match.group(2).strip()
            opt2 = coord_match.group(3).strip()
            suffix = coord_match.group(4).strip()

            # If prefix itself has compound items separated by 'or' / commas
            prefix_splits = [s.strip() for s in self.SPLIT_PATTERN.split(prefix) if len(s.strip()) > 3]
            if len(prefix_splits) > 1:
                common_prefix = prefix_splits[-1]
                prior_items = prefix_splits[:-1]
            else:
                common_prefix = prefix
                prior_items = []

            item1 = f"{common_prefix} {opt1} {suffix}".strip()
            item2 = f"{common_prefix} {opt2} {suffix}".strip()
            return prior_items + [item1, item2]

        splits = [s.strip() for s in self.SPLIT_PATTERN.split(chunk) if len(s.strip()) > 3]
        return splits if splits else [chunk]

    def disaggregate_and_normalize(self, item: FlyerItem) -> List[NormalizedDeal]:
        """Split bundled multi-item deal strings into discrete normalized deal entries."""
        raw_name = self.normalize_text(item.name)
        if not raw_name:
            return []

        # If brand field contains multiple brands joined by '|', split them
        item_brands = [b.strip() for b in (item.brand or "").split("|") if b.strip()]

        # First split into comma-separated chunks, then expand each chunk
        chunks = [c.strip() for c in re.split(r",\s*", raw_name) if len(c.strip()) > 3]
        if not chunks:
            chunks = [raw_name]

        sub_items: List[str] = []
        for chunk in chunks:
            sub_items.extend(self._expand_chunk(chunk))

        if not sub_items:
            sub_items = [raw_name]

        normalized_deals: List[NormalizedDeal] = []

        for idx, sub_name in enumerate(sub_items):
            size, unit = self.extract_unit_info(sub_name)

            # Match brand if available or infer from store brands
            brand = None
            if idx < len(item_brands):
                brand = item_brands[idx]
            elif item_brands:
                brand = item_brands[0]

            if not brand:
                for sb in self.STORE_BRANDS:
                    if sb.lower() in sub_name.lower():
                        brand = sb
                        break

            # Calculate unit price if size and price are present
            unit_price = None
            if item.price and size and size > 0:
                unit_price = round(item.price / size, 4)

            # Clean sub_name for canonical representation
            canonical = sub_name

            # Strip store brand prefix for commodity meat/produce cuts if present
            for sb in ["Signature SELECT", "Signature Farms"]:
                if canonical.lower().startswith(sb.lower()):
                    canonical = canonical[len(sb):].strip(" ,.-")
                    break

            # Strip leading "Fresh " for meat/poultry cuts to match generic ads
            if canonical.lower().startswith("fresh boneless") or canonical.lower().startswith("fresh whole") or canonical.lower().startswith("fresh diced"):
                canonical = canonical[6:].strip()

            # Normalize trailing value pack modifiers for chicken cuts
            if "chicken" in canonical.lower() and canonical.lower().endswith(" value pack"):
                canonical = canonical[:-11].strip()

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
