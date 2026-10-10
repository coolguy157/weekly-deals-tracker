"""
export_service.py
Purpose: Export analyzed circular deals to JSON/CSV formats and catalog re-normalization workflows.
"""

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from .database import DealsDatabase
from .analyzer import DealAnalyzer
from .normalizer import ProductNormalizer
from .sync_pipeline import _resolve_merchant_filter


def cmd_export(args: argparse.Namespace) -> None:
    """Export evaluated deals to JSON or CSV."""
    db = DealsDatabase(args.db)
    analyzer = DealAnalyzer(db)

    merchant = _resolve_merchant_filter(args)
    flyer_id = args.flyer_id or db.get_latest_flyer_id(merchant)
    if not flyer_id:
        print("No circular found to export.")
        return

    flyer_info = None
    with db._get_connection() as conn:
        row = conn.execute("SELECT flyer_id, postal_code, merchant, name, valid_from, valid_to, scraped_at FROM flyer_runs WHERE flyer_id = ?", (flyer_id,)).fetchone()
        if row:
            flyer_info = dict(row)

    evaluations = analyzer.evaluate_flyer(flyer_id, front_page_only=args.front_page_only)
    records = [
        {
            "deal_id": e.deal_id,
            "product_id": e.product_id,
            "ad_id": e.ad_id,
            "raw_deal_id": e.raw_deal_id,
            "name": e.canonical_name,
            "brand": e.brand,
            "category": e.category or "Other",
            "price": e.current_price,
            "unit_price": e.unit_price,
            "unit_size": e.unit_size,
            "unit_type": e.unit_type,
            "page": e.page_number,
            "is_front_page": e.is_front_page,
            "historical_min": e.historical_min,
            "historical_avg": e.historical_avg,
            "diff_pct_vs_avg": e.diff_pct_vs_avg,
            "badge": e.badge,
            "analysis": e.summary_reason,
            "promo_type": e.promo_type,
            "promo_detail": e.promo_detail,
            "raw_title": e.raw_title,
            "image_url": e.image_url,
            "is_category_best": e.is_category_best,
        }
        for e in evaluations
    ]

    if args.format == "json":
        export_payload = {
            "flyer": flyer_info,
            "updated_at": datetime.now().isoformat(),
            "total_deals": len(records),
            "deals": records,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2)
    elif args.format == "csv":
        if records:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                writer.writerows(records)

    print(f"Exported {len(records)} evaluated deals to {args.output}")


def cmd_renormalize(args: argparse.Namespace) -> None:
    """Disaggregate compound deals across circular history and reconcile product catalog."""
    db = DealsDatabase(args.db)
    normalizer = ProductNormalizer()

    # Backup local database if not in-memory
    if not db.is_memory and Path(db.db_path).exists():
        backup_path = f"{db.db_path}.bak"
        shutil.copyfile(db.db_path, backup_path)
        print(f"📦 Created safety database backup at: {backup_path}")

    print("Re-evaluating circular history and disaggregating multi-product compound deals...")
    disaggregated_obs, new_obs, deleted_orphans = db.renormalize_all_deals(normalizer)

    print("✅ Re-normalization complete!")
    print(f"   • Disaggregated {disaggregated_obs} compound observations into {new_obs} single-product observations.")
    print(f"   • Pruned {deleted_orphans} obsolete compound product records from catalog.")
