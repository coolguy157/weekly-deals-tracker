"""
models.py
Data structures representing normalized deals and circular product items.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedDeal:
    raw_deal_id: int
    flyer_id: int
    page_number: int
    is_front_page: bool
    canonical_name: str
    brand: Optional[str]
    advertised_price: Optional[float]
    unit_size: Optional[float]
    unit_type: Optional[str]
    unit_price: Optional[float]
    raw_title: str
    image_url: Optional[str]
    promo_type: str = "standard"
    is_trusted: bool = True
    source_type: str = "flipp_api"
    category: Optional[str] = None
    promo_detail: Optional[str] = None
    qualifying_qty: int = 1
    base_price: Optional[float] = None
    coupon_discount: Optional[float] = None
