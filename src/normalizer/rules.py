"""
rules.py
Discrete domain rules and catalog canonicalization overrides for supermarket deals.
Separates domain transformations from procedural if/else normalization loops.
"""

import re
from typing import Optional, Tuple, List
from .vocabulary import MEAT_KEYWORDS, SEASONING_KEYWORDS, DELI_BRANDS
from .units import UNIT_PATTERN

COLLAGE_5_FOR_5_MAP = {
    "kraft": ("Kraft Macaroni & Cheese", "Kraft"),
    "maruchan": ("Maruchan Yakisoba or Ramen", "Maruchan"),
    "michelina's": ("Michelina's Entree", "Michelina's"),
    "idahoan": ("Idahoan Mashed Potatoes", "Idahoan"),
    "bowl": ("Maruchan Ramen Bowl", "Maruchan"),
    "crest": ("Crest Toothpaste", "Crest"),
    "banquet": ("Banquet Pot Pies", "Banquet"),
    "snack pack": ("Snack Pack Pudding", "Snack Pack"),
    "chef boyardee": ("Chef Boyardee Canned Pasta", "Chef Boyardee"),
    "ragu": ("Ragu Pasta Sauce", "Ragu"),
}

STAPLES_5_FOR_5 = (
    "kraft", "maruchan", "michelina", "idahoan", "bowl", "crest",
    "banquet", "snack pack", "chef boyardee", "ragu",
)


def apply_store_brand_meat_stripping(canonical: str) -> str:
    """Strip store brand prefix on fresh meat cuts (e.g. 'Signature Farms Boneless Chicken Breast')."""
    for sb in ["Signature SELECT", "Signature Farms"]:
        if canonical.lower().startswith(sb.lower()):
            remainder = canonical[len(sb):].strip(" ,.-")
            if any(k in remainder.lower() for k in MEAT_KEYWORDS):
                return remainder
    # Strip leading package size modifiers on fresh meat cuts
    for pfx in ["Value Pack", "Family Size", "Small Pack"]:
        if canonical.lower().startswith(pfx.lower()):
            remainder = canonical[len(pfx):].strip(" ,.-")
            if any(k in remainder.lower() for k in MEAT_KEYWORDS):
                return remainder
    return canonical


def apply_poultry_cut_standardization(canonical: str) -> str:
    """Standardize fresh meat/poultry cut descriptions and value pack suffixes."""
    # Strip leading "Fresh " for meat/poultry cuts
    if canonical.lower().startswith("fresh boneless") or canonical.lower().startswith("fresh whole") or canonical.lower().startswith("fresh diced"):
        canonical = canonical[6:].strip()

    # Normalize trailing value pack modifiers
    if "chicken" in canonical.lower() and canonical.lower().endswith(" value pack"):
        canonical = canonical[:-11].strip()

    # Standardize bone-in chicken cuts
    if re.search(r"^(?:Fresh\s+)?Chicken\s+Thighs$", canonical, re.IGNORECASE):
        canonical = "Bone-In Chicken Thighs"
    elif re.search(r"^Fresh\s+Chicken\s+Drumsticks$", canonical, re.IGNORECASE):
        canonical = "Chicken Drumsticks"
    elif re.search(r"^(?:deli\s+)?wings$", canonical, re.IGNORECASE):
        canonical = "Chicken Wings"
    elif re.search(r"^(?:deli\s+)?tenders$", canonical, re.IGNORECASE):
        canonical = "Chicken Tenders"

    return canonical


def apply_beef_cut_standardization(canonical: str) -> str:
    """Standardize beef roast and cut descriptions."""
    if re.search(r"^(?:USDA\s+Choice\s+(?:Beef\s+)?)?Bottom\s+Round(?:\s+Roast)?$", canonical, re.IGNORECASE):
        if "usda choice" in canonical.lower():
            return "USDA Choice Beef Bottom Round Roast"
        return "Beef Bottom Round Roast"
    if re.search(r"^(?:USDA\s+Choice\s+(?:Beef\s+)?)?Top\s+Round(?:\s+Roast)?$", canonical, re.IGNORECASE):
        if "usda choice" in canonical.lower():
            return "USDA Choice Beef Top Round Roast"
        return "Beef Top Round Roast"
    if re.search(r"^(?:USDA\s+Choice\s+(?:Beef\s+)?)?Eye\s+of\s+Round(?:\s+Roast)?$", canonical, re.IGNORECASE):
        if "usda choice" in canonical.lower():
            return "USDA Choice Beef Eye of Round Roast"
        return "Beef Eye of Round Roast"
    if re.search(r"^(?:USDA\s+Choice\s+(?:Beef\s+)?)?Chuck(?:\s+Roast)?$", canonical, re.IGNORECASE):
        if "usda choice" in canonical.lower():
            return "USDA Choice Beef Chuck Roast"
        return "Beef Chuck Roast"
    if re.search(r"^(?:USDA\s+Choice\s+(?:Beef\s+)?)?Short\s+Ribs?(?:\s+Bone-?in)?$", canonical, re.IGNORECASE):
        if "usda choice" in canonical.lower():
            return "USDA Choice Beef Short Ribs"
        return "Beef Short Ribs"
    if re.search(r"^(?:USDA\s+Choice\s+(?:Beef\s+)?)?Chuck\s+Shoulder\s+Roast(?:\s+Bone-?in)?$", canonical, re.IGNORECASE):
        if "usda choice" in canonical.lower():
            return "USDA Choice Beef Chuck Shoulder Roast Bone-In"
        return "Beef Chuck Shoulder Roast Bone-In"
    return canonical


def apply_ground_meat_standardization(
    canonical: str,
    brand: Optional[str],
) -> Tuple[str, Optional[str]]:
    """
    Standardize ground beef and ground turkey across supermarket naming variations.
    Unifies lean/fat percentages, strips store brand prefixes and noise suffixes (Value Pack, Fresh, etc.).
    """
    c_lower = canonical.lower()

    # --- Ground Beef ---
    if "ground beef" in c_lower:
        is_patties = bool(re.search(r"\b(patties|burgers?)\b", c_lower))

        # Preserve premium specialized brands & gourmet blends (e.g. Schweid & Sons, Rastelli's, Wagyu)
        if brand and brand in ("Schweid & Sons", "Rastelli's"):
            return canonical, brand
        if any(k in c_lower for k in ("schweid", "rastelli", "wagyu", "meatloaf mix")):
            return canonical, brand

        # Extract lean percentage
        lean_pct = None
        m_pct = re.search(r"\b(73|80|85|90|93)(?:%|\s*%\s*lean|\s*/\s*\d+)?\b", canonical)
        if m_pct:
            lean_pct = m_pct.group(1)
        elif "80/20" in canonical or "20% fat" in c_lower:
            lean_pct = "80"
        elif "85/15" in canonical or "15% fat" in c_lower:
            lean_pct = "85"
        elif "90/10" in canonical or "10% fat" in c_lower:
            lean_pct = "90"
        elif "93/7" in canonical or "7% fat" in c_lower:
            lean_pct = "93"
        elif "73/27" in canonical or "27% fat" in c_lower:
            lean_pct = "73"

        suffix = " Patties" if is_patties else ""

        # Clear store brands and leaking beef grades on commodity ground beef
        if brand in ("Our Brand", "Giant", "Giant Brand", "Signature SELECT", "Signature Farms", "USDA Prime", "USDA Choice"):
            brand = None

        if lean_pct:
            return f"{lean_pct}% Lean Ground Beef{suffix}", brand
        return f"Ground Beef{suffix}", brand

    # --- Ground Turkey ---
    if "ground turkey" in c_lower:
        is_breast = "breast" in c_lower
        lean_pct = None
        m_pct = re.search(r"\b(85|90|93|99)(?:%|\s*%\s*lean|\s*/\s*\d+)?\b", canonical)
        if m_pct:
            lean_pct = m_pct.group(1)
        elif "99/1" in canonical or "1% fat" in c_lower:
            lean_pct = "99"
        elif "93/7" in canonical or "7% fat" in c_lower:
            lean_pct = "93"
        elif "85/15" in canonical or "15% fat" in c_lower:
            lean_pct = "85"

        is_organic = "organic" in c_lower
        org_prefix = "Organic " if is_organic else ""
        breast_suffix = " Breast" if is_breast else ""

        brand_prefix = f"{brand} " if brand and brand not in ("Our Brand", "Giant", "Giant Brand", "Signature SELECT", "Signature Farms") else ""

        if lean_pct:
            std_name = f"{brand_prefix}{org_prefix}{lean_pct}% Lean Ground Turkey{breast_suffix}".strip()
            return std_name, brand

    return canonical, brand


def apply_seasoning_standardization(canonical: str) -> str:
    """Standardize seasoning and mix packet names by stripping minor weight ranges."""
    if any(k in canonical.lower() for k in SEASONING_KEYWORDS):
        return UNIT_PATTERN.sub("", canonical).strip(" ,.-")
    return canonical


NON_SHELL_EGG_PATTERN = re.compile(
    r"\b(white|whites|salad|bites|liquid|noodles?|rolls?|waffles?|omelets?|quiche|deli|sub|sandwich|sandwiches|wrap|wraps|potato\s+salad|pasta\s+salad|food\s+color|dye|pickled|frittatas?|loaf|dog\s+food|cat\s+food|pet|treats?|skillet|bowl|creamer|butter)\b",
    re.IGNORECASE,
)
EGG_SIZE_GRADE_PATTERN = re.compile(r"\b(large|extra\s+large|jumbo|medium)\b", re.IGNORECASE)


def apply_egg_standardization(
    canonical: str,
    brand: Optional[str],
    size: Optional[float],
    unit: Optional[str],
    unit_price: Optional[float],
    item_price: Optional[float],
) -> Tuple[str, Optional[str], Optional[float], Optional[str], Optional[float]]:
    """
    Standardize shell egg products across all brands.
    - Normalizes 'Brand Eggs' -> 'Brand Large Eggs' when size grade is omitted.
    - Infers standard 1-dozen (12 ct) carton size when count is omitted in weekly circulars.
    - Excludes non-shell egg items (noodles, rolls, bites, salad, liquid whites).
    """
    # Shell eggs are never measured in ounces, pounds, or volume
    if unit in ("oz", "lb", "ml", "ltr", "gal", "qt", "pt"):
        return canonical, brand, size, unit, unit_price

    if re.search(r"\b(?<!['’])eggs?\b(?!['’])", canonical, re.IGNORECASE) and not NON_SHELL_EGG_PATTERN.search(canonical):
        if (brand == "Lucerne" or "lucerne" in canonical.lower()) and not canonical.lower().startswith("lucerne"):
            canonical = f"Lucerne {canonical}"
            brand = "Lucerne"

        # Standardize "Eggs" -> "Large Eggs" if grade/size omitted (standard supermarket table eggs)
        if not EGG_SIZE_GRADE_PATTERN.search(canonical):
            canonical = re.sub(r"\b(?<!['’])eggs?\b(?!['’])", "Large Eggs", canonical, flags=re.IGNORECASE)

        # In weekly circulars, standalone shell eggs without count is the standard 1-dozen (12 ct) carton
        if size is None and not re.search(r"\b\d+\s*ct\b", canonical, re.IGNORECASE):
            size = 12.0
            unit = "ct"
            canonical = f"{canonical} 12 ct"
            if item_price and size > 0:
                unit_price = round(item_price / size, 4)

    return canonical, brand, size, unit, unit_price


def apply_brand_specific_rules(
    canonical: str,
    brand: Optional[str],
    size: Optional[float],
    unit: Optional[str],
    unit_price: Optional[float],
    item_price: Optional[float],
    item_brands: List[str],
    item_name: str,
) -> Tuple[str, Optional[str], Optional[float], Optional[str], Optional[float]]:
    """
    Apply brand-specific canonicalization and packaging standardization rules.
    Returns (canonical, brand, size, unit, unit_price).
    """
    # Lay's Baked disambiguation
    if canonical.lower().startswith("baked ") and any("lay" in b.lower() for b in item_brands + [brand or "", item_name]):
        canonical = f"Lay's {canonical}"
        brand = "Lay's"

    # Josh / Josh Cellars wine
    if re.search(r"^Josh(?:\s+Cellars)?(?:\s+Wine)?$", canonical, re.IGNORECASE):
        canonical = "Josh Cellars Wine"
        brand = "Josh Cellars"
    elif re.search(r"\bJosh\s+Cellars\b", canonical, re.IGNORECASE):
        brand = "Josh Cellars"
    elif brand == "Josh":
        brand = "Josh Cellars"

    # Lucerne Cheese: unify standard 6-8 oz / 8 oz pack sizing
    if brand == "Lucerne" and "cheese" in canonical.lower():
        if not canonical.lower().startswith("lucerne"):
            canonical = f"Lucerne {canonical}"
        if re.search(r"\b(?:Shredded|Chunk|Sliced|Block\s+)?Cheese\s+8\s*oz\b", canonical, re.IGNORECASE):
            canonical = re.sub(r"\b8\s*oz\b", "6-8 oz", canonical, flags=re.IGNORECASE)
            size = 7.0
            unit = "oz"
            if item_price and size > 0:
                unit_price = round(item_price / size, 4)

    # Single-serve yogurt cups (Yoplait, Lucerne 4-6 oz)
    if re.search(r"\b(Yoplait|Lucerne)\s+Yogurt\b", canonical, re.IGNORECASE) and not re.search(r"\b(?:32|24|4\s*pack|4\s*pk)\b", canonical, re.IGNORECASE):
        brand_name = "Yoplait" if "yoplait" in canonical.lower() else "Lucerne"
        brand = brand_name
        canonical = f"{brand_name} Yogurt 4-6 oz"
        size = 5.0
        unit = "oz"
        if item_price and size > 0:
            unit_price = round(item_price / size, 4)

    # Multi-pack cream cheese weight resolution (Philadelphia Cream Cheese 2 Pack -> 16 oz)
    if "cream cheese" in canonical.lower() and (unit in ("pk", "pack", "ct", "count") or "2 pack" in canonical.lower() or "2 pk" in canonical.lower()):
        if size == 2.0 or (size is None and "2 pack" in canonical.lower()):
            size = 16.0
            unit = "oz"
            if item_price and size > 0:
                unit_price = round(item_price / size, 4)

    # Atlantic salmon portions (5 oz skinless)
    if re.search(r"\b(?:Fresh\s+)?(?:Atlantic\s+)?Salmon\s+Portions?\b", canonical, re.IGNORECASE) and not re.search(r"\b\d+\s*oz\b", canonical, re.IGNORECASE):
        canonical = "Fresh Atlantic Salmon Portions 5 oz Skinless"
        size = 5.0
        unit = "oz"
        if item_price and size > 0:
            unit_price = round(item_price / size, 4)

    # Cheap Chicken Monday deli promotion
    if re.search(r"\bcheap\s+chicken\b", canonical, re.IGNORECASE):
        canonical = "Cheap Chicken Monday 8 Piece Dark Meat"
        brand = "Signature Cafe"
        size = 8.0
        unit = "ct"
        if item_price:
            unit_price = round(item_price / 8.0, 4)

    # Velveeta Cheese Loaf: circular ad shorthand "Velveeta" -> 32 oz Loaf
    if canonical.lower() == "velveeta":
        canonical = "Velveeta Cheese Loaf 32 oz"
        brand = "Velveeta"
        size = 32.0
        unit = "oz"
        if item_price and size > 0:
            unit_price = round(item_price / size, 4)

    return canonical, brand, size, unit, unit_price


def apply_deli_or_meat_per_lb_fallback(
    canonical: str,
    brand: Optional[str],
    size: Optional[float],
    unit: Optional[str],
    unit_price: Optional[float],
    item_price: Optional[float],
    full_item_text: str,
) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """Deli counter cheese & meat / fresh butcher meat sold by the pound fallback."""
    if size is None and item_price:
        is_portion_or_unit = bool(re.search(r"\b(?:portions?|patt(?:y|ies)|cakes?|skewers?)\b", canonical, re.IGNORECASE))
        is_fresh_meat_cut = (
            not is_portion_or_unit
            and (
                "ground beef" in canonical.lower()
                or "ground turkey" in canonical.lower()
                or any(k in canonical.lower() for k in (
                    "boneless", "skinless", "bone-in", "fresh", "whole", "center cut",
                    "loin chop", "pork chop", "ribeye", "sirloin", "t-bone", "filet mignon",
                    "flank steak", "drumsticks", "tenders", "cutlets", "roast", "steak",
                    "chuck", "round", "ribs", "short rib", "brisket",
                ))
            )
            and any(k in canonical.lower() for k in ("chicken", "beef", "pork", "turkey", "salmon", "tilapia", "cod", "shrimp"))
        )
        if (
            brand in DELI_BRANDS
            or re.search(r"(?:per\s+lb|sold\s+by\s+the\s+lb|/\s*lb|\$?\d+(?:\.\d+)?\s*/?\s*lb\b)", full_item_text, re.IGNORECASE)
            or is_fresh_meat_cut
        ):
            size = 1.0
            unit = "lb"
            unit_price = round(item_price / 1.0, 4)

    return size, unit, unit_price
