"""
expander.py
Linguistic expansions for coordinated nouns, colors, variety lists, and multi-item deal strings.
"""

from typing import List
import re
from .units import UNIT_PATTERN

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
    splits = [s.strip() for s in SPLIT_PATTERN.split(chunk) if len(s.strip()) > 3]
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
