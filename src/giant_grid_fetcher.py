"""
giant_grid_fetcher.py
Automated Playwright & In-Page API extractor for Giant Food Stores weekly circulars.
Extracts product catalog records, regular shelf prices, and solves Buy X Get Y / BOGO effective unit prices.
"""

import os
import re
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
from playwright.sync_api import sync_playwright

from .fetcher import FlyerMetadata
from .normalizer.models import NormalizedDeal
from .normalizer.units import extract_unit_info
from .normalizer.categories import infer_department
from .promo_extractor import PromoExtractor, PromoInfo

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class GiantGridFetcher:
    """Automated extractor for Giant Food Stores weekly ad grid and product catalog details."""

    def __init__(self, user_data_dir: Optional[str] = None, headless: bool = False):
        if user_data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.user_data_dir = os.path.join(base_dir, "..", "data", "chrome_profile")
        else:
            self.user_data_dir = user_data_dir
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.headless = headless

    def fetch_circular_deals(
        self,
        grid_url: str = "https://giantfoodstores.com/savings/weekly-ad/grid-view",
        zip_code: str = "17837",
        store_id_override: Optional[str] = None,
    ) -> Tuple[FlyerMetadata, List[NormalizedDeal]]:
        """
        Launch persistent browser context, extract weekly circular items and resolve
        exact shelf prices and effective unit economics for all Buy X Get Y / bundle deals.
        """
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

            # Scroll through page to load all lazy-loaded paginated batches (typically 6 batches = ~354 items)
            for _ in range(12):
                page.evaluate("window.scrollBy(0, 3000)")
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

            normalized_deals: List[NormalizedDeal] = []

            for idx, item in enumerate(ads_list):
                ad_id = int(item.get("id") or (idx + 1))
                circular_id = item.get("circularId")
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
                promo_info = PromoExtractor.extract_promo(sales_text, [name, desc])

                # Check if this item requires in-page details API disambiguation (BOGOs, percent off, dollar off, or unpriced)
                should_disambiguate = bool(
                    circular_id and (
                        (direct_price is None or direct_price == "") or
                        (promo_info and promo_info.promo_type in ("bogo", "percent_off", "dollar_off"))
                    )
                )

                if should_disambiguate:
                    # Query in-page details API for specific product list & regular prices
                    details_url = f"https://giantfoodstores.com/api/v1.0/weekly/circular/users/2/{store_id}/ad/{circular_id}/details"
                    payload = {
                        "query": {"start": 0, "size": 15, "loyaltyCardNumber": ""},
                        "includeAdInfo": False,
                        "enablePersonalization": True,
                        "preview": False,
                    }

                    det_res = page.evaluate(
                        """async ([url, body]) => {
                        try {
                            const resp = await fetch(url, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                                body: JSON.stringify(body)
                            });
                            if (resp.status === 200) return await resp.json();
                        } catch(e) {}
                        return null;
                    }""",
                        [details_url, payload],
                    )

                    products = det_res.get("products", []) if det_res else []
                    if products:
                        for p_idx, prod in enumerate(products):
                            prod_name = (prod.get("name") or name).strip()
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
                                    category=category_name or prod.get("rootCatName"),
                                    promo_detail=p_detail,
                                    qualifying_qty=q_qty,
                                    base_price=reg_price if reg_price > 0 else None,
                                )
                            )
                        continue

                # Standard or priced bundle deals
                adv_price = float(direct_price) if (direct_price is not None and direct_price != "") else None
                
                # Check for X for $Y or other mechanics
                if promo_info:
                    if adv_price is None:
                        adv_price = PromoExtractor.calculate_effective_price(promo_info)
                    promo_type = promo_info.promo_type
                    qualifying_qty = promo_info.qualifying_qty
                    promo_detail = promo_info.promo_detail
                else:
                    promo_type = "standard"
                    qualifying_qty = 1
                    promo_detail = sales_text

                normalized_deals.append(
                    NormalizedDeal(
                        raw_deal_id=ad_id,
                        flyer_id=flyer_id,
                        page_number=page_num,
                        is_front_page=is_front,
                        canonical_name=name,
                        brand=None,
                        advertised_price=adv_price,
                        unit_size=None,
                        unit_type=None,
                        unit_price=None,
                        raw_title=f"{name} - {sales_text}",
                        image_url=image_url,
                        promo_type=promo_type,
                        is_trusted=True,
                        source_type="giant_grid_api",
                        category=category_name,
                        promo_detail=promo_detail,
                        qualifying_qty=qualifying_qty,
                        base_price=None,
                    )
                )

            context.close()
            return flyer_meta, normalized_deals
