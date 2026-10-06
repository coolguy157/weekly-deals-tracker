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
from .promo_extractor import PromoExtractor, PromoInfo

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

WORD_TO_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
BOGO_REGEX = re.compile(r"BUY\s+(\d+|ONE|TWO|THREE|FOUR)[\s\W_]+GET\s+(\d+|ONE|TWO|THREE|FOUR)[\s\W_]+FREE", re.IGNORECASE)


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

                # Check if this item is a Buy X Get Y / BOGO deal
                m_bogo = BOGO_REGEX.search(sales_text)
                if m_bogo and circular_id:
                    b_str = m_bogo.group(1).lower()
                    g_str = m_bogo.group(2).lower()
                    buy_qty = WORD_TO_NUM.get(b_str, int(b_str) if b_str.isdigit() else 1)
                    free_qty = WORD_TO_NUM.get(g_str, int(g_str) if g_str.isdigit() else 1)
                    total_qty = buy_qty + free_qty

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
                            
                            # Parse unit size if available
                            unit_size = None
                            unit_type = None
                            if size_str:
                                m_sz = re.search(r"(\d+(?:\.\d+)?)\s*(OZ|LB|CT|FL\s*OZ|PKG|BAG)", size_str, re.IGNORECASE)
                                if m_sz:
                                    unit_size = float(m_sz.group(1))
                                    unit_type = m_sz.group(2).lower()

                            total_cost = round(buy_qty * reg_price, 2)
                            effective_price = round(total_cost / total_qty, 2)
                            unit_price = round(effective_price / unit_size, 4) if (unit_size and unit_size > 0) else None

                            prod_img = prod.get("image", {}).get("large") or image_url
                            deal_id = int(f"{ad_id}{p_idx}")

                            normalized_deals.append(
                                NormalizedDeal(
                                    raw_deal_id=deal_id,
                                    flyer_id=flyer_id,
                                    page_number=1,
                                    is_front_page=True,
                                    canonical_name=prod_name,
                                    brand=prod_brand,
                                    advertised_price=effective_price,
                                    unit_size=unit_size,
                                    unit_type=unit_type,
                                    unit_price=unit_price,
                                    raw_title=f"{prod_name} - {sales_text}",
                                    image_url=prod_img,
                                    promo_type="bogo",
                                    is_trusted=True,
                                    source_type="giant_grid_api",
                                    category=category_name or prod.get("rootCatName"),
                                    promo_detail=f"BUY {buy_qty} GET {free_qty} FREE",
                                    qualifying_qty=total_qty,
                                    base_price=reg_price,
                                )
                            )
                        continue

                # Standard or priced bundle deals
                promo_info = PromoExtractor.extract_promo(sales_text, [name, desc])
                adv_price = float(direct_price) if (direct_price is not None and direct_price != "") else None
                
                # Check for X for $Y
                m_xfory = re.search(r"(\d+)\s*/\s*\$?(\d+(?:\.\d{2})?)", sales_text)
                if m_xfory:
                    qty = int(m_xfory.group(1))
                    total_p = float(m_xfory.group(2))
                    adv_price = round(total_p / qty, 2)
                    promo_type = "must_buy"
                    qualifying_qty = qty
                elif m_bogo:
                    promo_type = "bogo"
                    qualifying_qty = 2
                else:
                    promo_type = promo_info.promo_type if promo_info else "standard"
                    qualifying_qty = promo_info.qualifying_qty if promo_info else 1

                normalized_deals.append(
                    NormalizedDeal(
                        raw_deal_id=ad_id,
                        flyer_id=flyer_id,
                        page_number=1,
                        is_front_page=True,
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
                        promo_detail=sales_text,
                        qualifying_qty=qualifying_qty,
                        base_price=None,
                    )
                )

            context.close()
            return flyer_meta, normalized_deals
