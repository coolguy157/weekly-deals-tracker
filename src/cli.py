"""
Command-Line Interface for Weekly Deals & Price History Tracker.
"""

import argparse
import sys
import json
import csv
import os
from pathlib import Path
from typing import Optional
from .fetcher import FlippAdFetcher
from .normalizer import ProductNormalizer
from .database import DealsDatabase
from .analyzer import DealAnalyzer
from .formatter import (
    format_badge_fixed,
    format_badge,
    print_deal_card,
    render_filtered_report,
    render_smart_digest,
)


if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Load key-value pairs from a local .env file if present."""
    p = Path(dotenv_path)
    if not p.is_file():
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


def cmd_sync(args: argparse.Namespace) -> None:
    """Fetch current circular from Flipp and ingest into SQLite DB."""
    zip_code = args.zip or os.environ.get("TRACKER_ZIP")
    if not zip_code:
        print("Error: Missing ZIP code. Provide --zip <ZIP> or set TRACKER_ZIP in your .env file.")
        sys.exit(1)

    merchant = args.merchant or os.environ.get("TRACKER_MERCHANT", "Tom Thumb")
    fetcher = FlippAdFetcher()
    normalizer = ProductNormalizer()
    db = DealsDatabase(args.db)

    print(f"Fetching weekly circulars for ZIP {zip_code} (Merchant: '{merchant}')...")
    flyers = fetcher.get_flyers_for_zip(postal_code=zip_code, merchant_filter=merchant)

    if not flyers:
        print(f"No active flyers found for merchant '{args.merchant}' at ZIP {args.zip}.")
        return

    # Select weekly ad
    weekly_ad = next((f for f in flyers if "weekly" in f.name.lower()), flyers[0])
    print(f"Found Circular: {weekly_ad.name} (ID: {weekly_ad.id}) | Valid: {weekly_ad.valid_from[:10]} to {weekly_ad.valid_to[:10]}")

    db.upsert_flyer_run(weekly_ad)
    purged = db.purge_overlapping_untrusted_flyers(
        merchant=weekly_ad.merchant,
        valid_from=weekly_ad.valid_from,
        valid_to=weekly_ad.valid_to,
        keep_flyer_id=weekly_ad.id,
    )
    if purged:
        print(f"Superseded and purged {len(purged)} overlapping backfill circular(s): {purged}")

    pages, items = fetcher.get_flyer_pages_and_items(weekly_ad.id, front_page_only=args.front_page_only)
    print(f"Parsed {len(pages)} pages and {len(items)} items from circular.")

    normalized_batch = []
    for it in items:
        deals = normalizer.disaggregate_and_normalize(it)
        normalized_batch.extend(deals)

    inserted = db.record_deals(normalized_batch)
    print(f"Successfully recorded {inserted} normalized deal observations into database.")


def cmd_deals(args: argparse.Namespace) -> None:
    """Display analyzed deals for the latest circular with clean terminal digest formatting."""
    db = DealsDatabase(args.db)
    analyzer = DealAnalyzer(db)

    flyer_id = args.flyer_id or db.get_latest_flyer_id(args.merchant)
    if not flyer_id:
        print(f"No circulars found in database for merchant '{args.merchant}'. Run 'sync' first.")
        return

    verbose = getattr(args, "verbose", False)

    # If user explicitly requested front_page_only via flag, respect it
    evaluations = analyzer.evaluate_flyer(flyer_id, front_page_only=args.front_page_only)

    if args.query:
        q = args.query.lower()
        evaluations = [
            e for e in evaluations
            if q in e.canonical_name.lower() or (e.brand and q in e.brand.lower())
        ]

    if args.atl_only:
        evaluations = [e for e in evaluations if e.badge == "ALL_TIME_LOW"]

    if getattr(args, "price_hikes_only", False):
        evaluations = [e for e in evaluations if e.badge == "PRICE_HIKE"]

    # Filter out unpriced [SEE AD] items by default unless explicitly requested or query searched
    has_custom_filter = bool(args.query or args.atl_only or getattr(args, "price_hikes_only", False) or args.all_pages)
    see_ad_count = sum(1 for e in evaluations if e.badge == "SEE_AD")

    if not args.include_see_ad and not args.query:
        evaluations_priced = [e for e in evaluations if e.badge != "SEE_AD"]
    else:
        evaluations_priced = evaluations

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

    limit = getattr(args, "limit", None) or len(products)
    shown = products[:limit]
    limit_note = f" (showing first {len(shown)} - use --limit to view more)" if len(shown) < len(products) else ""
    print(f"\nFound {len(products)} matching product(s){limit_note}:\n")

    for p in shown:
        brand_str = f"Brand: {p.get('brand')}" if p.get("brand") else "Brand: N/A"
        print(f"--- Product: {p['canonical_name']} ({brand_str}) ---")
        history = db.get_product_price_history(p["product_id"], trusted_only=args.trusted_only)
        if not history:
            print("   No recorded price observations.")
            continue

        for h in history:
            valid_from = (h.get("valid_from") or "")[:10]
            valid_to = (h.get("valid_to") or "")[:10]
            price = f"${h['advertised_price']:.2f}" if h.get("advertised_price") is not None else "See ad"
            page_info = f"Page {h['page_number']}" + (" (Front Page)" if h['is_front_page'] else "")
            trust_info = "" if h.get("is_trusted", 1) else " \033[93m[Untrusted / Backfill]\033[0m"
            doorbuster_info = " \033[95m[Doorbuster / Outlier]\033[0m" if h.get("promo_type") in ("doorbuster", "outlier") else ""
            deal_id_str = f" [Deal ID: {h['deal_id']}]" if "deal_id" in h else ""
            print(f"   • [{valid_from} - {valid_to}] Price: {price} ({page_info}){doorbuster_info}{trust_info}{deal_id_str}")
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


def cmd_export(args: argparse.Namespace) -> None:
    """Export evaluated deals to JSON or CSV."""
    db = DealsDatabase(args.db)
    analyzer = DealAnalyzer(db)

    flyer_id = args.flyer_id or db.get_latest_flyer_id(args.merchant)
    if not flyer_id:
        print("No circular found to export.")
        return

    evaluations = analyzer.evaluate_flyer(flyer_id, front_page_only=args.front_page_only)
    records = [
        {
            "deal_id": e.deal_id,
            "product_id": e.product_id,
            "name": e.canonical_name,
            "brand": e.brand,
            "price": e.current_price,
            "unit_price": e.unit_price,
            "page": e.page_number,
            "is_front_page": e.is_front_page,
            "historical_min": e.historical_min,
            "historical_avg": e.historical_avg,
            "badge": e.badge,
            "analysis": e.summary_reason,
        }
        for e in evaluations
    ]

    if args.format == "json":
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    elif args.format == "csv":
        if records:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)

    print(f"Exported {len(records)} evaluated deals to {args.output}")


def cmd_renormalize(args: argparse.Namespace) -> None:
    """Disaggregate compound deals across circular history and reconcile product catalog."""
    import shutil

    db = DealsDatabase(args.db)
    normalizer = ProductNormalizer()

    # Backup local database if not in-memory
    if not db.is_memory and Path(db.db_path).exists():
        backup_path = f"{db.db_path}.bak"
        shutil.copyfile(db.db_path, backup_path)
        print(f"📦 Created safety database backup at: {backup_path}")

    print("Re-evaluating circular history and disaggregating multi-product compound deals...")
    disaggregated_obs, new_obs, deleted_orphans = db.renormalize_all_deals(normalizer)

    print(f"✅ Re-normalization complete!")
    print(f"   • Disaggregated {disaggregated_obs} compound observations into {new_obs} single-product observations.")
    print(f"   • Pruned {deleted_orphans} obsolete compound product records from catalog.")


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
    p_sync.add_argument("--zip", type=str, default=None, help="5-digit Postal / ZIP code (or set TRACKER_ZIP in .env)")
    p_sync.add_argument("--merchant", type=str, default="Tom Thumb", help="Merchant banner filter")
    p_sync.add_argument("--front-page-only", action="store_true", help="Ingest Page 1 only")

    # deals
    p_deals = subparsers.add_parser("deals", help="List evaluated deals for latest circular")
    p_deals.add_argument("-q", "--query", type=str, default=None, help="Filter deals by keyword or generic item (e.g. 'bacon', 'milk')")
    p_deals.add_argument("--merchant", type=str, default="Tom Thumb", help="Merchant banner")
    p_deals.add_argument("--flyer-id", type=int, default=None, help="Specific circular flyer ID")
    p_deals.add_argument("--front-page-only", action="store_true", help="Filter front page deals only")
    p_deals.add_argument("--atl-only", action="store_true", help="Filter All-Time Lows only")
    p_deals.add_argument("--hikes-only", "--price-hikes-only", dest="price_hikes_only", action="store_true", help="Filter Price Hikes only")
    p_deals.add_argument("--all", "--all-pages", dest="all_pages", action="store_true", help="Show all items across all circular pages")
    p_deals.add_argument("--include-see-ad", action="store_true", help="Include unpriced promotional tiles and bundle headers")
    p_deals.add_argument("-v", "--verbose", action="store_true", help="Show multi-line detailed cards for each item")

    # history
    p_hist = subparsers.add_parser("history", help="Show price history of a product")
    p_hist.add_argument("query", type=str, help="Product name or brand to search")
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
    p_exp.add_argument("--merchant", type=str, default="Tom Thumb", help="Merchant banner")
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
