"""
giant_grid_fetcher.py
Automated Playwright & In-Page API extractor for Giant Food Stores weekly circulars.
Extracts product catalog records, regular shelf prices, and solves Buy X Get Y / BOGO effective unit prices.
"""

import os
import sys
import re
import time
import json
import random
import logging
from typing import List, Tuple, Optional, Dict, Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from .fetcher import FlyerMetadata, FlyerItem
from .normalizer.models import NormalizedDeal
from .normalizer.units import extract_unit_info
from .normalizer.categories import infer_category, infer_department
from .normalizer.cleaner import normalize_text, clean_sales_notes
from .normalizer.normalizer import ProductNormalizer
from .promo_extractor import PromoExtractor, PromoInfo

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"


class GiantGridFetcher:
    """Automated extractor for Giant Food Stores weekly ad grid and product catalog details."""

    def __init__(self, user_data_dir: Optional[str] = None, headless: bool = False):
        if user_data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidate_parent = os.path.join(base_dir, "..", "data")
            candidate_local = os.path.join(base_dir, "data")
            target_data_dir = candidate_parent if os.path.exists(candidate_parent) else candidate_local
            self.user_data_dir = os.path.join(target_data_dir, "chrome_profile")
        else:
            self.user_data_dir = user_data_dir
        os.makedirs(self.user_data_dir, exist_ok=True)

        # Fallback to headless on Linux when no X11/wayland display server is active
        if not headless and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            logger.warning("No X11 DISPLAY detected on Linux. Falling back to headless=True.")
            self.headless = True
        else:
            self.headless = headless

        self.normalizer = ProductNormalizer()

    def _wait_for_captcha(self, page, timeout_sec: int = 120) -> bool:
        """Check if DataDome CAPTCHA is present; if so, wait for user to solve it."""
        def is_captcha_present() -> bool:
            try:
                for f in page.frames:
                    if "captcha" in f.url or "captcha-delivery" in f.url:
                        return True
                el = page.query_selector("iframe[src*='captcha'], iframe[src*='captcha-delivery']")
                if el and el.is_visible():
                    return True
            except Exception:
                pass
            return False

        if not is_captcha_present():
            return True

        logger.warning("=" * 60)
        logger.warning("DataDome CAPTCHA detected on Giant Food Stores.")
        logger.warning("Please solve the puzzle in the Chrome browser window.")
        logger.warning("=" * 60)
        print("\n--- [GiantGrid] DataDome CAPTCHA detected. Please solve the puzzle in the open Chrome browser window... ---")

        if sys.platform.startswith("win"):
            try:
                import subprocess
                ps_script = (
                    f'$action = New-ScheduledTaskAction -Execute "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
                    f'-Argument \'--user-data-dir="{self.user_data_dir}" {page.url}\'; '
                    f'$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; '
                    f'Register-ScheduledTask -TaskName "GiantAdWindow" -Action $action -Settings $settings -Force; '
                    f'Start-ScheduledTask -TaskName "GiantAdWindow"'
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=10)
                logger.info("[GiantGrid] Popped open interactive Chrome window via Windows Task Scheduler.")
            except Exception as e_pop:
                logger.warning(f"[GiantGrid] Could not pop window via Task Scheduler: {e_pop}")

        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            time.sleep(1.5)
            if not is_captcha_present():
                print("--- [GiantGrid] CAPTCHA resolved! Continuing sync... ---\n")
                time.sleep(1.5)
                return True

        logger.warning("Timed out waiting for DataDome CAPTCHA to be solved.")
        return False

    def fetch_circular_deals(
        self,
        grid_url: str = "https://giantfoodstores.com/savings/weekly-ad/grid-view",
        zip_code: str = "17837",
        store_id_override: Optional[str] = None,
        disambiguate_all: bool = True,
    ) -> Tuple[FlyerMetadata, List[NormalizedDeal]]:
        """
        Launch persistent browser context, extract weekly circular items and resolve
        exact shelf prices and effective unit economics for all Buy X Get Y / bundle deals.
        """
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is not installed. Install with 'pip install playwright' and 'playwright install chromium'."
            )
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                channel="chrome",
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--window-position=0,0",
                ],
                viewport={"width": 1400, "height": 900},
                user_agent=USER_AGENT,
            )
            page = context.pages[0] if context.pages else context.new_page()

            captured_ads_batches: List[Dict[str, Any]] = []
            ads_endpoint_url: str = ""

            def on_response(resp):
                nonlocal ads_endpoint_url
                if "/weekly/circular/users/2/" in resp.url and "/ads" in resp.url and resp.status == 200:
                    try:
                        captured_ads_batches.append(resp.json())
                        ads_endpoint_url = resp.url
                    except Exception:
                        pass

            page.on("response", on_response)

            logger.info(f"Navigating to Giant Grid View ({grid_url})...")
            page.goto(grid_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            self._wait_for_captcha(page)

            # Scroll through page to load all lazy-loaded paginated batches (typically 6 batches = ~354 items)
            for _ in range(12):
                try:
                    page.evaluate("window.scrollBy(0, 3000)")
                except Exception:
                    page.wait_for_timeout(1500)
                page.wait_for_timeout(1000)

            # Combine and deduplicate all ads across batches
            all_ads_map: Dict[int, Dict[str, Any]] = {}
            valid_from = "2026-10-02"
            valid_to = "2026-10-08"
            flyer_id = 8159694
            thumbnail_url = None

            for b in captured_ads_batches:
                if b.get("adsStartDate"):
                    valid_from = b.get("adsStartDate")
                if b.get("adsEndDate"):
                    valid_to = b.get("adsEndDate")
                if b.get("flyerRunId"):
                    flyer_id = int(b.get("flyerRunId"))
                if b.get("thumbnailImageUrl"):
                    thumbnail_url = b.get("thumbnailImageUrl")
                for a in b.get("ads", []):
                    if a.get("id"):
                        all_ads_map[a["id"]] = a

            ads_list = list(all_ads_map.values())

            # Extract Store ID from endpoint or default
            store_id = store_id_override
            if not store_id and ads_endpoint_url:
                m_store = re.search(r"/users/2/(\d+)/ads", ads_endpoint_url)
                if m_store:
                    store_id = m_store.group(1)
            if not store_id:
                store_id = "50000262"  # Lewisburg default store ID

            # Extract clean date YYYY-MM-DD
            start_date_str = str(valid_from).split("T")[0] if valid_from else "2026-10-02"
            end_date_str = str(valid_to).split("T")[0] if valid_to else "2026-10-08"

            flyer_meta = FlyerMetadata(
                id=flyer_id,
                merchant="Giant Food Stores",
                merchant_id=2,
                name="Giant Weekly Ad (Grid View)",
                postal_code=zip_code,
                valid_from=f"{start_date_str}T00:00:00-04:00",
                valid_to=f"{end_date_str}T23:59:59-04:00",
                thumbnail_url=thumbnail_url,
            )

            logger.info(f"Found {len(ads_list)} circular items from Giant (Flyer ID: {flyer_id}, Store: {store_id})")

            # Build page map from Flipp circular if available
            flipp_page_map: Dict[str, Tuple[int, bool]] = {}
            try:
                from .fetcher import FlippAdFetcher
                flipp_fetcher = FlippAdFetcher()
                flipp_flyers = flipp_fetcher.get_flyers_for_zip(postal_code=zip_code, merchant_filter="Giant")
                if flipp_flyers:
                    for ff in flipp_flyers:
                        _, f_items = flipp_fetcher.get_flyer_pages_and_items(ff.id)
                        for fi in f_items:
                            if fi.name:
                                flipp_page_map[fi.name.lower().strip()] = (fi.page_number, fi.is_front_page)
                logger.info(f"Loaded {len(flipp_page_map)} page mappings from Flipp circular.")
            except Exception as e:
                logger.warning(f"Could not load Flipp page map: {e}")

            # In-page details API enrichment: resolve individual product SKUs, exact brands, sizes, and shelf prices
            details_cache: Dict[int, List[Dict[str, Any]]] = {}
            targets: List[Tuple[int, Any]] = []
            for item in ads_list:
                cid = item.get("circularId")
                aid = int(item.get("id") or 0)
                if not cid or not aid:
                    continue
                if disambiguate_all:
                    targets.append((aid, cid))
                else:
                    s_txt = (item.get("salesText") or "").strip()
                    nm = (item.get("name") or "").strip()
                    ds = (item.get("description") or "").strip()
                    dp = item.get("price")
                    try:
                        dp_val = float(dp) if dp is not None and dp != "" else None
                    except (ValueError, TypeError):
                        dp_val = None
                    p_inf = PromoExtractor.extract_promo(s_txt, [nm, ds], price=dp_val)
                    is_multi = bool(
                        re.search(r"\b(?:or|varieties|select|assorted|mix\s*&\s*match)\b", f"{nm} {ds}", re.IGNORECASE) or
                        (p_inf and p_inf.promo_type in ("must_buy", "quantity_threshold", "mix_and_match"))
                    )
                    if (dp is None or dp == "") or (p_inf and p_inf.promo_type in ("bogo", "percent_off", "dollar_off")) or is_multi:
                        targets.append((aid, cid))

            if targets:
                logger.info(f"Disambiguating {len(targets)} circular items via in-page details API...")
                print(f"\n--- [GiantGrid] Disambiguating {len(targets)} circular items via in-page details API (spread-paced) ---")
                batch_size = 2
                for b_idx in range(0, len(targets), batch_size):
                    chunk = targets[b_idx : b_idx + batch_size]
                    batch_payload = [
                        {
                            "ad_id": aid,
                            "url": f"https://giantfoodstores.com/api/v1.0/weekly/circular/users/2/{store_id}/ad/{cid}/details",
                            "body": {
                                "query": {"start": 0, "size": 30, "loyaltyCardNumber": ""},
                                "includeAdInfo": False,
                                "enablePersonalization": True,
                                "preview": False,
                            },
                        }
                        for aid, cid in chunk
                    ]

                    for _attempt in range(3):
                        batch_res = page.evaluate(
                            """async (batch) => {
                            const promises = batch.map(async (item, idx) => {
                                if (idx > 0) {
                                    await new Promise(r => setTimeout(r, idx * 150));
                                }
                                try {
                                    const resp = await fetch(item.url, {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                            'Accept': 'application/json'
                                        },
                                        body: JSON.stringify(item.body)
                                    });
                                    if (resp.status === 200) {
                                        const data = await resp.json();
                                        return { ad_id: item.ad_id, products: data.products || [] };
                                    }
                                    if (resp.status === 403) {
                                        return { ad_id: item.ad_id, captcha: true };
                                    }
                                } catch (e) {}
                                return { ad_id: item.ad_id, products: [] };
                            });
                            return await Promise.all(promises);
                        }""",
                            batch_payload,
                        )

                        if any(r.get("captcha") for r in (batch_res or [])):
                            logger.warning(f"[GiantGrid] DataDome 403 detected at item {b_idx + 1}/{len(targets)}. Auto-refreshing page so CAPTCHA appears...")
                            print(f"\n--- [GiantGrid] DataDome 403 detected at item {b_idx + 1}/{len(targets)}. Auto-refreshing page to trigger CAPTCHA modal... ---")
                            try:
                                page.reload(wait_until="domcontentloaded", timeout=30000)
                                page.wait_for_timeout(2500)
                            except Exception as e_reload:
                                logger.warning(f"[GiantGrid] Page reload warning: {e_reload}")
                            solved = self._wait_for_captcha(page)
                            if solved:
                                time.sleep(random.uniform(2.5, 4.0))
                            continue

                        for r in (batch_res or []):
                            aid = r.get("ad_id")
                            if aid:
                                details_cache[aid] = r.get("products") or []
                        break

                    # Spaced and randomized jitter delay between batches
                    pace_delay = random.uniform(0.65, 1.25)
                    if (b_idx // batch_size + 1) % 12 == 0:
                        pace_delay += random.uniform(1.2, 2.5)
                    time.sleep(pace_delay)

                    done = min(b_idx + batch_size, len(targets))
                    if done % 25 == 0 or done == len(targets):
                        print(f"  [GiantGrid] Details progress: {done}/{len(targets)} circular items processed...")

            normalized_deals: List[NormalizedDeal] = []

            for idx, item in enumerate(ads_list):
                ad_id = int(item.get("id") or (idx + 1))
                name = (item.get("name") or "").strip()
                desc = (item.get("description") or "").strip()
                sales_text = (item.get("salesText") or "").strip()
                direct_price = item.get("price")
                category_name = item.get("categories", [{}])[0].get("name") if item.get("categories") else None
                images = item.get("images", {})
                image_url = images.get("medium") or images.get("small")

                # Resolve true flyer page number
                pg_info = flipp_page_map.get(name.lower())
                if not pg_info:
                    for fk, fv in flipp_page_map.items():
                        if fk in name.lower() or name.lower() in fk:
                            pg_info = fv
                            break

                if pg_info:
                    page_num = pg_info[0]
                    is_front = pg_info[1]
                else:
                    # Extended online grid item not in print circular: resolve by category / keyword
                    dept_page_map = {
                        "Produce": 12, "Meat & Seafood": 4, "Deli": 17, "Bakery": 2,
                        "Dairy": 13, "Frozen": 14, "Pantry": 15, "Beverages": 11,
                        "Snacks & Candy": 15, "Canned Goods": 15, "Personal Care": 19,
                        "Health": 19, "Household": 20, "Pet Care": 19, "Baby": 23,
                        "General Merchandise": 22,
                    }
                    combined_tag = f"{name} {desc} {category_name or ''}".lower()
                    inferred_dept = infer_department(combined_tag)
                    page_num = dept_page_map.get(inferred_dept, 15) if inferred_dept else 15
                    is_front = False

                # Extract promotional information via centralized PromoExtractor
                try:
                    dp_val = float(direct_price) if direct_price is not None and direct_price != "" else None
                except (ValueError, TypeError):
                    dp_val = None
                promo_info = PromoExtractor.extract_promo(sales_text, [name, desc], price=dp_val)

                # Check if we have disambiguated products from details API
                products = details_cache.get(ad_id, [])
                clean_parent_name = clean_sales_notes(normalize_text(name)) or normalize_text(name)
                parent_cat = infer_category(clean_parent_name) or category_name

                if products:
                    for p_idx, prod in enumerate(products):
                        raw_pname = (prod.get("name") or name).strip()
                        prod_name = clean_sales_notes(normalize_text(raw_pname)) or normalize_text(raw_pname)
                        prod_brand = prod.get("brand")
                        reg_price = prod.get("regularPrice") or prod.get("price") or 0.0
                        size_str = prod.get("size", "")
                        
                        # Parse unit size via centralized UnitNormalizer
                        unit_size, unit_type = extract_unit_info(size_str) if size_str else (None, None)

                        # Calculate effective price via centralized PromoExtractor
                        effective_price = None
                        if promo_info:
                            effective_price = PromoExtractor.calculate_effective_price(promo_info, base_price=reg_price)
                        
                        if effective_price is None:
                            if direct_price is not None and direct_price != "":
                                effective_price = float(direct_price)
                            elif prod.get("price") and prod.get("price") != reg_price:
                                effective_price = float(prod.get("price"))
                            elif reg_price > 0 and promo_info and promo_info.promo_type == "bogo":
                                buy_qty = promo_info.buy_qty or 1
                                free_qty = promo_info.free_qty or 1
                                total_qty = promo_info.qualifying_qty or (buy_qty + free_qty)
                                effective_price = round((buy_qty * reg_price) / total_qty, 2)
                            elif reg_price > 0:
                                effective_price = float(reg_price)

                        unit_price = round(effective_price / unit_size, 4) if (effective_price and unit_size and unit_size > 0) else None

                        prod_img = prod.get("image", {}).get("large") or image_url
                        deal_id = int(f"{ad_id}{p_idx}")
                        p_type = promo_info.promo_type if promo_info else "standard"
                        p_detail = promo_info.promo_detail if promo_info else sales_text
                        q_qty = promo_info.qualifying_qty if promo_info else 1

                        cat = parent_cat or infer_category(prod_name) or prod.get("rootCatName")

                        normalized_deals.append(
                            NormalizedDeal(
                                raw_deal_id=deal_id,
                                flyer_id=flyer_id,
                                page_number=page_num,
                                is_front_page=is_front,
                                canonical_name=prod_name,
                                brand=prod_brand,
                                advertised_price=effective_price,
                                unit_size=unit_size,
                                unit_type=unit_type,
                                unit_price=unit_price,
                                raw_title=f"{prod_name} - {sales_text}",
                                image_url=prod_img,
                                promo_type=p_type,
                                is_trusted=True,
                                source_type="giant_grid_api",
                                category=cat,
                                promo_detail=p_detail,
                                qualifying_qty=q_qty,
                                base_price=reg_price if reg_price > 0 else None,
                                ad_title=clean_parent_name,
                            )
                        )
                    continue

                # Standard or priced bundle deals: Route through ProductNormalizer for disaggregation,
                # unit detection, coordinate expansion, and category inference.
                clean_item_name = normalize_text(name)
                adv_price = float(direct_price) if (direct_price is not None and direct_price != "") else None
                if promo_info:
                    eff_price = PromoExtractor.calculate_effective_price(promo_info, base_price=adv_price)
                    if eff_price is not None:
                        adv_price = eff_price
                if adv_price is None and sales_text:
                    m = re.search(r"\$(\d+(?:\.\d{2})?)", sales_text)
                    if m:
                        adv_price = float(m.group(1))

                flyer_item = FlyerItem(
                    id=ad_id,
                    flyer_id=flyer_id,
                    name=clean_item_name,
                    price=adv_price,
                    original_price=None,
                    pre_price_text=sales_text,
                    post_price_text=desc,
                    description=desc,
                    brand=item.get("brand"),
                    page_number=page_num,
                    is_front_page=is_front,
                    cutout_image_url=image_url,
                    clean_image_url=image_url,
                )

                norm_items = self.normalizer.disaggregate_and_normalize(flyer_item)
                for norm_item in norm_items:
                    norm_item.source_type = "giant_grid_api"
                    norm_item.is_trusted = True
                    norm_item.ad_title = clean_item_name
                    if not norm_item.category and category_name:
                        norm_item.category = category_name
                    normalized_deals.append(norm_item)

            context.close()
            return flyer_meta, normalized_deals
