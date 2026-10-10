"""
Terminal formatting, ANSI color rendering, and deal card/digest presentation.
"""

from typing import List, Optional, Dict, Any


def format_badge_fixed(badge: str, width: int = 16) -> str:
    """Format deal badge with ANSI terminal color and fixed-width padding."""
    raw_labels = {
        "ALL_TIME_LOW": "[* ALL-TIME LOW]",
        "POINTS_FREEBIE": "[🪙 FREEBIE]",
        "POINTS_REWARD": "[🪙 REWARD]",
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
        "ALL_TIME_LOW": "\033[92m",
        "POINTS_FREEBIE": "\033[95m",
        "POINTS_REWARD": "\033[95m",
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


def format_compact_note(ev: Any) -> str:
    """Format a concise, high-signal annotation tag for clean single-line display."""
    tags = []

    # Promo Tag (BOGO, Must Buy, Digital Coupon, Points, Spend & Save, Percent Off)
    promo_type = getattr(ev, "promo_type", "standard")
    promo_detail = getattr(ev, "promo_detail", None)
    base_price = getattr(ev, "base_price", None)
    if promo_type == "bogo" and promo_detail:
        base_str = f" (Base ${base_price:.2f})" if base_price else ""
        tags.append(f"🎁 {promo_detail}{base_str}")
    elif promo_type == "must_buy" and promo_detail:
        tags.append(f"📦 {promo_detail}")
    elif promo_type == "digital_coupon" and promo_detail:
        tags.append(f"🎟️ {promo_detail}")
    elif promo_type == "points_redemption" and promo_detail:
        tags.append(f"🪙 {promo_detail}")
    elif promo_type == "points_bonus" and promo_detail:
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
    if ev.badge == "ALL_TIME_LOW":
        if ev.historical_min and ev.current_price and ev.current_price < (ev.historical_min - 0.005):
            pct = round(((ev.historical_min - ev.current_price) / ev.historical_min) * 100)
            tags.append(f"🌟 -{pct}% ATL (was ${ev.historical_min:.2f})")
        elif "Matches" in ev.summary_reason or (ev.historical_min and abs((ev.current_price or 0) - ev.historical_min) <= 0.005):
            tags.append("🌟 Matches ATL")
        else:
            tags.append("🌟 ATL")
    elif ev.badge == "PRICE_HIKE":
        if ev.diff_pct_vs_avg:
            tags.append(f"⚠️ +{round(ev.diff_pct_vs_avg)}% vs avg")
        else:
            tags.append("⚠️ Price Hike")
    elif ev.badge == "BEAT_AVERAGE":
        if ev.diff_pct_vs_avg:
            tags.append(f"🔥 {round(ev.diff_pct_vs_avg)}% vs avg")
    elif ev.badge == "CYCLE_REFRESH":
        if "multi-week" in ev.summary_reason.lower():
            tags.append("🔄 Multi-week")

    if not tags:
        return ""

    color = "\033[91m" if ev.badge == "PRICE_HIKE" else "\033[92m"
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
        note = format_compact_note(ev)
        print(f" {badge_str}  {price_str:>7}  {ev.canonical_name}{brand_str}{unit_str} ({page_str}){note}")


def render_filtered_report(
    evaluations: List[Any],
    flyer_id: int,
    title: str = "WEEKLY DEALS REPORT",
    verbose: bool = False,
    see_ad_omitted_count: int = 0,
    search_query: Optional[str] = None,
) -> None:
    """Render direct flat listing of filtered deal cards."""
    print(f"\n{'='*78}")
    print(f" {title} (Flyer ID: {flyer_id}) - {len(evaluations)} items")
    print(f"{'='*78}\n")

    for ev in evaluations:
        print_deal_card(ev, verbose=verbose)

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
) -> None:
    """Render default 3-tier digest: Front Page + Inside Price Hikes & All-Time Lows / Category Bests."""
    front_page_deals = [e for e in evaluations if e.is_front_page]
    inside_hikes = [e for e in evaluations if not e.is_front_page and e.badge == "PRICE_HIKE"]
    inside_atls = [e for e in evaluations if not e.is_front_page and (e.badge == "ALL_TIME_LOW" or getattr(e, "is_category_best", False))]

    print(f"\n{'='*78}")
    print(f" 🛒 WEEKLY DEALS DIGEST (Flyer ID: {flyer_id})")
    print(f" Showing: Front Page Deals ({len(front_page_deals)}) + Inside Price Hikes ({len(inside_hikes)}) & ATLs/Category Bests ({len(inside_atls)})")
    print(f"{'='*78}\n")

    print(f"⭐ FRONT PAGE DEALS (Cover - {len(front_page_deals)} items)")
    print(f"{'-'*78}")
    if front_page_deals:
        for ev in front_page_deals:
            print_deal_card(ev, verbose=verbose)
    else:
        print("  No priced front page deals found.")
    print()

    if inside_hikes:
        print(f"⚠️  PRICE HIKE ALERTS (Inside Pages - {len(inside_hikes)} items)")
        print(f"{'-'*78}")
        for ev in inside_hikes:
            print_deal_card(ev, verbose=verbose)
        print()

    if inside_atls:
        print(f"🌟 ALL-TIME LOWS & CATEGORY BESTS ON INSIDE PAGES ({len(inside_atls)} items)")
        print(f"{'-'*78}")
        for ev in inside_atls:
            print_deal_card(ev, verbose=verbose)
        print()

    print(f"{'-'*78}")
    print(f"💡 Total circular items: {total_circular_items} (omitted unpriced tiles & standard inside deals)")
    print(f"   • Search price history: py -m src.cli history \"<item>\" (e.g. py -m src.cli history \"beef\")")
    print(f"   • Search current ad:    py -m src.cli deals -q <item>")
    print(f"   • View all pages:       py -m src.cli deals --all")
    print(f"   • Multi-line details:   py -m src.cli deals --verbose")
    print(f"   • Show unpriced tiles:  py -m src.cli deals --include-see-ad\n")
