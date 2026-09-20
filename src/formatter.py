"""
Terminal formatting, ANSI color rendering, and deal card/digest presentation.
"""

from typing import List, Optional, Dict, Any


def format_badge_fixed(badge: str, width: int = 16) -> str:
    """Format deal badge with ANSI terminal color and fixed-width padding."""
    raw_labels = {
        "ALL_TIME_LOW": "[* ALL-TIME LOW]",
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


def print_deal_card(ev: Any, verbose: bool = False) -> None:
    """Print a single deal observation with formatted badge and inline metadata."""
    badge_str = format_badge_fixed(ev.badge, width=16)
    price_str = f"${ev.current_price:.2f}" if ev.current_price is not None else "See ad"
    page_str = f"p.{ev.page_number}" + (" (Cover)" if ev.is_front_page else "")
    brand_str = f" [{ev.brand}]" if ev.brand else ""

    # Actionable inline annotations for non-verbose mode
    note = ""
    if ev.badge == "PRICE_HIKE":
        note = f"  \033[91m↳ {ev.summary_reason}\033[0m"
    elif ev.badge in ("ALL_TIME_LOW", "BEAT_AVERAGE", "CYCLE_REFRESH"):
        note = f"  \033[92m↳ {ev.summary_reason}\033[0m"

    if verbose:
        print(f" {badge_str}  {price_str:>7}  {ev.canonical_name}{brand_str} ({page_str})")
        print(f"   ↳ {ev.summary_reason}\n")
    else:
        print(f" {badge_str}  {price_str:>7}  {ev.canonical_name}{brand_str} ({page_str}){note}")


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
    """Render default 3-tier digest: Front Page + Inside Price Hikes & All-Time Lows."""
    front_page_deals = [e for e in evaluations if e.is_front_page]
    inside_hikes = [e for e in evaluations if not e.is_front_page and e.badge == "PRICE_HIKE"]
    inside_atls = [e for e in evaluations if not e.is_front_page and e.badge == "ALL_TIME_LOW"]

    print(f"\n{'='*78}")
    print(f" 🛒 WEEKLY DEALS DIGEST (Flyer ID: {flyer_id})")
    print(f" Showing: Front Page Deals ({len(front_page_deals)}) + Inside Price Hikes ({len(inside_hikes)}) & ATLs ({len(inside_atls)})")
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
        print(f"🌟 ALL-TIME LOWS ON INSIDE PAGES ({len(inside_atls)} items)")
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
