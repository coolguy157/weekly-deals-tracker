"""
promo_extractor.py
Rule-based promotional mechanics extractor for unpriced and compound grocery deals.
Parses BOGOs, 'Must Buy' quantity thresholds, 'X for $Y' bundles, and digital coupon discounts.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import re


@dataclass
class PromoInfo:
    promo_type: str  # 'bogo', 'must_buy', 'digital_coupon', 'standard'
    promo_detail: str  # e.g., 'BUY 2 GET 2 FREE', 'MUST BUY 4 @ $2.49', '2 FOR $5.00'
    buy_qty: Optional[int] = None
    free_qty: Optional[int] = None
    discount_pct: Optional[float] = None  # e.g., 50.0 for Buy 1 Get 1 50% off
    qualifying_qty: int = 1
    stated_unit_price: Optional[float] = None
    stated_total_price: Optional[float] = None
    coupon_price: Optional[float] = None
    coupon_discount: Optional[float] = None


class PromoExtractor:
    """Extracts structured promotional information from ad text, descriptions, and pre/post price notes."""

    # 1. BOGO Patterns
    # "BUY 2 GET 2 FREE", "BUY 1 GET 1 FREE", "BUY 2 GET 3 FREE"
    BOGO_PATTERN = re.compile(
        r"\bBUY\s+(\d+|ONE|TWO|THREE)\s+GET\s+(\d+|ONE|TWO|THREE)\s+(?:OF\s+EQUAL\s+OR\s+LESSER\s+VALUE\s+)?FREE\b",
        re.IGNORECASE,
    )
    # "BUY 1 GET 1 50% OFF", "BUY 1 GET 1 HALF OFF"
    BOGO_DISCOUNT_PATTERN = re.compile(
        r"\bBUY\s+(\d+|ONE|TWO)\s+GET\s+(\d+|ONE|TWO)\s+(?:AT\s+)?(?:(\d+)%\s*OFF|HALF\s+OFF|50%\s*OFF)\b",
        re.IGNORECASE,
    )
    # Generic "BOGO FREE" or "BUY ONE GET ONE FREE"
    GENERIC_BOGO_PATTERN = re.compile(
        r"\b(?:BOGO\s+FREE|BUY\s+ONE\s+GET\s+ONE\s+FREE)\b",
        re.IGNORECASE,
    )

    # 2. Must Buy / Minimum Quantity Patterns
    # "MUST BUY 4 @ $2.49", "WHEN YOU BUY 4 $2.49 EA", "MUST BUY 3 OR MORE $1.99 EA"
    MUST_BUY_PRICE_PATTERN = re.compile(
        r"\b(?:MUST\s+BUY|WHEN\s+YOU\s+BUY|BUY)\s+(\d+)(?:\s+OR\s+MORE)?(?:.*?)(?:@|\$)\s*(\d+(?:\.\d{2})?)(?:\s*(?:EA|EACH))?\b",
        re.IGNORECASE,
    )
    # "MUST BUY 4", "WHEN YOU BUY 4" (without explicit unit price)
    MUST_BUY_QTY_ONLY_PATTERN = re.compile(
        r"\b(?:MUST\s+BUY|WHEN\s+YOU\s+BUY)\s+(\d+)\b",
        re.IGNORECASE,
    )
    # "2 FOR $5", "3 FOR $10.00", "4 FOR $5"
    X_FOR_Y_PATTERN = re.compile(
        r"\b(\d+)\s+FOR\s+\$(\d+(?:\.\d{2})?)\b",
        re.IGNORECASE,
    )

    # 3. Digital Coupon / Member Discount Patterns
    # "WITH DIGITAL COUPON $1.99", "FOR U FINAL PRICE $2.49", "WITH FOR U COUPON $1.49"
    COUPON_FINAL_PRICE_PATTERN = re.compile(
        r"\b(?:WITH\s+)?(?:DIGITAL\s+COUPON|FOR\s*U\s*COUPON|FOR\s*U|JUST\s*FOR\s*U|MEMBER\s+PRICE|WITH\s+CARD).*?\$(\d+(?:\.\d{2})?)\b",
        re.IGNORECASE,
    )
    # "SAVE $1.00 WITH DIGITAL COUPON", "$1.00 OFF WITH DIGITAL COUPON"
    COUPON_DISCOUNT_PATTERN = re.compile(
        r"\b(?:SAVE\s+)?\$?(\d+(?:\.\d{2})?)\s*(?:OFF)?\s*(?:WITH\s+)?(?:DIGITAL\s+COUPON|FOR\s*U)\b",
        re.IGNORECASE,
    )

    WORD_TO_NUM = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
    }

    @classmethod
    def _word_or_digit_to_int(cls, val: str) -> int:
        clean = val.strip().lower()
        if clean in cls.WORD_TO_NUM:
            return cls.WORD_TO_NUM[clean]
        try:
            return int(clean)
        except ValueError:
            return 1

    @classmethod
    def extract_promo(
        cls,
        text: Optional[str],
        additional_texts: Optional[List[Optional[str]]] = None,
    ) -> Optional[PromoInfo]:
        """
        Examine text and auxiliary fields (pre-price, post-price, description) for promo patterns.
        Returns PromoInfo or None if standard/no promo detected.
        """
        all_candidates = []
        if text:
            all_candidates.append(text)
        if additional_texts:
            for t in additional_texts:
                if t:
                    all_candidates.append(t)

        combined_text = " ".join(all_candidates).strip()
        if not combined_text:
            return None

        # 1. BOGO Check
        m_bogo = cls.BOGO_PATTERN.search(combined_text)
        if m_bogo:
            buy_qty = cls._word_or_digit_to_int(m_bogo.group(1))
            free_qty = cls._word_or_digit_to_int(m_bogo.group(2))
            total_qty = buy_qty + free_qty
            detail = f"BUY {buy_qty} GET {free_qty} FREE"
            return PromoInfo(
                promo_type="bogo",
                promo_detail=detail,
                buy_qty=buy_qty,
                free_qty=free_qty,
                qualifying_qty=total_qty,
            )

        m_bogo_disc = cls.BOGO_DISCOUNT_PATTERN.search(combined_text)
        if m_bogo_disc:
            buy_qty = cls._word_or_digit_to_int(m_bogo_disc.group(1))
            free_qty = cls._word_or_digit_to_int(m_bogo_disc.group(2))
            pct = float(m_bogo_disc.group(3)) if m_bogo_disc.group(3) else 50.0
            total_qty = buy_qty + free_qty
            detail = f"BUY {buy_qty} GET {free_qty} {int(pct)}% OFF"
            return PromoInfo(
                promo_type="bogo",
                promo_detail=detail,
                buy_qty=buy_qty,
                free_qty=free_qty,
                discount_pct=pct,
                qualifying_qty=total_qty,
            )

        if cls.GENERIC_BOGO_PATTERN.search(combined_text):
            return PromoInfo(
                promo_type="bogo",
                promo_detail="BUY 1 GET 1 FREE",
                buy_qty=1,
                free_qty=1,
                qualifying_qty=2,
            )

        # 2. Must Buy Check
        m_mb_price = cls.MUST_BUY_PRICE_PATTERN.search(combined_text)
        if m_mb_price:
            qty = int(m_mb_price.group(1))
            unit_price = float(m_mb_price.group(2))
            detail = f"MUST BUY {qty} @ ${unit_price:.2f}"
            return PromoInfo(
                promo_type="must_buy",
                promo_detail=detail,
                qualifying_qty=qty,
                stated_unit_price=unit_price,
            )

        m_x_for_y = cls.X_FOR_Y_PATTERN.search(combined_text)
        if m_x_for_y:
            qty = int(m_x_for_y.group(1))
            total_price = float(m_x_for_y.group(2))
            unit_price = round(total_price / qty, 2) if qty > 0 else total_price
            detail = f"{qty} FOR ${total_price:.2f}"
            return PromoInfo(
                promo_type="must_buy",
                promo_detail=detail,
                qualifying_qty=qty,
                stated_unit_price=unit_price,
                stated_total_price=total_price,
            )

        m_mb_qty = cls.MUST_BUY_QTY_ONLY_PATTERN.search(combined_text)
        if m_mb_qty:
            qty = int(m_mb_qty.group(1))
            return PromoInfo(
                promo_type="must_buy",
                promo_detail=f"MUST BUY {qty}",
                qualifying_qty=qty,
            )

        # 3. Digital Coupon Check
        m_coup_price = cls.COUPON_FINAL_PRICE_PATTERN.search(combined_text)
        if m_coup_price:
            price = float(m_coup_price.group(1))
            return PromoInfo(
                promo_type="digital_coupon",
                promo_detail=f"DIGITAL COUPON ${price:.2f}",
                coupon_price=price,
                qualifying_qty=1,
            )

        m_coup_disc = cls.COUPON_DISCOUNT_PATTERN.search(combined_text)
        if m_coup_disc:
            disc = float(m_coup_disc.group(1))
            return PromoInfo(
                promo_type="digital_coupon",
                promo_detail=f"SAVE ${disc:.2f} WITH DIGITAL COUPON",
                coupon_discount=disc,
                qualifying_qty=1,
            )

        return None

    @classmethod
    def calculate_effective_price(
        cls,
        promo: PromoInfo,
        base_price: Optional[float] = None,
    ) -> Optional[float]:
        """
        Compute net effective price per single unit based on promotional mechanics.
        - BOGO: (base_price * buy_qty) / (buy_qty + free_qty)
        - Must Buy @ $X: $X
        - X for $Y: $Y / X
        - Digital Coupon Price: coupon_price
        - Digital Coupon Discount: base_price - discount
        """
        if promo.promo_type == "bogo":
            if base_price is not None and base_price > 0:
                buy = promo.buy_qty or 1
                free = promo.free_qty or 1
                total = buy + free
                if promo.discount_pct is not None:
                    # e.g., Buy 1 Get 1 50% off -> total cost = base_price * (1 + (1 - discount_pct/100))
                    discount_multiplier = 1.0 - (promo.discount_pct / 100.0)
                    total_cost = (base_price * buy) + (base_price * free * discount_multiplier)
                    return round((total_cost / total) + 1e-9, 2)
                else:
                    # Pure free items
                    total_cost = base_price * buy
                    return round((total_cost / total) + 1e-9, 2)
            return None

        if promo.promo_type == "must_buy":
            if promo.stated_unit_price is not None:
                return promo.stated_unit_price
            if promo.stated_total_price is not None and promo.qualifying_qty > 0:
                return round((promo.stated_total_price / promo.qualifying_qty) + 1e-9, 2)
            return None

        if promo.promo_type == "digital_coupon":
            if promo.coupon_price is not None:
                return promo.coupon_price
            if promo.coupon_discount is not None and base_price is not None:
                return max(0.0, round(base_price - promo.coupon_discount + 1e-9, 2))
            return None

        return None
