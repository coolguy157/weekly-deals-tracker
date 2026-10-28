"""
Circular ad grouping and multi-item promotion aggregation for weekly deals.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from .normalizer.cleaner import GENERIC_PLACEHOLDER_NAMES


@dataclass
class GroupedDeal:
    group_id: str
    title: str
    items: List[Any]
    representative: Any
    badge: str
    page_number: int
    pages: List[int]
    is_front_page: bool
    min_price: Optional[float]
    max_price: Optional[float]
    min_unit_price: Optional[float]
    max_unit_price: Optional[float]
    unit_type: Optional[str]
    varieties: List[str]
    category: Optional[str] = None
    brands: List[str] = field(default_factory=list)


def _get_item_attr(item: Any, attr: str, default: Any = None) -> Any:
    """Helper to access attribute from either an object or a dict."""
    if isinstance(item, dict):
        return item.get(attr, default)
    return getattr(item, attr, default)


def get_group_key(deal: Any) -> str:
    """Generate a stable group key to aggregate circular varieties into promotion families."""
    promo_detail = (_get_item_attr(deal, "promo_detail") or "").strip().lower()
    promo_type = _get_item_attr(deal, "promo_type", "standard") or "standard"
    page = _get_item_attr(deal, "page_number") or _get_item_attr(deal, "page") or 1

    # Weekly Meal Deal bundle check
    if promo_type == "meal_deal" or "meal deal" in promo_detail or "get these free" in promo_detail:
        return f"meal_deal_p{page}"

    ad_id = _get_item_attr(deal, "ad_id")
    if ad_id:
        return f"ad_{ad_id}"

    raw_id = str(_get_item_attr(deal, "raw_deal_id") or "")
    if len(raw_id) >= 11:
        return f"ad_{raw_id[:10]}"
    if raw_id and raw_id != "0":
        return f"raw_{raw_id}"

    ad_title = (_get_item_attr(deal, "ad_title") or "").strip()
    if ad_title and ad_title.lower() not in GENERIC_PLACEHOLDER_NAMES:
        clean_ad = re.sub(r"[^a-z0-9]", "", ad_title.lower())[:30]
        return f"adtitle_p{page}_{clean_ad}"

    brand = (_get_item_attr(deal, "brand") or "").strip().lower()
    if promo_detail and promo_detail not in ("standard", "(none)"):
        clean_p = re.sub(r"[^a-z0-9]", "", promo_detail)[:25]
        return f"promo_p{page}_{promo_type}_{clean_p}_{brand}"

    deal_id = _get_item_attr(deal, "deal_id")
    return f"deal_{deal_id}"


def clean_flyer_raw_title(title: str) -> str:
    """Clean flyer raw headline, stripping encoding artifacts, trademark symbols, and trailing promo/price tags."""
    if not title:
        return ""
    t = title.replace("\ufffd", "").replace("®", "").replace("™", "").strip()
    t = re.sub(r"\s+", " ", t)
    # Strip promo / price trailers like "- $3.99 /ea." or "- SAVE $15..." or "- $7.99 DIGITAL COUPON"
    t = re.sub(r"\s*-\s*(\$\d+(\.\d{2})?|\d+/\s*\$\d+|SAVE\s+\$\d+|DIGITAL\s+COUPON).*$", "", t, flags=re.I).strip()
    # Strip store brand prefixes on fresh meat & produce
    t = re.sub(r"^(?:Signature SELECT|Signature Farms|Our Brand|Giant Brand|Giant)\s*(?:Fresh\s+)?", "", t, flags=re.I).strip()
    # Strip value pack prefix
    t = re.sub(r"\bValue\s+Pack\s+", "", t, flags=re.I).strip()
    # Condense verbose poultry descriptions
    t = re.sub(r"\bBoneless\s+Skinless\s+Chicken\s+Breasts\b", "Chicken Breasts", t, flags=re.I)
    return t


def synthesize_group_title(items: List[Any]) -> str:
    """Synthesize a canonical ad promotion title from a group of circular items."""
    if not items:
        return "Unknown Deal"

    # 1. Prefer explicit canonical ad_title if published and not a placeholder
    for it in items:
        ad_t = (_get_item_attr(it, "ad_title") or "").strip()
        if ad_t and ad_t.lower() not in GENERIC_PLACEHOLDER_NAMES:
            return ad_t

    if len(items) == 1:
        return _get_item_attr(items[0], "canonical_name") or _get_item_attr(items[0], "name") or "Deal Item"

    # 2. Meal Deal bundle check
    promo_detail = (_get_item_attr(items[0], "promo_detail") or "").lower()
    if (
        any(_get_item_attr(it, "promo_type") == "meal_deal" for it in items)
        or "meal deal" in promo_detail
        or "get these free" in promo_detail
    ):
        return "Weekly Meal Deal"

    # 3. Check for shared concise raw flyer headline across items
    raw_titles = {
        clean_flyer_raw_title(_get_item_attr(it, "raw_title") or "")
        for it in items
        if (_get_item_attr(it, "raw_title") or "").strip()
    }
    raw_titles.discard("")
    shared_raw = list(raw_titles)[0] if len(raw_titles) == 1 else None
    if shared_raw:
        if (
            len(shared_raw) <= 120
            and shared_raw.count(",") <= 5
            and shared_raw.lower() not in GENERIC_PLACEHOLDER_NAMES
            and not re.match(r"^(?:select|assorted|various|mix\s*&\s*match)\b", shared_raw, re.I)
        ):
            words = shared_raw.split()
            if sum(1 for w in words if w.isupper()) >= 2 and all(
                w.isupper() or w.lower() in ("or", "and", "in", "of", "with", "a", "an", "the", "pc", "pk") for w in words
            ):
                shared_raw = " ".join(
                    w.lower() if w.lower() in ("or", "and", "in", "of", "with", "a", "an", "the") else w.capitalize()
                    for w in words
                )
            return shared_raw

    brands = sorted(list({_get_item_attr(it, "brand") for it in items if _get_item_attr(it, "brand")}))
    names = [_get_item_attr(it, "canonical_name") or _get_item_attr(it, "name") or "" for it in items]

    # 3. Multi-brand specialized categories
    if "Duncan Hines" in brands and "PAM" in brands:
        return "Duncan Hines & PAM • Cake Mixes, Frosting & Baking Spray"
    if "CareOne" in brands and "Nature's Promise" in brands:
        return "Nature's Promise & CareOne • Vitamins & Supplements"
    if "Floral" in brands or any(re.search(r"carnation|mum", n, re.I) for n in names):
        return "Floral • Carnations & Mums (Colors May Vary)"
    if "Martin's Snacks" in brands and "Nature's Own" in brands:
        return "Martin's Snacks & Nature's Own • Chips, Popcorn & Bread"

    has_seafood = (
        "Fresh Seafood" in brands
        or any(
            re.search(
                r"\b(?:fish|seafood|salmon|shrimp|tilapia|swordfish|tuna|haddock|swai|whiting|flounder)\b|(?<!cape\s)\bcod\b",
                n,
                re.I,
            )
            for n in names
        )
        or (
            any(re.search(r"\b(?:fillet|filet)s?\b", n, re.I) for n in names)
            and not any(re.search(r"pork|beef|chicken|turkey|steak|chop|loin|chip|pretzel|snack", n, re.I) for n in names)
        )
    )
    if has_seafood:
        return "Fresh & Frozen Seafood Fillets"

    # 4. Common grocery product types
    keywords = [
        "Soda", "Potato Chips", "Tortilla Chips", "Chips", "Cookies", "Cereal",
        "Sausage", "Bratwurst", "Brats", "Shampoo", "Lotion", "Bread", "Dressing",
        "Broth", "Crackers", "Water", "Tea", "Juice", "Vitamins", "Candy", "Dip",
        "Pasta", "Rice", "Ice Cream", "Coffee", "Cheese", "Spices", "Yogurt",
        "Snacks", "Sauce", "Chicken", "Beef", "Pork", "Fish", "Seafood", "Bacon",
    ]

    matched_keyword = None
    for kw in keywords:
        if all(kw.lower() in n.lower() for n in names):
            matched_keyword = kw
            break

    pkg = ""
    for p in ["12 pk", "6 pk", "8 pk", "15 ct", "Family Size", "Party Size", "1 Liter", "2 Liter"]:
        if all(p.lower() in n.lower() for n in names):
            pkg = f" ({p})"
            break

    if matched_keyword:
        if len(brands) == 1:
            return f"{brands[0]} {matched_keyword}{pkg}"
        elif len(brands) <= 3:
            return f"{', '.join(brands)} • {matched_keyword}{pkg}"
        else:
            return f"{brands[0]}, {brands[1]} & more • {matched_keyword}{pkg}"

    if len(brands) == 1:
        return f"{brands[0]} Assorted Varieties{pkg} ({len(items)} Items)"
    elif 2 <= len(brands) <= 3:
        return f"{', '.join(brands)} Selection{pkg} ({len(items)} Items)"
    elif len(brands) > 3:
        return f"{brands[0]}, {brands[1]} & more{pkg} ({len(items)} Items)"
    elif shared_raw:
        clean_raw = shared_raw[:60].rsplit(" ", 1)[0].strip(" ,.-")
        return f"{clean_raw}{pkg} ({len(items)} Varieties)"
    else:
        cats = sorted(list({_get_item_attr(it, "category") for it in items if _get_item_attr(it, "category")}))
        if len(cats) == 1:
            return f"Assorted {cats[0]}{pkg} ({len(items)} Items)"
        return f"Assorted Selection{pkg} ({len(items)} Items)"


def _deal_priority(it: Any) -> float:
    """Numerical priority score for selecting the representative deal for a group."""
    badge = (_get_item_attr(it, "badge") or "").upper()
    if badge == "POINTS_FREEBIE":
        return 0.0
    if badge == "NEW_ALL_TIME_LOW":
        return 1.0
    if badge == "MATCHES_ATL":
        return 2.0
    if badge == "ALL_TIME_LOW":
        return 3.0
    if _get_item_attr(it, "is_category_best", False):
        return 4.0
    if badge in ("POINTS_DEAL", "POINTS_REWARD"):
        return 5.0
    if badge == "SPEND_SAVE":
        return 6.0
    if badge == "PERCENT_OFF":
        return 7.0
    if badge == "BEAT_AVERAGE":
        return 8.0
    if badge == "CYCLE_REFRESH":
        return 9.0
    if badge == "STANDARD_DEAL":
        return 10.0
    if badge == "FIRST_SEEN":
        return 11.0
    if badge == "PRICE_HIKE":
        return 12.0
    if badge == "SEE_AD":
        return 13.0
    return 20.0


def should_split_ad_group(items: List[Any]) -> bool:
    """
    Determine if a multi-item ad tile should be split into discrete deal cards in the digest.

    Rules:
    1. NEVER split true promotional bundles or qualifying groups:
       - BXGY / BOGO (e.g. Buy 1 Get 1 Free)
       - Multi-Buys / Mix & Match (e.g. "when you buy 4", "must buy 3", "5 for $5")
       - Bundles / Meal Deals
    2. NEVER split packaged goods promotions or variety families:
       - Items sharing brand and category (e.g. Lucerne cheese chunks/shreds/slices)
       - Packaged grocery promotional collages (soups, pasta, snacks, sodas, etc.)
         with fixed packaging units (oz, ct, pk, count, etc., not sold per lb).
    3. DO split fresh butcher/seafood cuts sold by weight (per lb) or distinct animal protein cuts
       (e.g. Chicken Breasts vs Pork Loin Chops, or Chuck Roast vs Bottom Round Roast vs Short Ribs)
       where items have independent price baselines and differing deal evaluations.
    """
    if len(items) <= 1:
        return False

    # 1. Never split true promotional bundles (BXGY, BOGO, Multi-Buy, Mix & Match)
    for it in items:
        ptype = (_get_item_attr(it, "promo_type", "standard") or "standard").lower()
        pdetail = (_get_item_attr(it, "promo_detail", "") or "").lower()
        rtitle = (_get_item_attr(it, "raw_title", "") or "").lower()

        if ptype in ("bogo", "bxgy", "buy_x_get_y", "must_buy", "bundle", "meal_deal", "mix_and_match"):
            return False
        if (_get_item_attr(it, "qualifying_qty") or 1) > 1:
            return False
        if any(
            k in pdetail or k in rtitle
            for k in (
                "bogo", "buy 1 get", "buy 2 get", "buy one get", "get 1 free", "get one free",
                "when you buy", "must buy", "mix & match", "mix and match", "participating",
            )
        ):
            return False

    # 2. Never split packaged goods varieties (unit not 'lb')
    units = {_get_item_attr(it, "unit_type") for it in items if _get_item_attr(it, "unit_type")}
    if "lb" not in units:
        # Packaged consumer goods (soups, crackers, cheese packs, sodas, etc.) stay grouped
        return False

    # 3. For per-lb items (fresh meat, poultry, pork, beef, seafood):
    # Split if they represent distinct commodities or cuts
    canonical_names = {
        (_get_item_attr(it, "canonical_name") or _get_item_attr(it, "name") or "").strip()
        for it in items
    }
    canonical_names.discard("")
    if len(canonical_names) <= 1:
        return False

    # Check if items are fresh meat/poultry/seafood cuts
    meat_keywords = (
        "chicken", "breast", "breasts", "pork", "chop", "chops", "beef", "roast", "roasts",
        "steak", "steaks", "tenderloin", "rib", "ribs", "short rib", "chuck", "round",
        "salmon", "fillet", "fillets", "wings", "tenders", "meat", "poultry", "sirloin",
        "brisket", "loin"
    )
    is_meat_or_seafood = any(
        any(
            k in (_get_item_attr(it, "canonical_name", "") or "").lower()
            or k in (_get_item_attr(it, "category", "") or "").lower()
            for k in meat_keywords
        )
        for it in items
    )

    return is_meat_or_seafood


def group_evaluations(evaluations: List[Any]) -> List[GroupedDeal]:
    """
    Group a list of DealEvaluation objects or deal dictionaries into consolidated
    circular ad promotion groups.
    """
    groups_map: Dict[str, List[Any]] = defaultdict(list)
    for e in evaluations:
        key = get_group_key(e)
        existing = groups_map[key]
        name = _get_item_attr(e, "canonical_name") or _get_item_attr(e, "name")
        price = _get_item_attr(e, "current_price") or _get_item_attr(e, "price") or 0.0
        # Deduplicate identical items within the same ad tile
        if not any(
            (_get_item_attr(it, "canonical_name") or _get_item_attr(it, "name")) == name
            and abs((_get_item_attr(it, "current_price") or _get_item_attr(it, "price") or 0.0) - price) < 0.01
            for it in existing
        ):
            existing.append(e)

    # Merge redundant meal deal sub-ad tiles on the same page
    meal_deal_groups = {k: v for k, v in groups_map.items() if k.startswith("meal_deal_")}
    to_delete = []
    for k, items in groups_map.items():
        if k.startswith("meal_deal_"):
            continue
        for md_k, md_items in meal_deal_groups.items():
            match_count = sum(
                1
                for it in items
                if any(
                    (_get_item_attr(m, "canonical_name") or _get_item_attr(m, "name"))
                    == (_get_item_attr(it, "canonical_name") or _get_item_attr(it, "name"))
                    for m in md_items
                )
            )
            if items and match_count >= min(3, len(items)) and (match_count / len(items)) >= 0.7:
                for it in items:
                    it_name = _get_item_attr(it, "canonical_name") or _get_item_attr(it, "name")
                    if not any(
                        (_get_item_attr(m, "canonical_name") or _get_item_attr(m, "name")) == it_name
                        for m in md_items
                    ):
                        md_items.append(it)
                to_delete.append(k)
                break

    for k in to_delete:
        del groups_map[k]

    grouped_list: List[GroupedDeal] = []
    for k, items in groups_map.items():
        if should_split_ad_group(items):
            for idx, it in enumerate(items):
                cname = _get_item_attr(it, "canonical_name") or _get_item_attr(it, "name") or "Deal Item"
                price = (
                    _get_item_attr(it, "current_price")
                    if _get_item_attr(it, "current_price") is not None
                    else _get_item_attr(it, "price")
                )
                u_price = _get_item_attr(it, "unit_price")
                u_type = _get_item_attr(it, "unit_type")
                page = _get_item_attr(it, "page_number") or _get_item_attr(it, "page") or 1
                is_front = bool(_get_item_attr(it, "is_front_page"))
                badge = _get_item_attr(it, "badge") or "STANDARD_DEAL"
                cat = _get_item_attr(it, "category")
                brand = _get_item_attr(it, "brand")

                grouped_list.append(
                    GroupedDeal(
                        group_id=f"{k}_{idx}",
                        title=cname,
                        items=[it],
                        representative=it,
                        badge=badge,
                        page_number=page,
                        pages=[page],
                        is_front_page=is_front,
                        min_price=price,
                        max_price=price,
                        min_unit_price=u_price,
                        max_unit_price=u_price,
                        unit_type=u_type,
                        varieties=[cname],
                        category=cat,
                        brands=[brand] if brand else [],
                    )
                )
            continue

        title = synthesize_group_title(items)

        # Prices
        prices = [
            _get_item_attr(it, "current_price")
            if _get_item_attr(it, "current_price") is not None
            else _get_item_attr(it, "price")
            for it in items
        ]
        valid_prices = [p for p in prices if p is not None]

        # Unit Prices
        unit_types = [_get_item_attr(it, "unit_type") for it in items if _get_item_attr(it, "unit_type")]
        primary_unit_type = None
        if unit_types:
            # Most common unit type
            counts: Dict[str, int] = defaultdict(int)
            for u in unit_types:
                counts[u] += 1
            primary_unit_type = max(counts.keys(), key=lambda x: counts[x])

        matching_unit_prices = [
            _get_item_attr(it, "unit_price")
            for it in items
            if _get_item_attr(it, "unit_type") == primary_unit_type and _get_item_attr(it, "unit_price") is not None
        ]

        # Select representative deal: lowest priority number = highest signal
        sorted_by_signal = sorted(items, key=_deal_priority)
        representative = sorted_by_signal[0]

        # Handle headline price for meal deal
        is_meal_deal = (
            k.startswith("meal_deal_")
            or _get_item_attr(representative, "promo_type") == "meal_deal"
            or "meal deal" in title.lower()
        )
        if is_meal_deal and valid_prices:
            # Anchor price is highest priced qualifying item
            min_p = max(valid_prices)
            max_p = max(valid_prices)
        else:
            min_p = min(valid_prices) if valid_prices else None
            max_p = max(valid_prices) if valid_prices else None

        min_up = min(matching_unit_prices) if matching_unit_prices else None
        max_up = max(matching_unit_prices) if matching_unit_prices else None

        pages = sorted(
            list(
                {
                    _get_item_attr(it, "page_number") or _get_item_attr(it, "page")
                    for it in items
                    if (_get_item_attr(it, "page_number") or _get_item_attr(it, "page")) is not None
                }
            )
        )
        is_front = any(bool(_get_item_attr(it, "is_front_page")) for it in items)

        unique_vars = sorted(
            list(
                {
                    _get_item_attr(it, "canonical_name") or _get_item_attr(it, "name")
                    for it in items
                    if (_get_item_attr(it, "canonical_name") or _get_item_attr(it, "name"))
                }
            )
        )
        brands = sorted(list({_get_item_attr(it, "brand") for it in items if _get_item_attr(it, "brand")}))
        cat = _get_item_attr(representative, "category") or _get_item_attr(items[0], "category")

        grouped_list.append(
            GroupedDeal(
                group_id=k,
                title=title,
                items=items,
                representative=representative,
                badge=_get_item_attr(representative, "badge") or "STANDARD_DEAL",
                page_number=pages[0] if pages else 1,
                pages=pages,
                is_front_page=is_front,
                min_price=min_p,
                max_price=max_p,
                min_unit_price=min_up,
                max_unit_price=max_up,
                unit_type=primary_unit_type,
                varieties=unique_vars,
                category=cat,
                brands=brands,
            )
        )

    # Default sort by representative signal priority, then front page, then min_price
    grouped_list.sort(
        key=lambda g: (
            0 if g.is_front_page else 1,
            _deal_priority(g.representative),
            g.min_price if g.min_price is not None else 999999,
        )
    )
    return grouped_list
