"""
Terminal formatting, ANSI color rendering, and deal card/digest presentation.
"""

import re
import shutil
from typing import List, Optional, Dict, Any

from .grouping import group_evaluations, GroupedDeal


def clean_repeated_promo(s: Optional[str]) -> Optional[str]:
    """Clean duplicated or repetitive promo strings (e.g. TalkBack duplicated accessibility text)."""
    if not s:
        return s
    cleaned = s.strip()
    words = cleaned.split()
    n = len(words)
    if n >= 4 and n % 2 == 0:
        half = n // 2
        if [w.lower() for w in words[:half]] == [w.lower() for w in words[half:]]:
            cleaned = " ".join(words[:half])

    # Pattern: "When You Buy 6 or More 10% OFF When You Buy 6 or More"
    m = re.match(r"^(.*?)\s+(10%\s*OFF|\$\d+(?:\.\d{2})?\s*OFF|\d+%\s*OFF)\s+\1$", cleaned, flags=re.I)
    if m:
        cleaned = f"{m.group(2)} {m.group(1)}"

    return cleaned


def format_badge_fixed(badge: str, width: int = 16) -> str:
    """Format deal badge with ANSI terminal color and fixed-width padding."""
    raw_labels = {
        "NEW_ALL_TIME_LOW": "[🔥 NEW ATL]",
        "MATCHES_ATL": "[⭐ MATCH ATL]",
        "ALL_TIME_LOW": "[* ALL-TIME LOW]",
        "POINTS_FREEBIE": "[🪙 FREEBIE]",
        "POINTS_DEAL": "[🪙 POINTS DEAL]",
        "POINTS_REWARD": "[🪙 REWARD]",
        "POINTS_REDEMPTION": "[🪙 REDEEM]",
        "SPEND_SAVE": "[🏷️ SPEND & SAVE]",
        "PERCENT_OFF": "[% DISCOUNT]",
        "BEAT_AVERAGE": "[^ BEAT AVERAGE]",
        "CYCLE_REFRESH": "[~ CYCLE REFRESH]",
        "FIRST_SEEN": "[+ FIRST SEEN]",
        "STANDARD_DEAL": "[DEAL]",
        "PRICE_HIKE": "[! PRICE HIKE]",
        "SEE_AD": "[SEE AD]",
    }
    raw = raw_labels.get(badge, f"[{badge}]")
    padded = f"{raw:<{width}}"

    color_map = {
        "NEW_ALL_TIME_LOW": "\033[91m",
        "MATCHES_ATL": "\033[93m",
        "ALL_TIME_LOW": "\033[92m",
        "POINTS_FREEBIE": "\033[95m",
        "POINTS_DEAL": "\033[95m",
        "POINTS_REWARD": "\033[95m",
        "POINTS_REDEMPTION": "\033[94m",
        "SPEND_SAVE": "\033[93m",
        "PERCENT_OFF": "\033[96m",
        "BEAT_AVERAGE": "\033[96m",
        "CYCLE_REFRESH": "\033[94m",
        "FIRST_SEEN": "\033[93m",
        "STANDARD_DEAL": "\033[90m",
        "PRICE_HIKE": "\033[91m",
        "SEE_AD": "\033[90m",
    }
    color = color_map.get(badge, "")
    reset = "\033[0m" if color else ""
    return f"{color}{padded}{reset}"


def format_badge(badge: str) -> str:
    """Format deal badge with ANSI terminal color and dynamic width."""
    return format_badge_fixed(badge, width=0)


def format_unit_price(unit_price: Optional[float], unit_type: Optional[str]) -> str:
    """Format unit price cleanly (e.g. '$0.16/oz', '$7.99/lb', '$0.25/ct')."""
    if unit_price is None or not unit_type:
        return ""
    if unit_price < 0.10:
        return f"${unit_price:.3f}/{unit_type}"
    return f"${unit_price:.2f}/{unit_type}"


def get_compact_tags(ev: Any) -> List[str]:
    """Return ordered list of compact signal tags for single-line display."""
    tags = []

    # Promo Tag (BOGO, Must Buy, Digital Coupon, Points, Spend & Save, Percent Off)
    promo_type = getattr(ev, "promo_type", "standard")
    promo_detail = clean_repeated_promo(getattr(ev, "promo_detail", None))
    # Suppress zero-value freebie artifacts like 'BUY 1 GET 0 FREE'
    if promo_detail and "get 0 free" in promo_detail.lower():
        promo_detail = None
    base_price = getattr(ev, "base_price", None)
    if promo_type == "bogo" and promo_detail:
        base_str = f" (Base ${base_price:.2f})" if base_price else ""
        tags.append(f"🎁 {promo_detail}{base_str}")
    elif promo_type == "must_buy" and promo_detail:
        tags.append(f"📦 {promo_detail}")
    elif promo_type == "digital_coupon" and promo_detail:
        tags.append(f"🎟️ {promo_detail}")
    elif promo_type in ("points_redemption", "points_bonus") and promo_detail:
        tags.append(f"🪙 {promo_detail}")
    elif promo_type == "spend_save" and promo_detail:
        tags.append(f"🏷️ {promo_detail}")
    elif promo_type == "percent_off" and promo_detail:
        tags.append(f"🏷️ {promo_detail}")

    # Category Best / Category context
    if getattr(ev, "is_category_best", False):
        tags.append("🏆 Cat Best")
    elif getattr(ev, "category_avg_unit_price", None) and getattr(ev, "unit_price", None):
        cat_avg = ev.category_avg_unit_price
        if ev.unit_price <= cat_avg * 0.85:
            pct = round(((cat_avg - ev.unit_price) / cat_avg) * 100)
            tags.append(f"🔥 -{pct}% cat avg")
        elif ev.unit_price > cat_avg * 1.15:
            pct = round(((ev.unit_price - cat_avg) / cat_avg) * 100)
            tags.append(f"⚠️ +{pct}% cat avg")

    # Historical price note
    badge = getattr(ev, "badge", "")
    historical_min = getattr(ev, "historical_min", None)
    current_price = getattr(ev, "current_price", None)
    if current_price is None:
        current_price = getattr(ev, "price", None)
    summary_reason = getattr(ev, "summary_reason", "")

    if badge in ("ALL_TIME_LOW", "NEW_ALL_TIME_LOW", "MATCHES_ATL"):
        if historical_min and current_price and current_price < (historical_min - 0.005):
            pct = round(((historical_min - current_price) / historical_min) * 100)
            tags.append(f"🌟 -{pct}% ATL")
        elif "Matches" in summary_reason or (historical_min and abs((current_price or 0) - historical_min) <= 0.005):
            tags.append("🌟 Matches ATL")
        else:
            tags.append("🌟 ATL")
    elif badge == "PRICE_HIKE":
        diff_pct = getattr(ev, "diff_pct_vs_avg", None)
        if diff_pct:
            tags.append(f"⚠️ +{round(diff_pct)}% vs avg")
        else:
            tags.append("⚠️ Price Hike")
    elif badge == "BEAT_AVERAGE":
        diff_pct = getattr(ev, "diff_pct_vs_avg", None)
        if diff_pct:
            tags.append(f"🔥 {round(diff_pct)}% vs avg")
    elif badge == "CYCLE_REFRESH":
        if "multi-week" in summary_reason.lower():
            tags.append("🔄 Multi-week")

    return tags


def format_compact_note(ev: Any) -> str:
    """Format a concise, high-signal annotation tag for clean single-line display."""
    tags = get_compact_tags(ev)
    if not tags:
        return ""

    color = "\033[91m" if getattr(ev, "badge", "") == "PRICE_HIKE" else "\033[92m"
    reset = "\033[0m"
    return f"  {color}↳ " + " • ".join(tags) + reset


def print_deal_card(ev: Any, verbose: bool = False) -> None:
    """Print a single deal observation with formatted badge and inline metadata."""
    badge_str = format_badge_fixed(ev.badge, width=16)
    if ev.badge == "POINTS_FREEBIE" or getattr(ev, "promo_type", "") == "points_redemption":
        price_str = "   FREE"
    elif ev.current_price is not None:
        price_str = f"${ev.current_price:.2f}"
    else:
        price_str = " See ad"
    page_str = f"p.{ev.page_number}" + (" (Cover)" if ev.is_front_page else "")

    # Deduplicate brand tag if brand is already part of canonical product name
    brand_str = ""
    if ev.brand and ev.brand.lower() not in ev.canonical_name.lower():
        brand_str = f" [{ev.brand}]"

    u_str = format_unit_price(getattr(ev, "unit_price", None), getattr(ev, "unit_type", None))
    unit_str = f" ({u_str})" if u_str else ""

    if verbose:
        print(f" {badge_str}  {price_str:>7}  {ev.canonical_name}{brand_str}{unit_str} ({page_str})")
        print(f"   ↳ {ev.summary_reason}\n")
    else:
        try:
            term_width = max(80, shutil.get_terminal_size(fallback=(100, 24)).columns)
        except Exception:
            term_width = 100
        target_width = max(76, term_width - 3)

        tags = get_compact_tags(ev)
        base_overhead = 1 + 16 + 2 + 7 + 2 + len(brand_str) + len(unit_str) + len(f" ({page_str})")
        avail = target_width - base_overhead

        name = ev.canonical_name
        avail_for_tags = avail - min(len(name), 35)
        cur_tag_str = ""
        for t in tags:
            candidate = (cur_tag_str + " • " + t) if cur_tag_str else t
            if len(candidate) + 4 <= avail_for_tags:
                cur_tag_str = candidate
            elif not cur_tag_str and len(t) + 4 <= avail - 20:
                cur_tag_str = t
                break
            else:
                break

        tag_str = ""
        tag_len = 0
        if cur_tag_str:
            color = "\033[91m" if ev.badge == "PRICE_HIKE" else "\033[92m"
            tag_str = f"  {color}↳ {cur_tag_str}\033[0m"
            tag_len = len(cur_tag_str) + 4

        avail_name = target_width - base_overhead - tag_len
        if len(name) > avail_name and avail_name > 10:
            name = name[:avail_name - 1].rstrip() + "…"

        print(f" {badge_str}  {price_str:>7}  {name}{brand_str}{unit_str} ({page_str}){tag_str}")


def print_grouped_deal_card(g: Any, verbose: bool = False, show_skus: bool = False) -> None:
    """Print a grouped circular ad card with price range, unit price, and variety breakdown."""
    rep = getattr(g, "representative", g)
    badge_str = format_badge_fixed(g.badge, width=16)

    # Price string
    if g.badge == "POINTS_FREEBIE" or getattr(rep, "promo_type", "") == "points_redemption":
        price_str = "       FREE"
    elif g.min_price is not None:
        if g.max_price is not None and abs(g.min_price - g.max_price) >= 0.01:
            price_str = f"${g.min_price:.2f}-${g.max_price:.2f}"
        else:
            price_str = f"${g.min_price:.2f}"
    else:
        price_str = "    See ad"

    # Page string
    pages_list = getattr(g, "pages", [getattr(g, "page_number", 1)])
    if pages_list:
        p_num = str(pages_list[0])
    else:
        p_num = str(getattr(g, "page_number", 1))
    page_str = f"p.{p_num}*" if g.is_front_page else f"p.{p_num}"

    # Unit price string
    if g.min_unit_price is not None and g.unit_type:
        unit_str = f" ({format_unit_price(g.min_unit_price, g.unit_type)})"
    else:
        unit_str = ""

    varieties = getattr(g, "varieties", [])

    if verbose:
        if g.min_unit_price is not None and g.max_unit_price is not None and abs(g.min_unit_price - g.max_unit_price) >= 0.005 and g.unit_type:
            u_min = format_unit_price(g.min_unit_price, g.unit_type)
            u_max = format_unit_price(g.max_unit_price, g.unit_type)
            unit_str_verbose = f" ({u_min}-{u_max})"
        else:
            unit_str_verbose = unit_str

        pages_verbose = f"p.{','.join(map(str, pages_list))}" if pages_list else f"p.{getattr(g, 'page_number', 1)}"
        if g.is_front_page:
            pages_verbose += " (Cover)"
        if len(varieties) > 1:
            sample = ", ".join(varieties[:3])
            more = f", +{len(varieties)-3} more" if len(varieties) > 3 else ""
            var_note = f" [{len(varieties)} varieties: {sample}{more}]"
        else:
            var_note = ""
        print(f" {badge_str}  {price_str:>11}  {g.title}{unit_str_verbose} ({pages_verbose}){var_note}")
        reason = getattr(rep, "summary_reason", "")
        if reason:
            print(f"   ↳ {reason}\n")
    else:
        # Strictly single-line layout budgeted to terminal width
        try:
            term_width = max(80, shutil.get_terminal_size(fallback=(100, 24)).columns)
        except Exception:
            term_width = 100
        target_width = max(76, term_width - 3)

        var_str = f" [{len(varieties)} varieties]" if len(varieties) > 1 else ""
        tags = get_compact_tags(rep)

        # Base overhead: 1 space + badge(16) + 2 spaces + price(11) + 2 spaces + var_str + unit_str + ' (' + page_str + ')'
        base_overhead = 1 + 16 + 2 + 11 + 2 + len(var_str) + len(unit_str) + len(f" ({page_str})")
        avail = target_width - base_overhead

        # Prioritize high-signal promo / ATL tags
        cur_tag_str = ""
        avail_for_tags = max(0, avail - min(len(g.title), 32))
        for t in tags:
            candidate = (cur_tag_str + " • " + t) if cur_tag_str else t
            if len(candidate) + 4 <= avail_for_tags:
                cur_tag_str = candidate
            elif not cur_tag_str and len(t) + 4 <= avail - 18:
                cur_tag_str = t
                break
            else:
                break

        tag_str = ""
        tag_len = 0
        if cur_tag_str:
            color = "\033[91m" if g.badge == "PRICE_HIKE" else "\033[92m"
            tag_str = f"  {color}↳ {cur_tag_str}\033[0m"
            tag_len = len(cur_tag_str) + 4

        avail_title = target_width - base_overhead - tag_len
        if avail_title < 18 and unit_str:
            # Drop unit string if space is tight to preserve title visibility
            base_overhead -= len(unit_str)
            unit_str = ""
            avail_title = target_width - base_overhead - tag_len

        title = g.title
        if len(title) > avail_title and avail_title > 10:
            title = title[:avail_title - 1].rstrip() + "…"

        print(f" {badge_str}  {price_str:>11}  {title}{var_str}{unit_str} ({page_str}){tag_str}")

    if show_skus and len(getattr(g, "items", [])) > 1:
        for it in g.items:
            it_name = getattr(it, "canonical_name", None) or getattr(it, "name", "Item")
            p = getattr(it, "current_price", None)
            if p is None:
                p = getattr(it, "price", None)
            p_str = f"${p:.2f}" if p is not None else "See ad"
            u_val = getattr(it, "unit_price", None)
            u_typ = getattr(it, "unit_type", None)
            u_str = f" ({format_unit_price(u_val, u_typ)})" if u_val and u_typ else ""
            deal_id = getattr(it, "deal_id", None)
            did_str = f" [Deal ID: {deal_id}]" if deal_id else ""
            print(f"       - {it_name}: {p_str}{u_str}{did_str}")


def render_filtered_report(
    evaluations: List[Any],
    flyer_id: int,
    title: str = "WEEKLY DEALS REPORT",
    verbose: bool = False,
    see_ad_omitted_count: int = 0,
    search_query: Optional[str] = None,
    show_skus: bool = False,
    flat: bool = False,
) -> None:
    """Render filtered report of deal cards, grouped by circular ad by default."""
    if flat:
        print(f"\n{'='*76}")
        print(f" {title} (Flyer ID: {flyer_id}) - {len(evaluations)} items")
        print(f"{'='*76}\n")

        for ev in evaluations:
            print_deal_card(ev, verbose=verbose)
    else:
        groups = group_evaluations(evaluations)
        total_items = sum(len(g.items) for g in groups)
        print(f"\n{'='*76}")
        print(f" {title} (Flyer ID: {flyer_id}) - {len(groups)} circular ads ({total_items} items)")
        print(f"{'='*76}\n")

        for g in groups:
            print_grouped_deal_card(g, verbose=verbose, show_skus=show_skus)

    if see_ad_omitted_count > 0:
        print(f"\nℹ️  Omitted {see_ad_omitted_count} unpriced promotional tiles (use --include-see-ad to display).")

    if search_query:
        print(f"\n💡 Search full price history across all circulars: py -m src.cli history \"{search_query}\"")
    print()


def render_smart_digest(
    evaluations: List[Any],
    total_circular_items: int,
    flyer_id: int,
    verbose: bool = False,
    show_skus: bool = False,
    flat: bool = False,
) -> None:
    """Render default 3-tier digest: Front Page + Inside Price Hikes & All-Time Lows / Category Bests."""
    if flat:
        front_page_deals = [e for e in evaluations if e.is_front_page]
        inside_hikes = [e for e in evaluations if not e.is_front_page and e.badge == "PRICE_HIKE"]
        inside_atls = [
            e for e in evaluations
            if not e.is_front_page
            and (e.badge in ("ALL_TIME_LOW", "NEW_ALL_TIME_LOW", "MATCHES_ATL") or getattr(e, "is_category_best", False))
        ]

        print(f"\n{'='*76}")
        print(f" 🛒 WEEKLY DEALS DIGEST (Flyer ID: {flyer_id})")
        print(f" Showing: Front Page Deals ({len(front_page_deals)}) + Inside Price Hikes ({len(inside_hikes)}) & ATLs/Category Bests ({len(inside_atls)})")
        print(f"{'='*76}\n")

        print(f"⭐ FRONT PAGE DEALS (Cover - {len(front_page_deals)} items)")
        print(f"{'-'*76}")
        if front_page_deals:
            for ev in front_page_deals:
                print_deal_card(ev, verbose=verbose)
        else:
            print("  No priced front page deals found.")
        print()

        if inside_hikes:
            print(f"⚠️  PRICE HIKE ALERTS (Inside Pages - {len(inside_hikes)} items)")
            print(f"{'-'*76}")
            for ev in inside_hikes:
                print_deal_card(ev, verbose=verbose)
            print()

        if inside_atls:
            print(f"🌟 ALL-TIME LOWS & CATEGORY BESTS ON INSIDE PAGES ({len(inside_atls)} items)")
            print(f"{'-'*76}")
            for ev in inside_atls:
                print_deal_card(ev, verbose=verbose)
            print()
    else:
        groups = group_evaluations(evaluations)
        front_page_groups = [g for g in groups if g.is_front_page]
        inside_hikes = [g for g in groups if not g.is_front_page and g.badge == "PRICE_HIKE"]
        inside_atls = [
            g for g in groups
            if not g.is_front_page
            and (g.badge in ("ALL_TIME_LOW", "NEW_ALL_TIME_LOW", "MATCHES_ATL") or getattr(g.representative, "is_category_best", False))
        ]
        fp_item_count = sum(len(g.items) for g in front_page_groups)

        print(f"\n{'='*76}")
        print(f" 🛒 WEEKLY DEALS DIGEST (Flyer ID: {flyer_id})")
        print(f" Showing: Front Page Promotions ({len(front_page_groups)}) + Inside Price Hikes ({len(inside_hikes)}) & ATLs/Category Bests ({len(inside_atls)})")
        print(f"{'='*76}\n")

        print(f"⭐ FRONT PAGE PROMOTIONS (Cover - {len(front_page_groups)} ads, {fp_item_count} items)")
        print(f"{'-'*76}")
        if front_page_groups:
            for g in front_page_groups:
                print_grouped_deal_card(g, verbose=verbose, show_skus=show_skus)
        else:
            print("  No priced front page promotions found.")
        print()

        if inside_hikes:
            print(f"⚠️  PRICE HIKE ALERTS (Inside Pages - {len(inside_hikes)} ads)")
            print(f"{'-'*76}")
            for g in inside_hikes:
                print_grouped_deal_card(g, verbose=verbose, show_skus=show_skus)
            print()

        if inside_atls:
            print(f"🌟 ALL-TIME LOWS & CATEGORY BESTS ON INSIDE PAGES ({len(inside_atls)} ads)")
            print(f"{'-'*76}")
            for g in inside_atls:
                print_grouped_deal_card(g, verbose=verbose, show_skus=show_skus)
            print()

    print(f"{'-'*76}")
    print(f"💡 Total circular items: {total_circular_items} (omitted unpriced tiles & standard inside deals)")
    print(f"   • Search price history: py -m src.cli history \"<item>\" (e.g. py -m src.cli history \"beef\")")
    print(f"   • Search current ad:    py -m src.cli deals -q <item>")
    print(f"   • View all pages:       py -m src.cli deals --all")
    print(f"   • Expand varieties:     py -m src.cli deals --skus")
    print(f"   • Flat unmerged items:  py -m src.cli deals --flat")
    print(f"   • Multi-line details:   py -m src.cli deals --verbose")
    print(f"   • Show unpriced tiles:  py -m src.cli deals --include-see-ad\n")

