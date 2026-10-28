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
from .ast_parser import DealASTParser
from .vocabulary import STORE_BRANDS, NATIONAL_BRANDS, DEPARTMENT_BANNERS
from .rules import (
    COLLAGE_5_FOR_5_MAP,
    STAPLES_5_FOR_5,
    apply_store_brand_meat_stripping,
    apply_poultry_cut_standardization,
    apply_beef_cut_standardization,
    apply_ground_meat_standardization,
    apply_berry_standardization,
    apply_seasoning_standardization,
    apply_egg_standardization,
    apply_brand_specific_rules,
    apply_deli_or_meat_per_lb_fallback,
)
from .cleaner import (
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
    NATIONAL_BRANDS = NATIONAL_BRANDS

    def __init__(self):
        self.ast_parser = DealASTParser()

    def infer_category(self, text: str) -> Optional[str]:
        return infer_category(text)

    def normalize_text(self, text: str) -> str:
        return normalize_text(text)

    def clean_sales_notes(self, text: str, preserve_bulk_pkg: bool = False) -> str:
        return clean_sales_notes(text, preserve_bulk_pkg=preserve_bulk_pkg)

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

        # Strip packaging and promotional notes before disaggregation (preserving bulk package clauses for pricing)
        cleaned_name = self.clean_sales_notes(raw_name, preserve_bulk_pkg=True)
        if not cleaned_name:
            cleaned_name = raw_name

        # Remove comma between coupled descriptive adjectives (e.g. "Boneless, Skinless" -> "Boneless Skinless")
        cleaned_name = re.sub(
            r"\b(Boneless|Bone-In|Fresh|Wild|Raw|Cooked),\s*(Skinless|Center\s*Cut|Never\s*Frozen|Caught|Peeled)\b",
            r"\1 \2",
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Remove comma before "Sold in" expressions so bulk rate clause remains attached to preceding item
        cleaned_name = re.sub(
            r",\s*(?=Sold in\b)",
            " ",
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Remove comma before unit/size/range expressions (e.g. ", 4.75-6 oz." or ", .5 ltr.")
        cleaned_name = re.sub(
            r",\s*(?=(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?\s*(?:ct|count|oz|ounce|lb|pound|pk|pack|ltr|liter|qt|quart|pt|pint|gal|gallon|ml)\b)",
            " ",
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Pre-expand compound structures (produce suffixes/prefixes, cheese combos, brand pairs)
        cleaned_name = pre_expand_deal_string(cleaned_name)

        # First split into comma-separated chunks, then expand each chunk
        chunks = [c.strip() for c in re.split(r",\s*", cleaned_name) if len(c.strip()) > 3]
        if not chunks:
            chunks = [cleaned_name]

        # If brand field contains multiple brands joined by '|', split and normalize them
        item_brands = [self.normalize_text(b) for b in (item.brand or "").split("|") if self.normalize_text(b)]

        # Check if deal starts with a known store brand or national brand
        initial_brand = None
        for sb in self.STORE_BRANDS:
            if raw_name.lower().startswith(sb.lower()):
                initial_brand = sb
                break
        if not initial_brand:
            for nb in self.NATIONAL_BRANDS:
                if raw_name.lower().startswith(nb.lower()):
                    initial_brand = nb
                    break
        initial_store_brand = initial_brand if initial_brand in self.STORE_BRANDS else None

        sub_items: List[str] = []
        for chunk in chunks:
            ast_chunk_items = self.ast_parser.disaggregate(chunk)
            if len(ast_chunk_items) > 1:
                expanded = ast_chunk_items
            else:
                expanded = self._expand_chunk(chunk)
            for sub in expanded:
                sub_clean = sub.replace("__OR__", " or ").strip(" ,.-")
                if not sub_clean or self.DISCARD_CHUNK_PATTERN.search(sub_clean):
                    continue
                # Discard pure numbers or fragments with fewer than 2 letters (e.g. "3.25", "1")
                if not re.search(r"[A-Za-z]{2,}", sub_clean):
                    continue
                # Discard standalone count/unit fragments with no product noun (e.g. "24 ct", "16 ct. minis")
                if re.match(r"^(?:\d+(?:\.\d+)?|\.\d+)\s*(?:ct\.?|count|oz\.?|ounce|lb\.?|pound|pk\.?|pack)(?:\s+minis)?\.?$", sub_clean, re.IGNORECASE):
                    continue
                sub_items.append(sub_clean)

        if not sub_items:
            sub_items = [cleaned_name.replace("__OR__", " or ")]

        normalized_deals: List[NormalizedDeal] = []

        # Mix & Match "5 for $5" collage detection across the entire item
        is_5_for_5 = bool(item.price == 5.0 and sum(1 for s in STAPLES_5_FOR_5 if s in item.name.lower()) >= 4)

        for idx, sub_name in enumerate(sub_items):
            size, unit = self.extract_unit_info(sub_name)
            size_from_desc = False
            if size is None and getattr(item, "description", None):
                desc_size, desc_unit = self.extract_unit_info(item.description)
                if desc_size is not None:
                    size, unit = desc_size, desc_unit
                    size_from_desc = True
            if size is None and getattr(item, "post_price_text", None):
                post_size, post_unit = self.extract_unit_info(item.post_price_text)
                if post_size is not None:
                    size, unit = post_size, post_unit

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
                for nb in self.NATIONAL_BRANDS:
                    if re.search(r"\b" + re.escape(nb) + r"\b", sub_name, re.IGNORECASE):
                        brand = nb
                        break

            # 2. Inherit initial brand if deal started with it and no other explicit brand in sub_name
            if not brand and initial_brand and not is_5_for_5:
                other_brand_in_sub = any(
                    re.search(r"\b" + re.escape(b) + r"\b", sub_name, re.IGNORECASE)
                    for b in item_brands
                    if b.lower() != initial_brand.lower()
                )
                if not other_brand_in_sub:
                    brand = initial_brand

            # 3. If still not found and only 1 item_brand available, assign it
            if not brand and len(item_brands) == 1:
                brand = item_brands[0]

            # Check for bulk package rate clause: "Sold in 3 lb. Package for $11.97 ea." or "Sold in a 2 lb. bag for $13.98 each"
            pkg_rate_match = re.search(
                r"\bSold in (?:a|the)?\s*(\d+(?:\.\d+)?)\s*(lb|oz|ct|count)\.?\s*(?:bag|package|pkg|box|container)?\s+for\s+\$(\d+(?:\.\d+)?)\b",
                sub_name,
                re.IGNORECASE,
            )
            pkg_promo_detail = None
            pkg_advertised_price = None
            unit_price = None
            if pkg_rate_match and item.price:
                pkg_qty = float(pkg_rate_match.group(1))
                pkg_u = pkg_rate_match.group(2).lower()
                pkg_cost = float(pkg_rate_match.group(3))
                if pkg_qty > 0 and abs(item.price - (pkg_cost / pkg_qty)) < 0.05:
                    pkg_advertised_price = pkg_cost
                    size = pkg_qty
                    unit = "lb" if pkg_u in ("lb", "pound") else pkg_u
                    unit_price = round(pkg_cost / pkg_qty, 4)
                    pkg_promo_detail = f"Sold in {int(pkg_qty) if pkg_qty.is_integer() else pkg_qty} {unit} pkg"
            elif item.price and size and size > 0:
                unit_price = round(item.price / size, 4)

            # Clean sub_name for canonical representation
            canonical = sub_name
            if size_from_desc and size and unit:
                size_str = int(size) if size.is_integer() else size
                canonical = f"{canonical} {size_str} {unit}"
            if not is_5_for_5 and brand and brand.lower() not in canonical.lower() and not initial_store_brand:
                canonical = f"{brand} {canonical}"

            if is_5_for_5:
                c_key = sub_name.lower().strip()
                if c_key in COLLAGE_5_FOR_5_MAP:
                    canonical, brand = COLLAGE_5_FOR_5_MAP[c_key]

            # Apply structured domain transformations
            canonical = apply_store_brand_meat_stripping(canonical)
            canonical = apply_poultry_cut_standardization(canonical)
            canonical = apply_beef_cut_standardization(canonical)
            canonical, brand = apply_ground_meat_standardization(canonical, brand)
            canonical, brand = apply_berry_standardization(canonical, brand)
            canonical = apply_seasoning_standardization(canonical)
            canonical = self.clean_sales_notes(canonical)
            canonical = " ".join(canonical.split()).strip(" ,.-")

            # Apply brand-specific rules
            canonical, brand, size, unit, unit_price = apply_brand_specific_rules(
                canonical=canonical,
                brand=brand,
                size=size,
                unit=unit,
                unit_price=unit_price,
                item_price=item.price,
                item_brands=item_brands,
                item_name=item.name,
            )

            # Apply commodity egg standardization across all brands
            canonical, brand, size, unit, unit_price = apply_egg_standardization(
                canonical=canonical,
                brand=brand,
                size=size,
                unit=unit,
                unit_price=unit_price,
                item_price=item.price,
            )

            # Fallback for butcher meat / deli counter sold by pound
            full_item_text = f"{item.name} {item.description or ''} {item.pre_price_text or ''} {item.post_price_text or ''}"
            size, unit, unit_price = apply_deli_or_meat_per_lb_fallback(
                canonical=canonical,
                brand=brand,
                size=size,
                unit=unit,
                unit_price=unit_price,
                item_price=item.price,
                full_item_text=full_item_text,
            )

            # Extract promo mechanics across item text, pre/post price notes, and description
            promo_info = PromoExtractor.extract_promo(
                sub_name,
                additional_texts=[item.name, item.pre_price_text, item.post_price_text, item.description],
            )

            advertised_price = pkg_advertised_price if pkg_advertised_price is not None else item.price
            promo_type = promo_info.promo_type if promo_info else "standard"
            promo_detail = promo_info.promo_detail if promo_info else None
            if pkg_promo_detail and (not promo_detail or promo_type == "standard"):
                promo_type = "must_buy"
                promo_detail = pkg_promo_detail
            qualifying_qty = promo_info.qualifying_qty if promo_info else 1

            if is_5_for_5:
                advertised_price = 1.00
                promo_type = "must_buy"
                promo_detail = "5 for $5.00 ($1.00 ea)"
                qualifying_qty = 5
            coupon_discount = promo_info.coupon_discount if promo_info else None
            base_price = item.original_price

            if promo_info:
                if advertised_price is None:
                    advertised_price = PromoExtractor.calculate_effective_price(promo_info, base_price=item.original_price)
                elif promo_info.qualifying_qty > 1 and promo_info.stated_unit_price is not None:
                    # If advertised_price was populated with the bundle total price (e.g. $6.00 for 2/ $6.00)
                    if promo_info.stated_total_price is not None and abs(advertised_price - promo_info.stated_total_price) < 0.01:
                        advertised_price = promo_info.stated_unit_price
                    elif abs(advertised_price - (promo_info.stated_unit_price * promo_info.qualifying_qty)) < 0.01:
                        advertised_price = promo_info.stated_unit_price

            if advertised_price is not None and size and size > 0:
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
