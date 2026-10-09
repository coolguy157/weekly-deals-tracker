"""
Command-Line Interface for Weekly Deals & Price History Tracker.
"""

import argparse
import sys
from typing import Optional

from .database import DealsDatabase
from .analyzer import DealAnalyzer
from .formatter import (
    format_unit_price,
    render_filtered_report,
    render_smart_digest,
)
from .normalizer.cleaner import GENERIC_PLACEHOLDER_NAMES

# Modular services & pipeline imports
from .sync_pipeline import (
    STORE_PRESETS,
    DEFAULT_STORE,
    load_dotenv,
    resolve_store,
    _resolve_merchant_filter,
    parse_store_configs,
    _get_app_bridge,
    _enrich_deals_with_app,
    _sync_single_store,
    cmd_sync,
)
from .export_service import (
    cmd_export,
    cmd_renormalize,
)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def cmd_deals(args: argparse.Namespace) -> None:
    """Display analyzed deals for the latest circular with clean terminal digest formatting."""
    db = DealsDatabase(args.db)
    analyzer = DealAnalyzer(db)

    merchant = _resolve_merchant_filter(args)
    flyer_id = args.flyer_id or db.get_latest_flyer_id(merchant)
    if not flyer_id:
        target_str = f"merchant '{merchant}'" if merchant else "any circular"
        print(f"No circulars found in database for {target_str}. Run 'sync' first.")
        return

    verbose = getattr(args, "verbose", False)

    # If user explicitly requested front_page_only via flag, respect it
    evaluations = analyzer.evaluate_flyer(flyer_id, front_page_only=args.front_page_only)

    if args.query:
        q = args.query.lower()
        evaluations = [
            e for e in evaluations
            if q in e.canonical_name.lower()
            or (e.brand and q in e.brand.lower())
            or (e.category and q in e.category.lower())
            or (e.promo_detail and q in e.promo_detail.lower())
            or (e.summary_reason and q in e.summary_reason.lower())
        ]

    if getattr(args, "category", None):
        cat_filter = args.category.lower()
        evaluations = [
            e for e in evaluations
            if (e.category and cat_filter in e.category.lower()) or (cat_filter in e.canonical_name.lower())
        ]

    if args.atl_only:
        evaluations = [e for e in evaluations if e.badge == "ALL_TIME_LOW"]

    if getattr(args, "cat_best_only", False):
        evaluations = [e for e in evaluations if getattr(e, "is_category_best", False)]

    if getattr(args, "price_hikes_only", False):
        evaluations = [e for e in evaluations if e.badge == "PRICE_HIKE"]

    if getattr(args, "sort_unit_price", False):
        evaluations.sort(key=lambda x: (x.unit_price is None, x.unit_price or 999999, x.current_price or 999999))

    # Filter out unpriced [SEE AD] items by default unless explicitly requested or query searched
    has_custom_filter = bool(args.query or args.atl_only or getattr(args, "cat_best_only", False) or getattr(args, "price_hikes_only", False) or args.all_pages or getattr(args, "sort_unit_price", False) or getattr(args, "category", None))
    see_ad_count = sum(1 for e in evaluations if e.badge == "SEE_AD")

    if not args.include_see_ad and not args.query:
        evaluations_priced = [e for e in evaluations if e.badge != "SEE_AD"]
    else:
        evaluations_priced = evaluations

    # Filter out generic placeholder umbrella tiles (e.g. 'Assorted Products') from standard digest
    if not args.query:
        evaluations_priced = [e for e in evaluations_priced if e.canonical_name.strip().lower() not in GENERIC_PLACEHOLDER_NAMES]

    # If --all or a specific search/filter is specified, print direct matching list
    if has_custom_filter or args.front_page_only:
        title = "ALL CIRCULAR DEALS" if args.all_pages else "WEEKLY DEALS REPORT"
        render_filtered_report(
            evaluations=evaluations_priced,
            flyer_id=flyer_id,
            title=title,
            verbose=verbose,
            see_ad_omitted_count=(see_ad_count if not args.include_see_ad and not args.query else 0),
            search_query=args.query,
        )
        return

    # DEFAULT SMART DIGEST VIEW: Front Page (Cover) + Circular-Wide Price Hikes & All-Time Lows
    render_smart_digest(
        evaluations=evaluations_priced,
        total_circular_items=len(evaluations),
        flyer_id=flyer_id,
        verbose=verbose,
    )


def cmd_history(args: argparse.Namespace) -> None:
    """Display price history timeline for a product."""
    db = DealsDatabase(args.db)
    products = db.search_products(args.query)

    if not products:
        print(f"No products found matching '{args.query}'.")
        return

    merchant = _resolve_merchant_filter(args)
    limit = getattr(args, "limit", None) or len(products)
    shown = products[:limit]
    limit_note = f" (showing first {len(shown)} - use --limit to view more)" if len(shown) < len(products) else ""
    print(f"\nFound {len(products)} matching product(s){limit_note}:\n")

    for p in shown:
        brand_str = f"Brand: {p.get('brand')}" if p.get("brand") else "Brand: N/A"
        cat_str = f" | Commodity: {p.get('category')}" if p.get("category") else ""
        print(f"--- Product: {p['canonical_name']} ({brand_str}{cat_str}) ---")
        history = db.get_product_price_history(p["product_id"], trusted_only=args.trusted_only, merchant=merchant)
        if not history:
            print("   No recorded price observations.")
            continue

        for h in history:
            valid_from = (h.get("valid_from") or "")[:10]
            valid_to = (h.get("valid_to") or "")[:10]
            price = f"${h['advertised_price']:.2f}" if h.get("advertised_price") is not None else "See ad"
            unit_str = ""
            if h.get("unit_price") is not None and h.get("unit_type"):
                u_fmt = format_unit_price(h.get("unit_price"), h.get("unit_type"))
                if u_fmt:
                    unit_str = f" ({u_fmt})"
            page_info = f"Page {h['page_number']}" + (" (Front Page)" if h['is_front_page'] else "")
            merchant_info = f" [{h['merchant']}]" if h.get("merchant") else ""
            trust_info = "" if h.get("is_trusted", 1) else " \033[93m[Untrusted / Backfill]\033[0m"
            doorbuster_info = " \033[95m[Doorbuster / Outlier]\033[0m" if h.get("promo_type") in ("doorbuster", "outlier") else ""
            deal_id_str = f" [Deal ID: {h['deal_id']}]" if "deal_id" in h else ""
            print(f"   • [{valid_from} - {valid_to}] Price: {price}{unit_str} ({page_info}){merchant_info}{doorbuster_info}{trust_info}{deal_id_str}")
        print()


def cmd_mark_trust(args: argparse.Namespace) -> None:
    """Mark circulars or deals as trusted or untrusted."""
    db = DealsDatabase(args.db)
    is_trusted = (args.action == "trust")
    if args.flyer_id:
        db.mark_flyer_trust(args.flyer_id, is_trusted=is_trusted)
        print(f"Marked flyer {args.flyer_id} and all its deals as {'TRUSTED' if is_trusted else 'UNTRUSTED'}.")
    elif args.all_past:
        # Keep latest live circular trusted by default
        latest_id = db.get_latest_flyer_id()
        except_ids = [latest_id] if (latest_id and not args.include_current) else []
        count = db.mark_all_past_deals_trust(is_trusted=is_trusted, except_flyer_ids=except_ids)
        print(f"Marked {count} past deal observations as {'TRUSTED' if is_trusted else 'UNTRUSTED'}.")


def cmd_mark_doorbuster(args: argparse.Namespace) -> None:
    """Mark a flyer or deal observation as a doorbuster / outlier promo."""
    db = DealsDatabase(args.db)
    is_doorbuster = (args.action == "tag")

    if args.deal_id:
        success = db.mark_deal_doorbuster(args.deal_id, is_doorbuster=is_doorbuster)
        status = "DOORBUSTER / OUTLIER" if is_doorbuster else "STANDARD PROMO"
        if success:
            print(f"Successfully marked deal {args.deal_id} as {status}.")
        else:
            print(f"Deal ID {args.deal_id} not found.")
    elif args.flyer_id:
        count = db.mark_flyer_doorbuster(args.flyer_id, is_doorbuster=is_doorbuster)
        status = "DOORBUSTER / OUTLIER" if is_doorbuster else "STANDARD PROMO"
        print(f"Marked {count} deals in flyer {args.flyer_id} as {status}.")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Weekly Deals & Price History Tracker CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--db", type=str, default=None, help="Path to custom SQLite DB file")

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # sync
    p_sync = subparsers.add_parser("sync", help="Fetch & ingest active circular")
    p_sync.add_argument("--store", type=str, default=None, help="Preset store alias (e.g. 'giant', 'lewisburg', 'tomthumb'; default: 'tomthumb')")
    p_sync.add_argument("--zip", type=str, default=None, help="5-digit Postal / ZIP code (or set TRACKER_ZIP in .env)")
    p_sync.add_argument("-m", "--merchant", type=str, default=None, help="Merchant banner filter (e.g. 'Giant', 'Tom Thumb')")
    p_sync.add_argument("--all-stores", action="store_true", help="Sync all configured stores (from TRACKER_STORES in .env or presets)")
    p_sync.add_argument("--front-page-only", action="store_true", help="Ingest front page only")
    p_sync.add_argument("--front-page-number", type=int, default=None, help="Explicit front page number (overrides auto-detection for Savings Lock inserts)")
    p_sync.add_argument("--enrich-app", action="store_true", help="Bridge with Tom Thumb mobile app to harvest in-app viewer promos and search base shelf prices")

    # deals
    p_deals = subparsers.add_parser("deals", help="List evaluated deals for latest circular")
    p_deals.add_argument("-q", "--query", type=str, default=None, help="Filter deals by keyword or generic item (e.g. 'bacon', 'milk')")
    p_deals.add_argument("-c", "--category", type=str, default=None, help="Filter deals by commodity category (e.g. 'Cheese', 'Bacon')")
    p_deals.add_argument("--store", type=str, default=None, help="Preset store alias (e.g. 'giant', 'tomthumb'; default: 'tomthumb')")
    p_deals.add_argument("-m", "--merchant", type=str, default=None, help="Merchant banner (e.g. 'Giant', 'Tom Thumb')")
    p_deals.add_argument("--flyer-id", type=int, default=None, help="Specific circular flyer ID")
    p_deals.add_argument("--front-page-only", action="store_true", help="Filter front page deals only")
    p_deals.add_argument("--atl-only", action="store_true", help="Filter All-Time Lows only")
    p_deals.add_argument("--cat-best", "--category-best", dest="cat_best_only", action="store_true", help="Filter deals that are the lowest unit price across their generic commodity category")
    p_deals.add_argument("--hikes-only", "--price-hikes-only", dest="price_hikes_only", action="store_true", help="Filter Price Hikes only")
    p_deals.add_argument("--all", "--all-pages", dest="all_pages", action="store_true", help="Show all items across all circular pages")
    p_deals.add_argument("--include-see-ad", action="store_true", help="Include unpriced promotional tiles and bundle headers")
    p_deals.add_argument("--sort-unit-price", "--sort-by-unit-price", dest="sort_unit_price", action="store_true", help="Sort deals by unit price ($/unit) ascending")
    p_deals.add_argument("-v", "--verbose", action="store_true", help="Show multi-line detailed cards for each item")

    # history
    p_hist = subparsers.add_parser("history", help="Show price history of a product")
    p_hist.add_argument("query", type=str, help="Product name or brand to search")
    p_hist.add_argument("--store", type=str, default=None, help="Filter history by preset store alias (default: 'tomthumb')")
    p_hist.add_argument("-m", "--merchant", type=str, default=None, help="Filter history by merchant banner (e.g. 'Giant', 'Tom Thumb')")
    p_hist.add_argument("--trusted-only", action="store_true", help="Show only verified/trusted deal observations")
    p_hist.add_argument("-n", "--limit", type=int, default=None, help="Maximum number of matching products to display")

    # mark-trust
    p_trust = subparsers.add_parser("mark-trust", help="Set trust / verification flag on deals")
    p_trust.add_argument("action", choices=["trust", "untrust"], help="Action to set")
    p_trust.add_argument("--flyer-id", type=int, default=None, help="Specific flyer ID to flag")
    p_trust.add_argument("--all-past", action="store_true", help="Flag all historical past circulars")
    p_trust.add_argument("--include-current", action="store_true", help="Include current live sync flyer")

    # mark-doorbuster
    p_door = subparsers.add_parser("mark-doorbuster", help="Tag or untag outlier / doorbuster promos")
    p_door.add_argument("action", choices=["tag", "untag"], help="Action to set (tag as doorbuster or untag to standard)")
    p_door.add_argument("--deal-id", type=int, default=None, help="Specific deal observation ID")
    p_door.add_argument("--flyer-id", type=int, default=None, help="Entire flyer ID to tag")

    # export
    p_exp = subparsers.add_parser("export", help="Export evaluated deals to file")
    p_exp.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    p_exp.add_argument("--output", type=str, default="deals_export.json", help="Output file path")
    p_exp.add_argument("--store", type=str, default=None, help="Preset store alias (default: 'tomthumb')")
    p_exp.add_argument("-m", "--merchant", type=str, default=None, help="Merchant banner")
    p_exp.add_argument("--flyer-id", type=int, default=None, help="Specific flyer ID")
    p_exp.add_argument("--front-page-only", action="store_true", help="Front page deals only")

    # renormalize
    p_renorm = subparsers.add_parser("renormalize", help="Reconcile and disaggregate all past compound deals")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "deals":
        cmd_deals(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "mark-trust":
        cmd_mark_trust(args)
    elif args.command == "mark-doorbuster":
        cmd_mark_doorbuster(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "renormalize":
        cmd_renormalize(args)


if __name__ == "__main__":
    main()
