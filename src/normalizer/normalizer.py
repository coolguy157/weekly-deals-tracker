"""
normalizer.py
Core ProductNormalizer class orchestrating unit parsing, text cleaning,
deal disaggregation, commodity categorization, and promotional calculation.
"""

from typing import List, Optional, Tuple
import re
from ..fetcher import FlyerItem
from ..promo_extractor import PromoExtractor
from .models import NormalizedDeal
from .categories import COMMODITY_PATTERNS, infer_category
from .units import UNIT_PATTERN, extract_unit_info
from .cleaner import (
    STORE_BRANDS,
    DEPARTMENT_BANNERS,
    PACKAGING_SALES_PATTERNS,
    DISCARD_CHUNK_PATTERN,
    normalize_text,
    clean_sales_notes,
)
from .expander import (
    SPLIT_PATTERN,
    COORD_PATTERN,
    COLOR_OR_NOUN_PATTERN,
    PREFIX_COORD_PATTERN,
    expand_chunk,
    pre_expand_deal_string,
)


class ProductNormalizer:
    """Parses raw circular text into normalized product entities with unit sizes and brands."""

    UNIT_PATTERN = UNIT_PATTERN
    SPLIT_PATTERN = SPLIT_PATTERN
    COORD_PATTERN = COORD_PATTERN
    COLOR_OR_NOUN_PATTERN = COLOR_OR_NOUN_PATTERN
    PREFIX_COORD_PATTERN = PREFIX_COORD_PATTERN
    STORE_BRANDS = STORE_BRANDS
    DEPARTMENT_BANNERS = DEPARTMENT_BANNERS
    PACKAGING_SALES_PATTERNS = PACKAGING_SALES_PATTERNS
    DISCARD_CHUNK_PATTERN = DISCARD_CHUNK_PATTERN
    COMMODITY_PATTERNS = COMMODITY_PATTERNS

    def infer_category(self, text: str) -> Optional[str]:
        return infer_category(text)

    def normalize_text(self, text: str) -> str:
        return normalize_text(text)

    def clean_sales_notes(self, text: str) -> str:
        return clean_sales_notes(text)

    def extract_unit_info(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        return extract_unit_info(text)

    def _expand_chunk(self, chunk: str) -> List[str]:
        return expand_chunk(chunk)

    def disaggregate_and_normalize(self, item: FlyerItem) -> List[NormalizedDeal]:
        """Split bundled multi-item deal strings into discrete normalized deal entries."""
        raw_name = self.normalize_text(item.name)
        if not raw_name:
            return []

        # Ignore department banner headers
        lower_raw = raw_name.lower().strip()
        if lower_raw in self.DEPARTMENT_BANNERS or any(lower_raw.startswith(b) for b in self.DEPARTMENT_BANNERS if len(b) > 8):
            return []

        # Strip packaging and promotional notes before disaggregation
        cleaned_name = self.clean_sales_notes(raw_name)
        if not cleaned_name:
            cleaned_name = raw_name

        # Pre-expand compound structures (produce suffixes/prefixes, cheese combos, brand pairs)
        cleaned_name = pre_expand_deal_string(cleaned_name)

        # If brand field contains multiple brands joined by '|', split and normalize them
        item_brands = [self.normalize_text(b) for b in (item.brand or "").split("|") if self.normalize_text(b)]

        # Check if deal starts with a known store brand
        initial_store_brand = None
        for sb in self.STORE_BRANDS:
            if raw_name.lower().startswith(sb.lower()):
                initial_store_brand = sb
                break

        # Remove comma between coupled descriptive adjectives (e.g. "Boneless, Skinless" -> "Boneless Skinless")
        pre_split_name = re.sub(
            r"\b(Boneless|Bone-In|Fresh|Wild|Raw|Cooked),\s*(Skinless|Center\s*Cut|Never\s*Frozen|Caught|Peeled)\b",
            r"\1 \2",
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Remove comma before unit/size expressions with optional leading decimal (e.g. ", .5 ltr.")
        pre_split_name = re.sub(
            r",\s*(?=(?:\d+(?:\.\d+)?|\.\d+)\s*(?:ct|count|oz|ounce|lb|pound|pk|pack|ltr|liter|qt|quart|pt|pint|gal|gallon|ml)\b)",
            " ",
            pre_split_name,
            flags=re.IGNORECASE,
        )

        # First split into comma-separated chunks, then expand each chunk
        chunks = [c.strip() for c in re.split(r",\s*", pre_split_name) if len(c.strip()) > 3]
        if not chunks:
            chunks = [cleaned_name]

        sub_items: List[str] = []
        for chunk in chunks:
            expanded = self._expand_chunk(chunk)
            for sub in expanded:
                sub_clean = sub.replace("__OR__", " or ").strip(" ,.-")
                if not sub_clean or self.DISCARD_CHUNK_PATTERN.search(sub_clean):
                    continue
                sub_items.append(sub_clean)

        if not sub_items:
            sub_items = [cleaned_name.replace("__OR__", " or ")]

        normalized_deals: List[NormalizedDeal] = []

        for idx, sub_name in enumerate(sub_items):
            size, unit = self.extract_unit_info(sub_name)

            # Match brand:
            # 1. Look for known item_brands or store brands within sub_name
            brand = None
            for b in item_brands:
                if re.search(r"\b" + re.escape(b) + r"\b", sub_name, re.IGNORECASE):
                    brand = b
                    break

            if not brand:
                for sb in self.STORE_BRANDS:
                    if re.search(r"\b" + re.escape(sb) + r"\b", sub_name, re.IGNORECASE):
                        brand = sb
                        break

            # Check common national brand keywords if not found
            if not brand:
                for nb in [
                    "McCormick", "Kraft", "Pillsbury", "Ro-Tel", "Libby's", "Bush's", "Mission",
                    "Fage", "Horizon", "Daisy", "Philadelphia", "Lays", "Lay's", "Cheetos", "Ruffles",
                    "Doritos", "Tostitos", "Smartfood", "Frito Lay", "Utz", "Planters",
                    "Coca-Cola", "Pepsi", "Gatorade", "Propel", "Budweiser", "Bud",
                    "Shiner", "Corona", "Modelo", "Dos Equis", "Decoy", "Conundrum", "Rold Gold",
                    "Miss Vickie's", "Soleil", "Snapple", "Poppi", "Ozarka", "Sunny Delight",
                    "Premier Protein", "Dr Pepper", "Powerade", "Vitamin Water", "Dasani", "Snuggle", "Purex",
                    "Tina's", "Yoplait", "Chobani", "Dannon", "Oikos", "Tillamook",
                    "Quaker", "Cap'n Crunch", "Life", "Campbell's", "Chef Boyardee", "Barilla",
                    "Dole", "Bolthouse", "Bolthouse Farms", "NatureSweet", "Fresh Express", "Taylor Farms",
                    "Earthbound Farm", "Organic Girl", "Green Giant", "Birds Eye",
                    "Driscoll's", "Sunkist", "Halo", "Cuties", "Chiquita", "Del Monte",
                    "Stouffer's", "Lean Cuisine", "Perdue", "Tyson", "Oscar Mayer",
                    "Sugardale", "Jimmy Dean", "Hillshire Farm", "Applegate", "Hebrew National", "Ball Park", "Nathan's",
                    "General Mills", "Kellogg's", "Post", "Sargento", "Cabot", "Hidden Valley", "Ken's",
                    "Ken's Steak House", "Marzetti", "Newman's Own", "Wish-Bone", "Heinz", "French's",
                    "Hellmann's", "Best Foods",
                ]:
                    if re.search(r"\b" + re.escape(nb) + r"\b", sub_name, re.IGNORECASE):
                        brand = nb
                        break

            # 2. Inherit initial store brand if deal started with it and no other explicit brand in sub_name
            if not brand and initial_store_brand:
                other_brand_in_sub = any(
                    re.search(r"\b" + re.escape(b) + r"\b", sub_name, re.IGNORECASE)
                    for b in item_brands
                    if b.lower() != initial_store_brand.lower()
                )
                if not other_brand_in_sub:
                    brand = initial_store_brand

            # 3. If still not found and only 1 item_brand available, assign it
            if not brand and len(item_brands) == 1:
                brand = item_brands[0]

            # Calculate unit price if size and price are present
            unit_price = None
            if item.price and size and size > 0:
                unit_price = round(item.price / size, 4)

            # Clean sub_name for canonical representation
            canonical = sub_name

            # Standardize Cheap Chicken Monday deli promotion
            if re.search(r"\bcheap\s+chicken\b", canonical, re.IGNORECASE):
                canonical = "Cheap Chicken Monday 8 Piece Dark Meat"
                brand = "Signature Cafe"
                size = 8.0
                unit = "ct"
                if item.price:
                    unit_price = round(item.price / 8.0, 4)

            # Strip store brand prefix on meat cuts (e.g. "Signature Farms Boneless Chicken Breast" -> "Boneless Chicken Breast")
            meat_keywords = (
                "chicken", "beef", "pork", "turkey", "roast", "steak", "steaks",
                "chop", "chops", "rib", "ribs", "thigh", "thighs", "breast", "breasts",
                "drumstick", "drumsticks", "wing", "wings", "tenderloin", "brisket",
                "sausage", "bacon", "loin"
            )
            for sb in ["Signature SELECT", "Signature Farms"]:
                if canonical.lower().startswith(sb.lower()):
                    remainder = canonical[len(sb):].strip(" ,.-")
                    if any(k in remainder.lower() for k in meat_keywords):
                        canonical = remainder
                    break

            # Strip leading "Fresh " for meat/poultry cuts to match generic ads
            if canonical.lower().startswith("fresh boneless") or canonical.lower().startswith("fresh whole") or canonical.lower().startswith("fresh diced"):
                canonical = canonical[6:].strip()

            # Normalize trailing value pack modifiers for chicken cuts
            if "chicken" in canonical.lower() and canonical.lower().endswith(" value pack"):
                canonical = canonical[:-11].strip()

            # Standardize seasoning and mix packet canonical names (strip minor packet weight ranges)
            seasoning_keywords = ("taco seasoning", "seasoning mix", "gravy mix", "fajita seasoning", "chili seasoning", "sloppy joe seasoning")
            if any(k in canonical.lower() for k in seasoning_keywords):
                canonical = self.UNIT_PATTERN.sub("", canonical).strip(" ,.-")

            canonical = self.clean_sales_notes(canonical)
            canonical = " ".join(canonical.split()).strip(" ,.-")

            # Standardize Lucerne Eggs canonical name
            if brand == "Lucerne" and ("egg" in canonical.lower() or "eggs" in canonical.lower()):
                if not canonical.lower().startswith("lucerne"):
                    canonical = f"Lucerne {canonical}"

            # Standardize Lucerne Cheese canonical name and unify standard 6-8 oz / 8 oz pack sizing
            if brand == "Lucerne" and "cheese" in canonical.lower():
                if not canonical.lower().startswith("lucerne"):
                    canonical = f"Lucerne {canonical}"
                if re.search(r"\b(?:Shredded|Chunk|Sliced|Block\s+)?Cheese\s+8\s*oz\b", canonical, re.IGNORECASE):
                    canonical = re.sub(r"\b8\s*oz\b", "6-8 oz", canonical, flags=re.IGNORECASE)
                    size = 7.0
                    unit = "oz"
                    if item.price and size > 0:
                        unit_price = round(item.price / size, 4)

            # Standardize single-serve yogurt cups (e.g. Yoplait, Lucerne 4-6 oz / 6 oz / unsized)
            if re.search(r"\b(Yoplait|Lucerne)\s+Yogurt\b", canonical, re.IGNORECASE) and not re.search(r"\b(?:32|24|4\s*pack|4\s*pk)\b", canonical, re.IGNORECASE):
                brand_name = "Yoplait" if "yoplait" in canonical.lower() else "Lucerne"
                brand = brand_name
                canonical = f"{brand_name} Yogurt 4-6 oz"
                size = 5.0
                unit = "oz"
                if item.price and size > 0:
                    unit_price = round(item.price / size, 4)

            # Multi-pack cream cheese weight resolution (e.g. Philadelphia Cream Cheese 2 Pack -> 16 oz)
            if "cream cheese" in canonical.lower() and (unit in ("pk", "pack", "ct", "count") or "2 pack" in canonical.lower() or "2 pk" in canonical.lower()):
                if size == 2.0 or (size is None and "2 pack" in canonical.lower()):
                    size = 16.0  # 2 x 8 oz blocks
                    unit = "oz"
                    if item.price and size > 0:
                        unit_price = round(item.price / size, 4)

            # Deli counter cheese & meat / fresh butcher meat sold by the pound fallback
            deli_brands = ("Primo Taglio", "Dietz & Watson", "Dietz Watson", "Boar's Head")
            full_item_text = f"{item.name} {item.description or ''} {item.pre_price_text or ''} {item.post_price_text or ''}"
            if size is None and item.price:
                is_fresh_meat_cut = (
                    any(k in canonical.lower() for k in ("boneless", "skinless", "bone-in", "fresh", "center cut", "loin chop", "pork chop", "ribeye", "sirloin", "t-bone", "filet mignon", "flank steak", "drumsticks", "tenders", "cutlets"))
                    and any(k in canonical.lower() for k in ("chicken", "beef", "pork", "turkey", "salmon", "tilapia", "cod", "shrimp"))
                )
                if (
                    brand in deli_brands
                    or re.search(r"\b(?:per\s+lb|sold\s+by\s+the\s+lb|/lb|\$?\d+(?:\.\d+)?\s*/?\s*lb)\b", full_item_text, re.IGNORECASE)
                    or is_fresh_meat_cut
                ):
                    size = 1.0
                    unit = "lb"
                    unit_price = round(item.price / 1.0, 4)

            # Extract promo mechanics across item text, pre/post price notes, and description
            promo_info = PromoExtractor.extract_promo(
                sub_name,
                additional_texts=[item.name, item.pre_price_text, item.post_price_text, item.description],
            )

            advertised_price = item.price
            promo_type = promo_info.promo_type if promo_info else "standard"
            promo_detail = promo_info.promo_detail if promo_info else None
            qualifying_qty = promo_info.qualifying_qty if promo_info else 1
            coupon_discount = promo_info.coupon_discount if promo_info else None
            base_price = item.original_price

            if advertised_price is None and promo_info:
                advertised_price = PromoExtractor.calculate_effective_price(promo_info, base_price=item.original_price)
                if advertised_price is not None and size and size > 0:
                    unit_price = round(advertised_price / size, 4)
            elif advertised_price is not None and unit_price is None and size and size > 0:
                unit_price = round(advertised_price / size, 4)

            image = item.clean_image_url or item.cutout_image_url
            category = self.infer_category(canonical)

            normalized_deals.append(
                NormalizedDeal(
                    raw_deal_id=item.id,
                    flyer_id=item.flyer_id,
                    page_number=item.page_number,
                    is_front_page=item.is_front_page,
                    canonical_name=canonical,
                    brand=brand,
                    advertised_price=advertised_price,
                    unit_size=size,
                    unit_type=unit,
                    unit_price=unit_price,
                    raw_title=item.name,
                    image_url=image,
                    promo_type=promo_type,
                    category=category,
                    promo_detail=promo_detail,
                    qualifying_qty=qualifying_qty,
                    base_price=base_price,
                    coupon_discount=coupon_discount,
                )
            )

        return normalized_deals
