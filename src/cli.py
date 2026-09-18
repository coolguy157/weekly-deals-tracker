"""
Command-Line Interface for Weekly Deals & Price History Tracker.
"""

import argparse
import sys
import json
import csv
from typing import Optional
from .fetcher import FlippAdFetcher
from .normalizer import ProductNormalizer
from .database import DealsDatabase
from .analyzer import DealAnalyzer


if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_badge(badge: str) -> str:
    badge_colors = {
        "ALL_TIME_LOW": "\033[92m[* ALL-TIME LOW]\033[0m",
        "BEAT_AVERAGE": "\033[96m[^ BEAT AVERAGE]\033[0m",
        "CYCLE_REFRESH": "\033[94m[~ CYCLE REFRESH]\033[0m",
        "FIRST_SEEN": "\033[93m[+ FIRST SEEN]\033[0m",
        "STANDARD_DEAL": "\033[90m[DEAL]\033[0m",
        "PRICE_HIKE": "\033[91m[! PRICE HIKE]\033[0m",
        "SEE_AD": "\033[90m[SEE AD]\033[0m",
    }
    return badge_colors.get(badge, f"[{badge}]")


import os
from pathlib import Path


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

    pages, items = fetcher.get_flyer_pages_and_items(weekly_ad.id, front_page_only=args.front_page_only)
    print(f"Parsed {len(pages)} pages and {len(items)} items from circular.")

    normalized_batch = []
    for it in items:
        deals = normalizer.disaggregate_and_normalize(it)
        normalized_batch.extend(deals)

    inserted = db.record_deals(normalized_batch)
    print(f"Successfully recorded {inserted} normalized deal observations into database.")


def cmd_deals(args: argparse.Namespace) -> None:
    """Display analyzed deals for the latest circular."""
    db = DealsDatabase(args.db)
    analyzer = DealAnalyzer(db)

    flyer_id = args.flyer_id or db.get_latest_flyer_id(args.merchant)
    if not flyer_id:
        print(f"No circulars found in database for merchant '{args.merchant}'. Run 'sync' first.")
        return

    evaluations = analyzer.evaluate_flyer(flyer_id, front_page_only=args.front_page_only)

    if args.query:
        q = args.query.lower()
        evaluations = [
            e for e in evaluations
            if q in e.canonical_name.lower() or (e.brand and q in e.brand.lower())
        ]

    if args.atl_only:
        evaluations = [e for e in evaluations if e.badge == "ALL_TIME_LOW"]

    print(f"\n{'='*75}")
    print(f" WEEKLY DEALS REPORT (Flyer ID: {flyer_id}) - {len(evaluations)} items")
    print(f"{'='*75}\n")

    for ev in evaluations:
        badge_str = format_badge(ev.badge)
        price_str = f"${ev.current_price:.2f}" if ev.current_price is not None else "See ad"
        page_str = f"Page {ev.page_number}" + (" (Cover)" if ev.is_front_page else "")

        print(f"{badge_str} {ev.canonical_name} ({page_str})")
        print(f"   Price: {price_str} | {ev.summary_reason}")
        if ev.brand:
            print(f"   Brand: {ev.brand}")
        print()


def cmd_history(args: argparse.Namespace) -> None:
    """Display price history timeline for a product."""
    db = DealsDatabase(args.db)
    products = db.search_products(args.query)

    if not products:
        print(f"No products found matching '{args.query}'.")
        return

    print(f"\nFound {len(products)} matching product(s):\n")
    for p in products[:5]:
        print(f"--- Product: {p['canonical_name']} (Brand: {p.get('brand') or 'N/A'}) ---")
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
            print(f"   • [{valid_from} - {valid_to}] Price: {price} ({page_info}){trust_info}")
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

    # history
    p_hist = subparsers.add_parser("history", help="Show price history of a product")
    p_hist.add_argument("query", type=str, help="Product name or brand to search")
    p_hist.add_argument("--trusted-only", action="store_true", help="Show only verified/trusted deal observations")

    # mark-trust
    p_trust = subparsers.add_parser("mark-trust", help="Set trust / verification flag on deals")
    p_trust.add_argument("action", choices=["trust", "untrust"], help="Action to set")
    p_trust.add_argument("--flyer-id", type=int, default=None, help="Specific flyer ID to flag")
    p_trust.add_argument("--all-past", action="store_true", help="Flag all historical past circulars")
    p_trust.add_argument("--include-current", action="store_true", help="Include current live sync flyer")

    # export
    p_exp = subparsers.add_parser("export", help="Export evaluated deals to file")
    p_exp.add_argument("--format", choices=["json", "csv"], default="json", help="Export format")
    p_exp.add_argument("--output", type=str, default="deals_export.json", help="Output file path")
    p_exp.add_argument("--merchant", type=str, default="Tom Thumb", help="Merchant banner")
    p_exp.add_argument("--flyer-id", type=int, default=None, help="Specific flyer ID")
    p_exp.add_argument("--front-page-only", action="store_true", help="Front page deals only")

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
    elif args.command == "export":
        cmd_export(args)


if __name__ == "__main__":
    main()
