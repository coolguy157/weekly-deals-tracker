"""
Flipp API circular fetcher and coordinate parser.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import urllib.request
import urllib.error
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class FlyerMetadata:
    id: int
    merchant: str
    merchant_id: int
    name: str
    postal_code: str
    valid_from: str
    valid_to: str
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    width: float = 0.0
    height: float = 0.0
    thumbnail_url: Optional[str] = None


@dataclass
class FlyerPage:
    id: int
    page_number: int
    name: str
    left: float
    right: float
    top: float
    bottom: float


@dataclass
class FlyerItem:
    id: int
    flyer_id: int
    name: str
    price: Optional[float]
    original_price: Optional[float]
    pre_price_text: Optional[str]
    post_price_text: Optional[str]
    description: Optional[str]
    brand: Optional[str]
    page_number: int
    is_front_page: bool
    cutout_image_url: Optional[str]
    clean_image_url: Optional[str]
    left: float = 0.0
    right: float = 0.0
    top: float = 0.0
    bottom: float = 0.0
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class FlippAdFetcher:
    """Client for querying Flipp's public flyer and item API endpoints."""

    BASE_URL = "https://backflipp.wishabi.com/flipp"

    def __init__(self, timeout: int = 30, user_agent: str = USER_AGENT):
        self.timeout = timeout
        self.user_agent = user_agent

    def _get_json(self, endpoint_url: str, retries: int = 3, backoff_sec: float = 2.0) -> Dict[str, Any]:
        last_err = None
        for attempt in range(retries):
            req = urllib.request.Request(
                endpoint_url,
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    return json.loads(raw_bytes.decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_err = e
                logger.warning(f"HTTP error {e.code} querying {endpoint_url} (attempt {attempt + 1}/{retries}): {e.reason}")
                if attempt < retries - 1 and e.code in (500, 502, 503, 504, 429):
                    import time
                    time.sleep(backoff_sec * (attempt + 1))
                    continue
                raise
            except Exception as e:
                last_err = e
                logger.warning(f"Error querying {endpoint_url} (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(backoff_sec * (attempt + 1))
                    continue
                raise
        if last_err:
            raise last_err

    def get_flyers_for_zip(
        self, postal_code: str, merchant_filter: Optional[str] = None, locale: str = "en-us"
    ) -> List[FlyerMetadata]:
        """Fetch all active circulars for a postal code, optionally filtering by merchant."""
        url = f"{self.BASE_URL}/flyers?postal_code={postal_code}&locale={locale}"
        data = self._get_json(url)
        raw_flyers = data.get("flyers", [])

        results: List[FlyerMetadata] = []
        for f in raw_flyers:
            merchant_name = f.get("merchant", "")
            if merchant_filter and merchant_filter.lower() not in merchant_name.lower():
                continue

            results.append(
                FlyerMetadata(
                    id=f["id"],
                    merchant=merchant_name,
                    merchant_id=f.get("merchant_id", 0),
                    name=f.get("name", "Weekly Ad"),
                    postal_code=str(f.get("postal_code", postal_code)),
                    valid_from=f.get("valid_from", ""),
                    valid_to=f.get("valid_to", ""),
                    available_from=f.get("available_from"),
                    available_to=f.get("available_to"),
                    width=float(f.get("width", 0.0)),
                    height=float(f.get("height", 0.0)),
                    thumbnail_url=f.get("thumbnail_url"),
                )
            )
        return results

    @staticmethod
    def _detect_front_page_number(pages: List[FlyerPage], page_items_map: Dict[int, list]) -> int:
        """
        Detect the true front page number of the weekly circular.
        Handles circular formats where multi-month promotional inserts (e.g. Tom Thumb's
        'Savings Lock' pages) precede the actual weekly ad cover page.
        """
        if not pages:
            return 1

        for page in pages:
            p_items = page_items_map.get(page.page_number, [])
            if not p_items:
                continue

            has_weekly_item = False
            has_dates = False
            for it in p_items:
                v_from = it.get("valid_from")
                v_to = it.get("valid_to")
                if v_from and v_to:
                    try:
                        d_from = datetime.fromisoformat(str(v_from)[:10])
                        d_to = datetime.fromisoformat(str(v_to)[:10])
                        has_dates = True
                        if (d_to - d_from).days <= 21:
                            has_weekly_item = True
                            break
                    except Exception:
                        pass

            if not has_dates or has_weekly_item:
                return page.page_number

        return 1

    def get_flyer_pages_and_items(
        self,
        flyer_id: int,
        front_page_only: bool = False,
        front_page_number: Optional[int] = None,
    ) -> tuple[List[FlyerPage], List[FlyerItem]]:
        """Fetch the full flyer payload and resolve items to flyer pages using coordinate math."""
        url = f"{self.BASE_URL}/flyers/{flyer_id}"
        data = self._get_json(url)

        # 1. Parse pages
        pages: List[FlyerPage] = []
        for p in data.get("pages", []):
            pages.append(
                FlyerPage(
                    id=p.get("id", 0),
                    page_number=int(p.get("page", 1)),
                    name=p.get("name", f"Page {p.get('page', 1)}"),
                    left=float(p.get("left", 0.0)),
                    right=float(p.get("right", 0.0)),
                    top=float(p.get("top", 0.0)),
                    bottom=float(p.get("bottom", 0.0)),
                )
            )

        # Sort pages by page number
        pages.sort(key=lambda x: x.page_number)

        # 2. Parse items and assign page based on coordinate overlap
        raw_items = data.get("items", [])
        page_items_map: Dict[int, list] = {}
        assigned_raw: List[tuple] = []

        for it in raw_items:
            it_left = float(it.get("left", 0.0))
            it_right = float(it.get("right", 0.0))
            it_center_x = (it_left + it_right) / 2.0 if (it_left and it_right) else it_left

            # Find matching page
            item_page_num = 1
            for page in pages:
                if page.left <= it_center_x <= page.right:
                    item_page_num = page.page_number
                    break

            page_items_map.setdefault(item_page_num, []).append(it)
            assigned_raw.append((it, item_page_num, it_left, it_right))

        # Detect front page number (handles multi-month Savings Lock inserts preceding weekly cover)
        target_front_page = front_page_number or self._detect_front_page_number(pages, page_items_map)

        items: List[FlyerItem] = []
        for it, item_page_num, it_left, it_right in assigned_raw:
            is_front_page = (item_page_num == target_front_page)
            if front_page_only and not is_front_page:
                continue

            price_val = it.get("price")
            if price_val is None:
                price_val = it.get("current_price")
            try:
                price_float = float(price_val) if price_val is not None else None
            except (ValueError, TypeError):
                price_float = None

            orig_price_val = it.get("original_price")
            try:
                orig_float = float(orig_price_val) if orig_price_val is not None else None
            except (ValueError, TypeError):
                orig_float = None

            items.append(
                FlyerItem(
                    id=it.get("id", 0),
                    flyer_id=flyer_id,
                    name=it.get("name", "").strip(),
                    price=price_float,
                    original_price=orig_float,
                    pre_price_text=it.get("pre_price_text"),
                    post_price_text=it.get("post_price_text"),
                    description=it.get("description"),
                    brand=it.get("brand"),
                    page_number=item_page_num,
                    is_front_page=is_front_page,
                    cutout_image_url=it.get("cutout_image_url"),
                    clean_image_url=it.get("clean_image_url"),
                    left=it_left,
                    right=it_right,
                    top=float(it.get("top", 0.0)),
                    bottom=float(it.get("bottom", 0.0)),
                    raw_payload=it,
                )
            )

        return pages, items
