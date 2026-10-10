"""
sync_pipeline.py
Purpose: Circular ingestion pipeline, store presets resolution, and mobile app enrichment bridge.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple

from .database import DealsDatabase
from .fetcher import FlippAdFetcher
from .normalizer import ProductNormalizer


STORE_PRESETS = {
    "giant": {"zip": "17837", "merchant": "Giant Food Stores", "name": "Giant (Lewisburg, PA 17837)"},
    "lewisburg": {"zip": "17837", "merchant": "Giant Food Stores", "name": "Giant (Lewisburg, PA 17837)"},
    "giant_lewisburg": {"zip": "17837", "merchant": "Giant Food Stores", "name": "Giant (Lewisburg, PA 17837)"},
    "tomthumb": {"zip": "75080", "merchant": "Tom Thumb", "name": "Tom Thumb (Richardson, TX 75080)"},
    "tom_thumb": {"zip": "75080", "merchant": "Tom Thumb", "name": "Tom Thumb (Richardson, TX 75080)"},
}

DEFAULT_STORE = "tomthumb"


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


def resolve_store(store_key: Optional[str]) -> Optional[dict]:
    """Resolve a store preset alias to its zip and merchant configuration."""
    if not store_key:
        return None
    normalized = store_key.lower().strip().replace("-", "_").replace(" ", "_")
    return STORE_PRESETS.get(normalized)


def _resolve_merchant_filter(args: argparse.Namespace) -> Optional[str]:
    """Resolve merchant banner filter from args, env, or default store preset."""
    if getattr(args, "store", None):
        preset = resolve_store(args.store)
        if preset:
            return preset["merchant"]
    if getattr(args, "merchant", None):
        preset = resolve_store(args.merchant)
        return preset["merchant"] if preset else args.merchant
    if os.environ.get("TRACKER_MERCHANT"):
        return os.environ.get("TRACKER_MERCHANT")
    preset = resolve_store(DEFAULT_STORE)
    return preset["merchant"] if preset else "Tom Thumb"


def parse_store_configs(stores_str: str) -> List[Tuple[str, str]]:
    """Parse comma-separated zip:merchant pairs (e.g. '17837:Giant Food Stores, 75080:Tom Thumb')."""
    stores = []
    for item in stores_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            z, m = item.split(":", 1)
            stores.append((z.strip(), m.strip()))
        else:
            stores.append((item.strip(), ""))
    return stores


def _get_app_bridge():
    """Attempt dynamic import of App Automation circular bridge."""
    try:
        current_file = Path(__file__).resolve()
        workspace_root = current_file.parent.parent.parent
        for candidate_name in ["app_automation", "App Automation"]:
            candidate_dir = workspace_root / candidate_name
            if candidate_dir.exists():
                if str(candidate_dir) not in sys.path:
                    sys.path.insert(0, str(candidate_dir))
                from src.bridge.circular_bridge import get_inapp_weekly_ad_promos, lookup_shelf_prices, enrich_weekly_ad_ambiguous_deals
                return get_inapp_weekly_ad_promos, lookup_shelf_prices, enrich_weekly_ad_ambiguous_deals
    except Exception as e:
        print(f"Warning: Could not import App Automation bridge: {e}")
    return None, None, None


def _enrich_deals_with_app(db: DealsDatabase, flyer_id: int) -> None:
    """Enrich unpriced and BOGO deals by querying the mobile app for promos and shelf prices."""
    from .promo_extractor import PromoExtractor, PromoInfo

    get_promos_fn, lookup_shelf_fn, disambiguate_fn = _get_app_bridge()
    if not lookup_shelf_fn:
        print("  [App Enrichment] App Automation bridge not available. Skipping in-app enrichment.\n")
        return

    print("\n--- [App Enrichment] Connecting to Tom Thumb App Automation Bridge ---")
    deals = db.get_deals_for_flyer(flyer_id)
    bogo_deals = [d for d in deals if d.get("promo_type") == "bogo" and d.get("advertised_price") is None]

    if not bogo_deals:
        print("  [App Enrichment] No unpriced BOGO deals requiring shelf price lookup.")
        return

    print(f"  [App Enrichment] Found {len(bogo_deals)} unpriced BOGO deals. Resolving shelf prices...")

    # Build search query terms for BOGOs
    search_queries = []
    deal_map = {}
    for d in bogo_deals:
        cname = d["canonical_name"]
        # Use brand or first 2-3 words of canonical name
        term = d.get("brand") or " ".join(cname.split()[:2])
        search_queries.append(term)
        deal_map[term] = d

    # 1. Check local DB cache first
    cached_count = 0
    queries_needing_app = []
    for term, d in deal_map.items():
        cached_price = d.get("last_shelf_price")
        if cached_price and cached_price > 0:
            cached_count += 1
            # Compute effective price
            promo_info = PromoExtractor.extract_promo(d.get("promo_detail") or "BUY 1 GET 1 FREE") or PromoInfo(
                promo_type="bogo",
                promo_detail=d.get("promo_detail") or "BOGO",
                buy_qty=1,
                free_qty=1,
                qualifying_qty=d.get("qualifying_qty") or 2,
            )
            eff_price = PromoExtractor.calculate_effective_price(promo_info, base_price=cached_price)
            unit_price = round(eff_price / d["unit_size"], 4) if (eff_price and d.get("unit_size")) else None
            db.update_deal_price(d["id"], advertised_price=eff_price, unit_price=unit_price, base_price=cached_price)
            print(f"  [Cached Shelf Price] {d['canonical_name']}: Base ${cached_price:.2f} -> Effective ${eff_price:.2f}/ea")
        else:
            queries_needing_app.append(term)

    # 2. Query live app for remaining items
    if queries_needing_app:
        print(f"  [App Enrichment] Querying app for {len(queries_needing_app)} uncached items...")
        app_prices = lookup_shelf_fn(queries_needing_app)
        for term, price in app_prices.items():
            d = deal_map.get(term)
            if d and price:
                db.update_product_shelf_price(d["product_id"], price)
                promo_info = PromoExtractor.extract_promo(d.get("promo_detail") or "BUY 1 GET 1 FREE") or PromoInfo(
                    promo_type="bogo",
                    promo_detail=d.get("promo_detail") or "BOGO",
                    buy_qty=1,
                    free_qty=1,
                    qualifying_qty=d.get("qualifying_qty") or 2,
                )
                eff_price = PromoExtractor.calculate_effective_price(promo_info, base_price=price)
                unit_price = round(eff_price / d["unit_size"], 4) if (eff_price and d.get("unit_size")) else None
                db.update_deal_price(d["id"], advertised_price=eff_price, unit_price=unit_price, base_price=price)
                print(f"  [App Scraped Price] {d['canonical_name']}: Base ${price:.2f} -> Effective ${eff_price:.2f}/ea")

    # 3. Disambiguate multi-buy/BOGO collage tiles (Chips, Soda, Mix & Match)
    if disambiguate_fn:
        print("  [App Enrichment] Disambiguating circular collage tiles and unpriced multi-buys...")
        try:
            disambiguate_fn(db)
        except Exception as e:
            print(f"  [App Enrichment] Warning during collage disambiguation: {e}")

    print("--- [App Enrichment] Enrichment complete ---\n")


def _sync_single_store(
    zip_code: str,
    merchant: Optional[str],
    front_page_only: bool = False,
    enrich_app: bool = False,
    db_path: Optional[str] = None,
    use_grid: bool = False,
    front_page_number: Optional[int] = None,
) -> None:
    """Ingest active circular for a specific zip code and merchant."""
    db = DealsDatabase(db_path)
    merchant_label = merchant or "Any"

    # If Giant Food Stores or use_grid requested, use GiantGridFetcher
    if (merchant and "giant" in merchant.lower()) or use_grid:
        from .giant_grid_fetcher import GiantGridFetcher
        print(f"Fetching Giant weekly ad grid & resolving Buy X Get Y prices for ZIP {zip_code}...")
        grid_fetcher = GiantGridFetcher()
        weekly_ad, normalized_deals = grid_fetcher.fetch_circular_deals(zip_code=zip_code)
        
        db.upsert_flyer_run(weekly_ad)
        purged = db.purge_overlapping_untrusted_flyers(
            merchant=weekly_ad.merchant,
            valid_from=weekly_ad.valid_from,
            valid_to=weekly_ad.valid_to,
            keep_flyer_id=weekly_ad.id,
        )
        if purged:
            print(f"Superseded and purged {len(purged)} overlapping backfill circular(s): {purged}")
            
        db.delete_flyer(weekly_ad.id)
        db.upsert_flyer_run(weekly_ad)
        inserted = db.record_deals(normalized_deals)
        print(f"Successfully recorded {inserted} normalized Giant deals (including solved BOGOs & shelf prices) into database.\n")
        return

    fetcher = FlippAdFetcher()
    normalizer = ProductNormalizer()

    print(f"Fetching weekly circulars for ZIP {zip_code} (Merchant: '{merchant_label}')...")
    flyers = fetcher.get_flyers_for_zip(postal_code=zip_code, merchant_filter=merchant)

    if not flyers:
        print(f"No active flyers found for merchant '{merchant}' at ZIP {zip_code}.\n")
        return

    # Select weekly ad
    weekly_ad = next((f for f in flyers if "weekly" in f.name.lower()), flyers[0])
    print(f"Found Circular: {weekly_ad.name} (ID: {weekly_ad.id}) [{weekly_ad.merchant}] | Valid: {weekly_ad.valid_from[:10]} to {weekly_ad.valid_to[:10]}")

    db.upsert_flyer_run(weekly_ad)
    purged = db.purge_overlapping_untrusted_flyers(
        merchant=weekly_ad.merchant,
        valid_from=weekly_ad.valid_from,
        valid_to=weekly_ad.valid_to,
        keep_flyer_id=weekly_ad.id,
    )
    if purged:
        print(f"Superseded and purged {len(purged)} overlapping backfill circular(s): {purged}")

    db.delete_flyer(weekly_ad.id)
    db.upsert_flyer_run(weekly_ad)
    pages, items = fetcher.get_flyer_pages_and_items(
        weekly_ad.id, front_page_only=front_page_only, front_page_number=front_page_number
    )
    print(f"Parsed {len(pages)} pages and {len(items)} items from circular.")

    normalized_batch = []
    for it in items:
        deals = normalizer.disaggregate_and_normalize(it)
        normalized_batch.extend(deals)

    inserted = db.record_deals(normalized_batch)
    print(f"Successfully recorded {inserted} normalized deal observations into database.\n")

    if enrich_app:
        _enrich_deals_with_app(db, weekly_ad.id)


def _get_sync_single_fn():
    """Retrieve _sync_single_store, supporting mock patch on src.cli._sync_single_store."""
    for mod_name in ["src.cli", "deals_tracker.src.cli"]:
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "_sync_single_store"):
            return getattr(mod, "_sync_single_store")
    return _sync_single_store


def cmd_sync(args: argparse.Namespace) -> None:
    """Fetch current circular from Flipp and ingest into SQLite DB."""
    enrich_app = getattr(args, "enrich_app", False)
    fp_num = getattr(args, "front_page_number", None)
    extra_kwargs = {"front_page_number": fp_num} if fp_num is not None else {}
    sync_fn = _get_sync_single_fn()

    # 1. Preset store alias requested
    if getattr(args, "store", None):
        preset = resolve_store(args.store)
        if not preset:
            valid = ", ".join(STORE_PRESETS.keys())
            print(f"Error: Unknown store preset '{args.store}'. Available presets: {valid}")
            sys.exit(1)
        sync_fn(preset["zip"], preset["merchant"], front_page_only=args.front_page_only, enrich_app=enrich_app, db_path=args.db, **extra_kwargs)
        return

    # 2. Explicit ZIP provided
    if args.zip:
        merchant = args.merchant or os.environ.get("TRACKER_MERCHANT")
        sync_fn(args.zip, merchant, front_page_only=args.front_page_only, enrich_app=enrich_app, db_path=args.db, **extra_kwargs)
        return

    # 3. Explicit --all-stores requested
    if getattr(args, "all_stores", False):
        env_stores = os.environ.get("TRACKER_STORES")
        if env_stores:
            store_list = parse_store_configs(env_stores)
        else:
            store_list = [(p["zip"], p["merchant"]) for p in [STORE_PRESETS["giant"], STORE_PRESETS["tomthumb"]]]
        for z, m in store_list:
            sync_fn(z, m, front_page_only=args.front_page_only, enrich_app=enrich_app, db_path=args.db, **extra_kwargs)
        return

    # 4. Fallback to environment variables
    env_stores = os.environ.get("TRACKER_STORES")
    if env_stores and not args.merchant:
        store_list = parse_store_configs(env_stores)
        for z, m in store_list:
            sync_fn(z, m, front_page_only=args.front_page_only, enrich_app=enrich_app, db_path=args.db, **extra_kwargs)
        return

    zip_code = os.environ.get("TRACKER_ZIP")
    merchant = args.merchant or os.environ.get("TRACKER_MERCHANT")
    if zip_code:
        sync_fn(zip_code, merchant, front_page_only=args.front_page_only, enrich_app=enrich_app, db_path=args.db, **extra_kwargs)
        return

    # 5. Default fallback to Tom Thumb
    preset = resolve_store(DEFAULT_STORE)
    if preset:
        sync_fn(preset["zip"], preset["merchant"], front_page_only=args.front_page_only, enrich_app=enrich_app, db_path=args.db, **extra_kwargs)
        return

    print("Error: Missing ZIP code or store. Provide --store <giant|tomthumb>, --zip <ZIP>, or set TRACKER_ZIP / TRACKER_STORES in .env.")
    sys.exit(1)
