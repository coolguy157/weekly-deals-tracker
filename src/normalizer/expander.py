"""
expander.py
Linguistic expansions for coordinated nouns, colors, variety lists, and multi-item deal strings.
"""

from typing import List
import re
from .units import UNIT_PATTERN
from .vocabulary import (
    STORE_BRANDS,
    NATIONAL_BRANDS,
    COMMON_HEAD_NOUNS_PATTERN,
    KNOWN_HEAD_NOUN_WORDS,
    FOOD_KEYWORDS,
)

ALL_PREFIX_BRANDS = STORE_BRANDS + [b for b in NATIONAL_BRANDS if b not in STORE_BRANDS]

# Disaggregation delimiters (e.g. "Item A, Item B or Item C")
SPLIT_PATTERN = re.compile(r"\s+or\s+|\s*,\s*(?=[A-Z0-9])", re.IGNORECASE)

# Coordinated meat/poultry cut patterns where a shared prefix/suffix applies to both
COORD_PATTERN = re.compile(
    r"^(.*?)\b(Breasts|Thighs|Drumsticks|Wings|Tenders|Tenderloins|Pork Chops|Pork Loin Chops|Pork Spare Ribs|Whole Chickens)\s+or\s+(Breasts|Thighs|Drumsticks|Wings|Tenders|Tenderloins|Pork Chops|Pork Loin Chops|Pork Spare Ribs|Whole Chickens)\b(.*)$",
    re.IGNORECASE,
)

# Produce color/variety coordinated patterns: e.g. "Red or Green Grapes", "Yellow or Zucchini Squash"
COLOR_OR_NOUN_PATTERN = re.compile(
    r"^(.*?)\b(Red|Green|Yellow|Zucchini|Black|White|Seedless|Baking|Sweet|Russet)\s+or\s+(Red|Green|Yellow|Zucchini|Black|White|Seedless|Baking|Sweet|Russet)\s+(Grapes?|Squash|Potato(?:es)?|Apple(?:s)?|Pear(?:s)?|Onion(?:s)?|Pepper(?:s)?)\b(.*)$",
    re.IGNORECASE,
)

# Prefix coordination for packaged items: e.g. "Premier Protein Frozen Pancakes or Waffles"
PREFIX_COORD_PATTERN = re.compile(
    r"^(.*?\b(?:Frozen|Protein|Organic|Natural|Fresh))\s+(Pancakes|Waffles|Bars|Treats|Burgers|Pizzas)\s+or\s+(Pancakes|Waffles|Bars|Treats|Burgers|Pizzas)\b(.*)$",
    re.IGNORECASE,
)

# Coordinated adjective/cut styles for cheese, produce, or meat: e.g. "Shredded or Chunk Cheese"
ADJECTIVE_OR_NOUN_PATTERN = re.compile(
    r"^(.*?)\b(Shredded|Chunk|Sliced|Block|String|Grated|Crumbled|Whole|Diced|Crushed|Salted|Unsalted)\s+or\s+(Shredded|Chunk|Sliced|Block|String|Grated|Crumbled|Whole|Diced|Crushed|Salted|Unsalted)\s+(Cheese|Cheddar|Mozzarella|Swiss|Provolone|Baby\s+Bella\s+Mushrooms|Mushrooms|Tomato(?:es)?|Butter|Potato(?:es)?)\b(.*)$",
    re.IGNORECASE,
)


def expand_chunk(chunk: str) -> List[str]:
    """Expand a single chunk, handling coordinated patterns like 'Breasts or Thighs' or simple 'or' splits."""
    chunk = re.sub(r"^(?:or|and)\s+", "", chunk.strip(), flags=re.IGNORECASE).strip(" ,.-")
    if not chunk:
        return []

    # 1. Check color/variety noun: "O Organics Red or Green Grapes" or "Yellow or Zucchini Squash"
    color_match = COLOR_OR_NOUN_PATTERN.match(chunk)
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
            for sub in expand_chunk(post):
                results.append(sub)
        return results

    # 2. Check adjective/cut noun: "Our Brand Shredded or Chunk Cheese"
    adj_match = ADJECTIVE_OR_NOUN_PATTERN.match(chunk)
    if adj_match:
        pre = adj_match.group(1).strip()
        p_str = f"{pre} " if pre else ""
        o1 = adj_match.group(2).strip()
        o2 = adj_match.group(3).strip()
        noun = adj_match.group(4).strip()
        post = adj_match.group(5).strip()
        item1 = f"{p_str}{o1} {noun}".strip()
        item2 = f"{p_str}{o2} {noun}".strip()
        results = [item1, item2]
        if post:
            for sub in expand_chunk(post):
                results.append(sub)
        return results

    # 2. Check prefix coordination: "Premier Protein Frozen Pancakes or Waffles"
    pref_match = PREFIX_COORD_PATTERN.match(chunk)
    if pref_match:
        prefix = pref_match.group(1).strip()
        opt1 = pref_match.group(2).strip()
        opt2 = pref_match.group(3).strip()
        suffix = pref_match.group(4).strip()
        return [f"{prefix} {opt1} {suffix}".strip(), f"{prefix} {opt2} {suffix}".strip()]

    # 3. Check meat cut coordination
    coord_match = COORD_PATTERN.match(chunk)
    if coord_match:
        prefix = coord_match.group(1).strip()
        opt1 = coord_match.group(2).strip()
        opt2 = coord_match.group(3).strip()
        suffix = coord_match.group(4).strip()

        prefix_splits = [s.strip() for s in SPLIT_PATTERN.split(prefix) if len(s.strip()) > 3]
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
    splits = [s.strip() for s in SPLIT_PATTERN.split(chunk) if len(s.strip()) >= 3]
    if len(splits) > 1:
        all_expanded = []
        for s in splits:
            all_expanded.extend(expand_chunk(s))
        return all_expanded

    return [chunk]


def pre_expand_deal_string(name: str) -> str:
    """Pre-process and expand compound lists (produce suffixes/prefixes, cheese combos, brand pairs)."""
    cleaned_name = name

    # Simplify packaging options "Cans or Bottles" -> "Cans/Bottles"
    cleaned_name = re.sub(r"\b(?:Cans|Bottles)\s+or\s+(?:Bottles|Cans)\b", "Cans/Bottles", cleaned_name, flags=re.IGNORECASE)

    # Generalized Poultry cut coordination: e.g. "<Prefix> Chicken Breasts, Thin Sliced or Tenders" or "... Breasts, Thighs or Drumsticks"
    def _expand_poultry_cuts(m):
        prefix = m.group(1).strip()
        c2 = m.group(2).strip()
        c3 = m.group(3).strip()
        base = re.sub(
            r"\b(?:Boneless\s+Skinless|Boneless|Bone-In)?\s*(?:Chicken\s+Breasts?|Whole\s+Chickens?|Breasts?)\b",
            "",
            prefix,
            flags=re.IGNORECASE,
        ).strip()
        b_str = f"{base} " if base else ""
        item1 = prefix
        if "thin" in c2.lower():
            p_prefix = prefix.replace("Chicken Breasts", "").replace("Breasts", "").strip()
            item2 = f"{p_prefix} Thin Sliced Chicken Breasts".strip()
            item2 = " ".join(item2.split())
        else:
            item2 = f"{b_str}Chicken {c2}".strip()
        item3 = f"{b_str}Chicken {c3}".strip()
        return f"{item1} or {item2} or {item3}"

    cleaned_name = re.sub(
        r"\b([A-Za-z0-9'\s]+?\b(?:Fresh\s+)?(?:Chicken\s+)?(?:Breasts?|Whole\s+Chickens?)),\s*(Thin\s+Sliced(?:\s+Breasts?)?|Thighs|Drumsticks|Wings|Tenders|Cutlets)\s+or\s+(Thighs|Drumsticks|Wings|Tenders|Cutlets)\b",
        _expand_poultry_cuts,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # Boundary between Greenhouse Grown and next brand if missing comma (common in Giant circulars)
    cleaned_name = re.sub(
        r"\b(Greenhouse\s+Grown)\s+(Dole|Bolthouse|NatureSweet|Fresh\s+Express|Taylor\s+Farms|Our\s+Brand|Earthbound\s+Farm)\b",
        r"\1, \2",
        cleaned_name,
        flags=re.IGNORECASE,
    )

    salad_brand_pat = r"(?:(?!or\b|and\b|Salad\b|Blend\b|Kit\b|Bowl\b)[A-Za-z0-9'&]+(?:\s+(?!or\b|and\b|Salad\b|Blend\b|Kit\b|Bowl\b)[A-Za-z0-9'&]+)*)"
    salad_compound_pat = r"(?:Salad\s+(?:Blends?|Kits?|Bowls?)(?:\s+or\s+(?:Salad\s+)?(?:Blends?|Kits?|Bowls?))?|(?:Salad\s+)?(?:Blends?|Kits?|Bowls?)\s+or\s+(?:Salad\s+)?(?:Blends?|Kits?|Bowls?)|Salad\s+(?:Blends?|Kits?|Bowls?))"

    def _protect_or(s: str) -> str:
        return re.sub(r"\s+or\s+", "__OR__", s, flags=re.IGNORECASE)

    # 3-item salad list: "Brand1, Brand2 or Brand3 Salad Blend or Kit"
    def _expand_salad_trio(m):
        b1 = m.group(1).strip()
        b2 = m.group(2).strip()
        b3 = m.group(3).strip()
        suf = _protect_or(m.group(4).strip())
        return f"{b1} {suf} or {b2} {suf} or {b3} {suf}"

    cleaned_name = re.sub(
        rf"\b({salad_brand_pat}),\s*({salad_brand_pat})\s+or\s+({salad_brand_pat})\s+({salad_compound_pat})\b",
        _expand_salad_trio,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # 2-item salad pair: "Dole or Our Brand Salad Blend or Kit"
    def _expand_salad_pair(m):
        b1 = m.group(1).strip()
        b2 = m.group(2).strip()
        suf = _protect_or(m.group(3).strip())
        return f"{b1} {suf} or {b2} {suf}"

    cleaned_name = re.sub(
        rf"\b({salad_brand_pat})\s+or\s+({salad_brand_pat})\s+({salad_compound_pat})\b",
        _expand_salad_pair,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # -------------------------------------------------------------------------
    # Generalized Right-Distribution: Shared Head Noun over Coordinated Modifiers
    # [Prefix] M1, M2 or M3 <HeadNoun> [Size] -> Prefix M1 HeadNoun or ...
    # [Prefix] M1 or M2 <HeadNoun> [Size] -> Prefix M1 HeadNoun or ...
    # Replaces specialized helpers (_expand_cheese_list*, _expand_suffix_*, _expand_sausage_*, etc.)
    # -------------------------------------------------------------------------
    _SIZE_SUFFIX = r"(?:\s+((?:(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?)\s*(?:oz|ounce|lb|pound|ct|count|pk|pack|qt|pt|gal)\.?))?"

    # Pre-pass: Coordinated 2-word prep adjectives over compound commodity noun phrases
    # e.g. "Sliced or Whole White Mushrooms", "Our Brand Whole or Sliced Baby Bella Mushrooms", "Yogurt or Oatmeal parfaits"
    def _expand_coord_prep_produce(m):
        prefix = m.group(1).strip()
        p_str = f"{prefix} " if prefix else ""
        v1, v2, noun = m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
        return f"{p_str}{v1} {noun} or {p_str}{v2} {noun}"

    cleaned_name = re.sub(
        r"\b((?:(?!or\b|and\b)[A-Za-z0-9'\-]+\s+)??)([A-Za-z]+)\s+or\s+([A-Za-z]+)\s+((?:Baby\s+Bella\s+|White\s+|Portabella\s+|Button\s+)?(?:parfaits?|mushrooms?|crusts?|tortillas?))\b",
        _expand_coord_prep_produce,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # Generalized 3-item shared head noun expansion
    def _expand_shared_head_noun_trio(m):
        prefix = m.group(1).strip()
        v1, v2, v3, noun = m.group(2).strip(), m.group(3).strip(), m.group(4).strip(), m.group(5).strip()
        size = m.group(6).strip() if m.group(6) else ""
        s_str = f" {size}" if size else ""

        if UNIT_PATTERN.search(v1) or UNIT_PATTERN.search(v2) or UNIT_PATTERN.search(v3):
            return m.group(0)
        if prefix:
            p_last = prefix.strip().split()[-1].lower()
            if p_last in KNOWN_HEAD_NOUN_WORDS or (p_last.endswith("s") and p_last[:-1] in KNOWN_HEAD_NOUN_WORDS):
                return m.group(0)
        for v in (v1, v2, v3):
            v_last = v.split()[-1].lower() if v else ""
            if v_last in KNOWN_HEAD_NOUN_WORDS or (v_last.endswith("s") and v_last[:-1] in KNOWN_HEAD_NOUN_WORDS):
                return m.group(0)

        p_brand = prefix
        for b in ALL_PREFIX_BRANDS:
            if v1.lower().startswith(b.lower() + " "):
                p_brand = b
                v1 = v1[len(b):].strip()
                break
        p_str = f"{p_brand} " if p_brand else ""
        return f"{p_str}{v1} {noun}{s_str} or {p_str}{v2} {noun}{s_str} or {p_str}{v3} {noun}{s_str}"

    var_token_3 = r"(?:(?!or\b|and\b)[A-Za-z0-9'\-]+(?:\s+(?!or\b|and\b)[A-Za-z0-9'\-]+)?)"
    cleaned_name = re.sub(
        rf"\b((?:(?!or\b|and\b)[A-Za-z0-9'\-]+\s+)??)({var_token_3}),\s*({var_token_3})\s+or\s+({var_token_3})\s+({COMMON_HEAD_NOUNS_PATTERN}){_SIZE_SUFFIX}\b",
        _expand_shared_head_noun_trio,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # Generalized 2-item shared head noun expansion
    def _expand_shared_head_noun_pair(m):
        prefix = m.group(1).strip()
        v1, v2, noun = m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
        size = m.group(5).strip() if m.group(5) else ""
        s_str = f" {size}" if size else ""

        if UNIT_PATTERN.search(v1) or UNIT_PATTERN.search(v2):
            return m.group(0)
        if prefix:
            p_last = prefix.strip().split()[-1].lower()
            if p_last in KNOWN_HEAD_NOUN_WORDS or (p_last.endswith("s") and p_last[:-1] in KNOWN_HEAD_NOUN_WORDS):
                return m.group(0)

        v1_last = v1.split()[-1].lower() if v1 else ""
        if v1_last in KNOWN_HEAD_NOUN_WORDS or (v1_last.endswith("s") and v1_last[:-1] in KNOWN_HEAD_NOUN_WORDS):
            return m.group(0)
        v2_last = v2.split()[-1].lower() if v2 else ""
        if v2_last in KNOWN_HEAD_NOUN_WORDS or (v2_last.endswith("s") and v2_last[:-1] in KNOWN_HEAD_NOUN_WORDS):
            return m.group(0)

        # Propagate brand/prefix to v2 if v1 starts with brand and v2 does not
        p_brand = prefix
        for b in ALL_PREFIX_BRANDS:
            if (prefix.lower().startswith(b.lower()) or v1.lower().startswith(b.lower())) and not v2.lower().startswith(b.lower()):
                p_brand = b
                if v1.lower().startswith(b.lower()):
                    rem = v1[len(b):].strip()
                    rem_w = rem.split()
                    v1 = " ".join(rem_w)
                    if len(rem_w) > 1:
                        adj = " ".join(rem_w[:-1])
                        v2 = f"{adj} {v2}".strip()
                break

        p_str = f"{p_brand} " if p_brand else ""
        return f"{p_str}{v1} {noun}{s_str} or {p_str}{v2} {noun}{s_str}"

    var_token_2 = r"(?:(?!or\b|and\b)[A-Za-z0-9'\-]+(?:\s+(?!or\b|and\b)[A-Za-z0-9'\-]+)?)"
    cleaned_name = re.sub(
        rf"\b((?:(?!or\b|and\b)[A-Za-z0-9'\-]+\s+)??)({var_token_2})\s+or\s+({var_token_2})\s+({COMMON_HEAD_NOUNS_PATTERN}){_SIZE_SUFFIX}\b",
        _expand_shared_head_noun_pair,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # Expand unit alternatives with shared brand prefix: e.g. "Oxiclean 3 lb. or 24 ct." -> "Oxiclean 3 lb. or Oxiclean 24 ct."
    cleaned_name = re.sub(
        r"\b([A-Za-z0-9'\s]+?\b)\s+((?:\d+(?:\.\d+)?|\.\d+)\s*(?:lb|oz|ct|count|pk|pack|qt|pt|gal)\.?)\s+or\s+((?:\d+(?:\.\d+)?|\.\d+)\s*(?:lb|oz|ct|count|pk|pack|qt|pt|gal)\.?)\b",
        r"\1 \2 or \1 \3",
        cleaned_name,
        flags=re.IGNORECASE,
    )

    # Expand produce prefix lists: "Baby Potatoes Red, Gold or Medley" or "New Crop Pears Bartlett, Red, Bosc or Danjou"
    def _expand_prefix_list(m):
        prefix = m.group(1).strip()
        v_comma = m.group(2).strip()
        v_last = m.group(3).strip()
        parts = [p.strip() for p in v_comma.split(",") if p.strip()] + [v_last]
        return " or ".join(f"{prefix} {p}" for p in parts)

    _prod_nouns = "Apples|Potatoes|Grapes|Pears|Citrus|Squash|Tomatoes|Onions|Peppers"
    _var_tok = r"(?:(?!or\b|and\b|" + _prod_nouns + r")[A-Za-z0-9']+(?:\s+(?!or\b|and\b|" + _prod_nouns + r")[A-Za-z0-9']+)?)"
    _prefix_pat = rf"\b((?:[A-Za-z0-9']+\s+)*(?:Apples|Potatoes|Grapes|Pears|Citrus|Squash))\s+({_var_tok}(?:,\s*{_var_tok})+)\s+or\s+({_var_tok})\b"

    cleaned_name = re.sub(
        _prefix_pat,
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

    # Expand brand pair with shared size: "Doritos, Tostitos 6-13 oz" or "Lays or Cheetos 8-15 oz"
    def _expand_brand_size(m):
        b1 = m.group(1).strip()
        b2 = m.group(2).strip()
        size = m.group(3).strip()
        if any(w.lower() in FOOD_KEYWORDS for w in b1.split() + b2.split()):
            return m.group(0)
        if len(b1.split()) > 2 or len(b2.split()) > 2:
            return m.group(0)
        if not UNIT_PATTERN.search(b1) and len(b1) > 2 and len(b2) > 2:
            return f"{b1} {size}, {b2} {size}"
        return m.group(0)

    cleaned_name = re.sub(
        r"\b([A-Za-z0-9'\s]+?)(?:\s+or\s+|\s*,\s*)([A-Za-z0-9'\s]+?)\s+((?:(?:\d+(?:\.\d+)?|\.\d+)(?:\s*-\s*(?:\d+(?:\.\d+)?|\.\d+))?)\s*(?:oz|ounce|lb|pound|ct|count|pk|pack|ltr|liter|quart|qt|pint|pt|gal|gallon|ml)\b[^\,]*?)(?=\s+or\s+[A-Z]|,\s*[A-Z]|$)",
        _expand_brand_size,
        cleaned_name,
        flags=re.IGNORECASE,
    )

    return cleaned_name
