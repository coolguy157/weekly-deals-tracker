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
        r"((?:\d+(?:\.\d+)?|\.\d+))\s*-\s*((?:\d+(?:\.\d+)?|\.\d+))\s*(oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon|ml)\b|"
        r"((?:\d+(?:\.\d+)?|\.\d+))\s*(oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon|ml)\b",
        re.IGNORECASE,
    )

    # Disaggregation delimiters (e.g. "Item A, Item B or Item C")
    SPLIT_PATTERN = re.compile(r"\s+or\s+|\s*,\s*(?=[A-Z0-9])", re.IGNORECASE)

    # Coordinated meat/poultry cut patterns where a shared prefix/suffix applies to both
    COORD_PATTERN = re.compile(
        r"^(.*?)\b(Breasts|Thighs|Drumsticks|Wings|Pork Chops|Pork Loin Chops|Pork Spare Ribs|Whole Chickens)\s+or\s+(Breasts|Thighs|Drumsticks|Wings|Pork Chops|Pork Loin Chops|Pork Spare Ribs|Whole Chickens)\b(.*)$",
        re.IGNORECASE,
    )

    # Produce color/variety coordinated patterns: e.g. "Red or Green Grapes", "Yellow or Zucchini Squash"
    COLOR_OR_NOUN_PATTERN = re.compile(
        r"^(.*?)\b(Red|Green|Yellow|Zucchini|Black|White|Seedless|Baking|Sweet|Russet)\s+or\s+(Red|Green|Yellow|Zucchini|Black|White|Seedless|Baking|Sweet|Russet)\s+(Grapes|Squash|Potatoes|Apples|Pears|Onions|Peppers)\b(.*)$",
        re.IGNORECASE,
    )

    # Prefix coordination for packaged items: e.g. "Premier Protein Frozen Pancakes or Waffles"
    PREFIX_COORD_PATTERN = re.compile(
        r"^(.*?\b(?:Frozen|Protein|Organic|Natural|Fresh))\s+(Pancakes|Waffles|Bars|Treats|Burgers|Pizzas)\s+or\s+(Pancakes|Waffles|Bars|Treats|Burgers|Pizzas)\b(.*)$",
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

    DEPARTMENT_BANNERS = {
        "groceries", "wine", "beer", "produce", "meat", "seafood",
        "deli", "bakery", "floral", "pharmacy", "general merchandise", "dairy", "freshpass"
    }

    # Packaging, portioning, and promotional sales patterns to clean
    PACKAGING_SALES_PATTERNS = [
        re.compile(r",?\s*Sold in (?:a|the) \d+(?:\.\d+)?\s*(?:lb|oz|ct|bag)\.?\s*bag(?:\s+for\s+\$\d+(?:\.\d+)?)?(?:\s*each)?(?:\s*Limit\s*\d+)?", re.IGNORECASE),
        re.compile(r",?\s*Sold in (?:a|the) bag", re.IGNORECASE),
        re.compile(r",?\s*Sold by the (?:ea|lb|each|pound)", re.IGNORECASE),
        re.compile(r"\bLimit\s+\d+\b", re.IGNORECASE),
        re.compile(r",?\s*(?:or\s+)?Seasoned(?:\s+\$?\d+(?:\.\d+)?)?(?:\s*(?:lb|each))?\.?", re.IGNORECASE),
        re.compile(r",?\s*(?:Select|Selected)\s+Varieties\b", re.IGNORECASE),
        re.compile(r",?\s*Grade\s+AA?\b", re.IGNORECASE),
    ]

    DISCARD_CHUNK_PATTERN = re.compile(
        r"^(Sold in|Sold by|Limit \d+|Seasoned \$|\$\d+|for \$|each Limit|Select Varieties|Selected Varieties)",
        re.IGNORECASE,
    )

    def normalize_text(self, text: str) -> str:
        """Strip special symbols and extra whitespace."""
        cleaned = self.CLEAN_SYMBOLS.sub("", text)
        return " ".join(cleaned.split()).strip()

    def clean_sales_notes(self, text: str) -> str:
        """Strip packaging notes, quantity limits, and variant price clauses."""
        cleaned = text
        for pat in self.PACKAGING_SALES_PATTERNS:
            cleaned = pat.sub("", cleaned)
        return " ".join(cleaned.split()).strip(" ,.-")

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

    def _expand_chunk(self, chunk: str) -> List[str]:
        """Expand a single chunk, handling coordinated patterns like 'Breasts or Thighs' or simple 'or' splits."""
        chunk = re.sub(r"^(?:or|and)\s+", "", chunk.strip(), flags=re.IGNORECASE).strip(" ,.-")
        if not chunk:
            return []

        # 1. Check color/variety noun: "O Organics Red or Green Grapes" or "Yellow or Zucchini Squash"
        color_match = self.COLOR_OR_NOUN_PATTERN.match(chunk)
        if color_match:
            pre = color_match.group(1).strip()
            o1 = color_match.group(2).strip()
            o2 = color_match.group(3).strip()
            noun = color_match.group(4).strip()
            post = color_match.group(5).strip()
            item1 = f"{pre} {o1} {noun}".strip()
            item2 = f"{pre} {o2} {noun}".strip()
            results = [item1, item2]
            if post:
                for sub in self._expand_chunk(post):
                    results.append(sub)
            return results

        # 2. Check prefix coordination: "Premier Protein Frozen Pancakes or Waffles"
        pref_match = self.PREFIX_COORD_PATTERN.match(chunk)
        if pref_match:
            prefix = pref_match.group(1).strip()
            opt1 = pref_match.group(2).strip()
            opt2 = pref_match.group(3).strip()
            suffix = pref_match.group(4).strip()
            return [f"{prefix} {opt1} {suffix}".strip(), f"{prefix} {opt2} {suffix}".strip()]

        # 3. Check meat cut coordination
        coord_match = self.COORD_PATTERN.match(chunk)
        if coord_match:
            prefix = coord_match.group(1).strip()
            opt1 = coord_match.group(2).strip()
            opt2 = coord_match.group(3).strip()
            suffix = coord_match.group(4).strip()

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

        # 4. Standard split if no coordination matched
        splits = [s.strip() for s in self.SPLIT_PATTERN.split(chunk) if len(s.strip()) > 3]
        if len(splits) > 1:
            all_expanded = []
            for s in splits:
                all_expanded.extend(self._expand_chunk(s))
            return all_expanded

        return [chunk]

    def disaggregate_and_normalize(self, item: FlyerItem) -> List[NormalizedDeal]:
        """Split bundled multi-item deal strings into discrete normalized deal entries."""
        raw_name = self.normalize_text(item.name)
        if not raw_name:
            return []

        # Ignore department banner headers with no price
        if (item.price is None or item.price <= 0) and raw_name.lower() in self.DEPARTMENT_BANNERS:
            return []

        # Strip packaging and promotional notes before disaggregation
        cleaned_name = self.clean_sales_notes(raw_name)
        if not cleaned_name:
            cleaned_name = raw_name

        # Simplify packaging options "Cans or Bottles" -> "Cans/Bottles"
        cleaned_name = re.sub(r"\b(?:Cans|Bottles)\s+or\s+(?:Bottles|Cans)\b", "Cans/Bottles", cleaned_name, flags=re.IGNORECASE)

        # Expand produce suffix lists: "Acorn, Butternut or Spaghetti Squash" -> "Acorn Squash or Butternut Squash or Spaghetti Squash"
        def _expand_suffix_list(m):
            v1 = m.group(1).strip()
            v2 = m.group(2).strip()
            v3 = m.group(3).strip()
            noun = m.group(4).strip()
            return f"{v1} {noun} or {v2} {noun} or {v3} {noun}"

        cleaned_name = re.sub(
            r"\b([A-Za-z]+),\s*([A-Za-z]+)\s+or\s+([A-Za-z]+)\s+(Squash|Potatoes|Apples|Grapes|Pears|Melons|Peppers|Onions)\b",
            _expand_suffix_list,
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Expand produce prefix lists: "Baby Potatoes Red, Gold or Medley" -> "Baby Potatoes Red or Baby Potatoes Gold or Baby Potatoes Medley"
        def _expand_prefix_list(m):
            prefix = m.group(1).strip()
            v1 = m.group(2).strip()
            v2 = m.group(3).strip()
            v3 = m.group(4).strip()
            return f"{prefix} {v1} or {prefix} {v2} or {prefix} {v3}"

        cleaned_name = re.sub(
            r"\b((?:[A-Za-z0-9'\s]+\s+)?(?:Apples|Potatoes|Grapes|Pears|Citrus|Squash))\s+([A-Za-z]+),\s*([A-Za-z]+)\s+or\s+([A-Za-z\s]+)",
            _expand_prefix_list,
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Expand adjacent unpunctuated cheese types: "Lucerne Shredded Cheese String Cheese 32 oz"
        cleaned_name = re.sub(
            r"\b((?:[A-Za-z0-9'\s]+\s+)?)(Chunk|Shredded|Sliced|String|Block)\s+Cheese\s+(Chunk|Shredded|Sliced|String|Block)\s+Cheese\s+((?:(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?)\s*(?:oz|ounce|lb|pound|ct|count|pk|pack))\b",
            r"\1\2 Cheese \4 or \1\3 Cheese \4",
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Expand coordinated 3-item cheese lists: "Lucerne Chunk, Shredded or Sliced Cheese 24-32 oz"
        def _expand_cheese_list3(m):
            prefix = m.group(1).strip()
            p_str = f"{prefix} " if prefix else ""
            v1, v2, v3, size = m.group(2).strip(), m.group(3).strip(), m.group(4).strip(), m.group(5).strip()
            return f"{p_str}{v1} Cheese {size} or {p_str}{v2} Cheese {size} or {p_str}{v3} Cheese {size}"

        cleaned_name = re.sub(
            r"\b((?:[A-Za-z0-9'\s]+\s+)?)(Chunk|Shredded|Sliced|String|Block),\s*(Chunk|Shredded|Sliced|String|Block)\s+or\s+(Chunk|Shredded|Sliced|String|Block)\s+Cheese\s+((?:(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?)\s*(?:oz|ounce|lb|pound|ct|count|pk|pack))\b",
            _expand_cheese_list3,
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Expand coordinated 2-item cheese lists: "Lucerne Shredded or Sliced Cheese 24-32 oz"
        def _expand_cheese_list2(m):
            prefix = m.group(1).strip()
            p_str = f"{prefix} " if prefix else ""
            v1, v2, size = m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
            return f"{p_str}{v1} Cheese {size} or {p_str}{v2} Cheese {size}"

        cleaned_name = re.sub(
            r"\b((?:[A-Za-z0-9'\s]+\s+)?)(Chunk|Shredded|Sliced|String|Block)\s+or\s+(Chunk|Shredded|Sliced|String|Block)\s+Cheese\s+((?:(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?)\s*(?:oz|ounce|lb|pound|ct|count|pk|pack))\b",
            _expand_cheese_list2,
            cleaned_name,
            flags=re.IGNORECASE,
        )

        # Expand brand pair with shared size: "Doritos, Tostitos 6-13 oz" or "Lays or Cheetos 8-15 oz"
        def _expand_brand_size(m):
            b1 = m.group(1).strip()
            b2 = m.group(2).strip()
            size = m.group(3).strip()
            if not self.UNIT_PATTERN.search(b1) and len(b1) > 2 and len(b2) > 2:
                return f"{b1} {size}, {b2} {size}"
            return m.group(0)

        cleaned_name = re.sub(
            r"\b([A-Za-z0-9'\s]+?)(?:\s+or\s+|\s*,\s*)([A-Za-z0-9'\s]+?)\s+((?:(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?)\s*(?:oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon|ml)\b[^\,]*?)(?=\s+or\s+[A-Z]|,\s*[A-Z]|$)",
            _expand_brand_size,
            cleaned_name,
            flags=re.IGNORECASE,
        )

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
                sub_clean = sub.strip(" ,.-")
                if not sub_clean or self.DISCARD_CHUNK_PATTERN.search(sub_clean):
                    continue
                sub_items.append(sub_clean)

        if not sub_items:
            sub_items = [cleaned_name]

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
                    "Fage", "Horizon", "Daisy", "Philadelphia", "Lays", "Lay's", "Cheetos",
                    "Doritos", "Tostitos", "Coca-Cola", "Pepsi", "Gatorade", "Budweiser", "Bud",
                    "Shiner", "Corona", "Modelo", "Dos Equis", "Decoy", "Conundrum", "Rold Gold",
                    "Miss Vickie's", "Soleil", "Snapple", "Poppi", "Ozarka", "Sunny Delight",
                    "Premier Protein", "Dr Pepper", "Powerade", "Vitamin Water", "Dasani", "Snuggle", "Purex",
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

            # Strip store brand prefix for commodity meat/poultry cuts to match generic ads
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
