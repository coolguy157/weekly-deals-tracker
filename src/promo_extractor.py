"""
promo_extractor.py
Rule-based promotional mechanics extractor for unpriced and compound grocery deals.
Parses BOGOs, 'Must Buy' quantity thresholds, 'X for $Y' bundles, and digital coupon discounts.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import re


@dataclass
class PromoInfo:
    promo_type: str  # 'bogo', 'must_buy', 'digital_coupon', 'points_redemption', 'points_bonus', 'spend_save', 'percent_off', 'standard'
    promo_detail: str  # e.g., 'BUY 2 GET 2 FREE', 'MUST BUY 4 @ $2.49', '2 FOR $5.00'
    buy_qty: Optional[int] = None
    free_qty: Optional[int] = None
    discount_pct: Optional[float] = None  # e.g., 50.0 for Buy 1 Get 1 50% off or 25% Off
    qualifying_qty: int = 1
    stated_unit_price: Optional[float] = None
    stated_total_price: Optional[float] = None
    coupon_price: Optional[float] = None
    coupon_discount: Optional[float] = None
    points_cost: Optional[int] = None  # e.g., 75, 100, 175
    points_saved_val: Optional[float] = None  # e.g., 1.89, 2.79, 5.00
    points_bonus: Optional[int] = None  # e.g., 300
    points_multiplier: Optional[float] = None  # e.g., 10.0 for 10x
    spend_threshold: Optional[float] = None  # e.g., 20.00
    est_reward_val: Optional[float] = None  # e.g., estimated dollar value of bonus points
    est_net_price: Optional[float] = None  # e.g., spend_threshold - est_reward_val


class PromoExtractor:
    """Extracts structured promotional information from ad text, descriptions, and pre/post price notes."""

    # Default estimated point value (derived from circular grocery freebie redemption: ~2.74¢/pt)
    DEFAULT_POINT_VALUE = 0.0274

    # 1. BOGO Patterns
    # "BUY 2 GET 2 FREE", "BUY 1 GET 1 FREE", "BUY 2 GET 3 FREE", "BUY 5 GET 1 FREE"
    BOGO_PATTERN = re.compile(
        r"\bBUY\s+(\d+|ONE|TWO|THREE|FOUR|FIVE|SIX)\s+GET\s+(\d+|ONE|TWO|THREE|FOUR|FIVE|SIX)\s+(?:OF\s+EQUAL\s+OR\s+LESSER\s+VALUE\s+)?(?:MUST\s+BUY\s+LIKE\s+BRAND\s+)?FREE\b",
        re.IGNORECASE,
    )
    # "BUY 1 GET 1 50% OFF", "BUY 1 GET 1 HALF OFF"
    BOGO_DISCOUNT_PATTERN = re.compile(
        r"\bBUY\s+(\d+|ONE|TWO|THREE|FOUR)\s+GET\s+(\d+|ONE|TWO|THREE|FOUR)\s+(?:AT\s+)?(?:(\d+)%\s*OFF|HALF\s+OFF|50%\s*OFF)\b",
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
    # "WITH DIGITAL COUPON $1.99", "FOR U FINAL PRICE $2.49", "$2.99 /lb. DIGITAL COUPON"
    COUPON_FINAL_PRICE_PATTERN = re.compile(
        r"(?:\b(?:WITH\s+)?(?:DIGITAL\s+COUPON|FOR\s*U\s*COUPON|FOR\s*U|JUST\s*FOR\s*U|MEMBER\s+PRICE|WITH\s+CARD).*?\$(\d+(?:\.\d{2})?)\b|\$(\d+(?:\.\d{2})?)(?:\s*/\s*(?:lb|ea|count|oz|pkg))?\.?\s*(?:DIGITAL\s+COUPON|FOR\s*U\s*COUPON|FOR\s*U|JUST\s*FOR\s*U|MEMBER\s+PRICE|WITH\s+CARD)\b)",
        re.IGNORECASE,
    )
    # "SAVE $1.00 WITH DIGITAL COUPON", "$1.00 OFF WITH DIGITAL COUPON"
    COUPON_DISCOUNT_PATTERN = re.compile(
        r"\b(?:SAVE\s+)?\$?(\d+(?:\.\d{2})?)\s*(?:OFF)?\s*(?:WITH\s+)?(?:DIGITAL\s+COUPON|FOR\s*U)\b",
        re.IGNORECASE,
    )

    # 4. Points Redemption Patterns (Buy with points / Free with points)
    # "FREE ... when you redeem 75 CHOICE points", "5-POINT FREEBIE", "5 POINT FREEBIE", "when you redeem 100 CHOICE points"
    REDEEM_POINTS_PATTERN = re.compile(
        r"(?:REDEEM\s+(\d+)\s+(?:CHOICE\s+)?POINTS|(\d+)[-\s]+POINT\s+FREEBIE)",
        re.IGNORECASE,
    )
    POINTS_SAVE_AMT_PATTERN = re.compile(
        r"SAVE\s+(?:UP\s+TO\s+|AT\s+LEAST\s+)?\$(\d+(?:\.\d{2})?)",
        re.IGNORECASE,
    )

    # 5. Extra Points / Points Bonus Patterns
    # "300 CHOICE POINTS When you spend $20", "EARN 10X CHOICE POINTS", "EARN 200 CHOICE POINTS"
    BONUS_POINTS_SPEND_PATTERN = re.compile(
        r"(\d+)\s+(?:CHOICE\s+)?POINTS\s+WHEN\s+YOU\s+SPEND\s+\$(\d+(?:\.\d{2})?)",
        re.IGNORECASE,
    )
    BONUS_POINTS_BUY_PATTERN = re.compile(
        r"(\d+)\s+(?:CHOICE\s+)?POINTS\s+WHEN\s+YOU\s+BUY\s+(\d+)",
        re.IGNORECASE,
    )
    EARN_POINTS_MULT_PATTERN = re.compile(
        r"EARN\s+(\d+)X\s+(?:CHOICE\s+)?POINTS",
        re.IGNORECASE,
    )

    # 6. Spend & Save / Multi-Buy Threshold Patterns
    # "SAVE $5 When you spend $20 on participating products", "SAVE $15 When you buy 3"
    SPEND_SAVE_PATTERN = re.compile(
        r"SAVE\s+\$(\d+(?:\.\d{2})?)\s+WHEN\s+YOU\s+SPEND\s+\$(\d+(?:\.\d{2})?)",
        re.IGNORECASE,
    )
    BUY_SAVE_PATTERN = re.compile(
        r"SAVE\s+\$(\d+(?:\.\d{2})?)\s+WHEN\s+YOU\s+BUY\s+(\d+)",
        re.IGNORECASE,
    )

    # 7. Percentage Off Patterns
    # "25% Off", "33% Off"
    PCT_OFF_PATTERN = re.compile(
        r"\b(\d+)%\s*OFF\b",
        re.IGNORECASE,
    )

    # 8. Dollar Off / Off-Shelf Discount Patterns
    # "$1.00 Off", "$2.00 Off", "50¢ Off", "2 Off/lb.", "SAVE up to $3.79"
    DOLLAR_OFF_PATTERN = re.compile(
        r"\b(?:SAVE\s+(?:UP\s+TO\s+)?|.*?\$|\b)(\d+(?:\.\d{2})?)\s*(?:OFF(?:\/LB\.?)?)\b",
        re.IGNORECASE,
    )
    CENTS_OFF_PATTERN = re.compile(
        r"\b(\d+)\s*¢\s*OFF\b",
        re.IGNORECASE,
    )

    # 9. Meal Deal / Buy Main Item Get Sides Free Patterns
    # "buy this Our Brand Boneless Beef Chuck Roast get these FREE* ... SAVE at least $8.27* with this week's meal deal"
    MEAL_DEAL_PATTERN = re.compile(
        r"(?:BUY\s+THIS\s+(.*?)\s+GET\s+THESE\s+FREE.*?(?:SAVE\s+(?:AT\s+LEAST\s+)?\$(\d+(?:\.\d{2})?))?.*?(?:MEAL\s+DEAL)?|MEAL\s+DEAL)",
        re.IGNORECASE,
    )

    WORD_TO_NUM = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
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
        point_value: float = DEFAULT_POINT_VALUE,
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

        # Normalize bullets, middle dots, special dashes, etc. to spaces
        cleaned_text = re.sub(r"[•・·\-\*]+", " ", combined_text)
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

        # 0. Meal Deal / Buy Main Get Sides Free Check
        if "meal deal" in cleaned_text.lower() or ("buy this" in cleaned_text.lower() and "get these free" in cleaned_text.lower()):
            m_main = re.search(r"BUY\s+THIS\s+(.*?)\s+GET\s+THESE\s+FREE", cleaned_text, re.IGNORECASE)
            main_item = m_main.group(1).strip() if m_main else ""
            m_save = re.search(r"SAVE\s+(?:UP\s+TO\s+|AT\s+LEAST\s+)?\$(\d+(?:\.\d{2})?)", cleaned_text, re.IGNORECASE)
            save_amt = float(m_save.group(1)) if m_save else None

            # Clean anchor item name if matched
            if main_item:
                main_item = re.sub(r"(?i)\b(?:Butcher Shop|U\.?S\.?D\.?A\.?|Choice|Fresh|Vacuum Sealed)\b.*", "", main_item).strip()
            detail = "Weekly Meal Deal"
            if main_item and save_amt:
                detail = f"Weekly Meal Deal: Buy {main_item} (Save ${save_amt:.2f})"
            elif main_item:
                detail = f"Weekly Meal Deal: Buy {main_item}"
            elif save_amt:
                detail = f"Weekly Meal Deal (Save ${save_amt:.2f})"
            return PromoInfo(
                promo_type="meal_deal",
                promo_detail=detail,
                qualifying_qty=1,
                coupon_discount=save_amt,
            )

        # 1. BOGO Check
        m_bogo = cls.BOGO_PATTERN.search(cleaned_text)
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

        m_bogo_disc = cls.BOGO_DISCOUNT_PATTERN.search(cleaned_text)
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

        if cls.GENERIC_BOGO_PATTERN.search(cleaned_text):
            return PromoInfo(
                promo_type="bogo",
                promo_detail="BUY 1 GET 1 FREE",
                buy_qty=1,
                free_qty=1,
                qualifying_qty=2,
            )

        # 2. Points Redemption (Buy with points)
        m_red = cls.REDEEM_POINTS_PATTERN.search(cleaned_text)
        if m_red:
            pts_val = int(m_red.group(1) or m_red.group(2))
            m_sv = cls.POINTS_SAVE_AMT_PATTERN.search(cleaned_text)
            saved = float(m_sv.group(1)) if m_sv else None
            detail = f"FREE with {pts_val} CHOICE points" + (f" (Save ${saved:.2f})" if saved else "")
            return PromoInfo(
                promo_type="points_redemption",
                promo_detail=detail,
                points_cost=pts_val,
                points_saved_val=saved,
                stated_unit_price=0.0,
                qualifying_qty=1,
            )

        # 3. Extra Points / Points Bonus
        m_bsp = cls.BONUS_POINTS_SPEND_PATTERN.search(cleaned_text)
        if m_bsp:
            pts = int(m_bsp.group(1))
            spend = float(m_bsp.group(2))
            reward_val = round(pts * point_value, 2)
            net_spend = round(max(0.0, spend - reward_val), 2)
            detail = f"{pts} CHOICE POINTS When you spend ${spend:.2f} (~${reward_val:.2f} reward value, Est. Net ${net_spend:.2f})"
            return PromoInfo(
                promo_type="points_bonus",
                promo_detail=detail,
                points_bonus=pts,
                spend_threshold=spend,
                est_reward_val=reward_val,
                est_net_price=net_spend,
                qualifying_qty=1,
            )

        m_em = cls.EARN_POINTS_MULT_PATTERN.search(cleaned_text)
        if m_em:
            mult = float(m_em.group(1))
            pct_back = round(mult * point_value * 100, 1)
            detail = f"EARN {int(mult)}X CHOICE POINTS (~{pct_back}% back in grocery rewards)"
            return PromoInfo(
                promo_type="points_bonus",
                promo_detail=detail,
                points_multiplier=mult,
                qualifying_qty=1,
            )

        m_bq = cls.BONUS_POINTS_BUY_PATTERN.search(cleaned_text)
        if m_bq:
            pts = int(m_bq.group(1))
            buy_q = int(m_bq.group(2))
            reward_val = round(pts * point_value, 2)
            detail = f"EARN {pts} CHOICE POINTS When you buy {buy_q} (~${reward_val:.2f} reward value)"
            return PromoInfo(
                promo_type="points_bonus",
                promo_detail=detail,
                points_bonus=pts,
                qualifying_qty=buy_q,
                est_reward_val=reward_val,
            )

        # 4. Spend & Save Threshold
        m_ss = cls.SPEND_SAVE_PATTERN.search(cleaned_text)
        if m_ss:
            save_amt = float(m_ss.group(1))
            spend_amt = float(m_ss.group(2))
            net_spend = round(max(0.0, spend_amt - save_amt), 2)
            detail = f"SAVE ${save_amt:.2f} When you spend ${spend_amt:.2f} (Net Spend: ${net_spend:.2f})"
            return PromoInfo(
                promo_type="spend_save",
                promo_detail=detail,
                spend_threshold=spend_amt,
                coupon_discount=save_amt,
                est_net_price=net_spend,
                qualifying_qty=1,
            )

        m_bs = cls.BUY_SAVE_PATTERN.search(cleaned_text)
        if m_bs:
            save_amt = float(m_bs.group(1))
            buy_qty = int(m_bs.group(2))
            detail = f"SAVE ${save_amt:.2f} When you buy {buy_qty}"
            return PromoInfo(
                promo_type="must_buy",
                promo_detail=detail,
                coupon_discount=save_amt,
                qualifying_qty=buy_qty,
            )

        # 5. Must Buy Check
        m_mb_price = cls.MUST_BUY_PRICE_PATTERN.search(cleaned_text)
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

        m_x_for_y = cls.X_FOR_Y_PATTERN.search(cleaned_text)
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

        m_mb_qty = cls.MUST_BUY_QTY_ONLY_PATTERN.search(cleaned_text)
        if m_mb_qty:
            qty = int(m_mb_qty.group(1))
            return PromoInfo(
                promo_type="must_buy",
                promo_detail=f"MUST BUY {qty}",
                qualifying_qty=qty,
            )

        # 6. Digital Coupon Check
        m_coup_price = cls.COUPON_FINAL_PRICE_PATTERN.search(cleaned_text)
        if m_coup_price:
            price_str = m_coup_price.group(1) or m_coup_price.group(2)
            price = float(price_str)
            return PromoInfo(
                promo_type="digital_coupon",
                promo_detail=f"DIGITAL COUPON ${price:.2f}",
                coupon_price=price,
                qualifying_qty=1,
            )

        m_coup_disc = cls.COUPON_DISCOUNT_PATTERN.search(cleaned_text)
        if m_coup_disc:
            disc = float(m_coup_disc.group(1))
            return PromoInfo(
                promo_type="digital_coupon",
                promo_detail=f"SAVE ${disc:.2f} WITH DIGITAL COUPON",
                coupon_discount=disc,
                qualifying_qty=1,
            )

        # 7. Percentage Off Check (e.g. 25% Off)
        m_pct = cls.PCT_OFF_PATTERN.search(cleaned_text)
        if m_pct and not m_bogo_disc:
            pct_val = float(m_pct.group(1))
            return PromoInfo(
                promo_type="percent_off",
                promo_detail=f"{int(pct_val)}% OFF",
                discount_pct=pct_val,
                qualifying_qty=1,
            )

        # 8. Dollar Off / Off-Shelf Discount Check
        m_do = cls.DOLLAR_OFF_PATTERN.search(cleaned_text)
        if m_do:
            off_val = float(m_do.group(1))
            return PromoInfo(
                promo_type="dollar_off",
                promo_detail=f"${off_val:.2f} OFF",
                coupon_discount=off_val,
                qualifying_qty=1,
            )

        m_co = cls.CENTS_OFF_PATTERN.search(cleaned_text)
        if m_co:
            cents_val = float(m_co.group(1)) / 100.0
            return PromoInfo(
                promo_type="dollar_off",
                promo_detail=f"{int(m_co.group(1))}¢ OFF",
                coupon_discount=cents_val,
                qualifying_qty=1,
            )

        return None

    @classmethod
    def calculate_effective_price(
        cls,
        promo: PromoInfo,
        base_price: Optional[float] = None,
        point_value: float = DEFAULT_POINT_VALUE,
    ) -> Optional[float]:
        """
        Compute net effective price per single unit based on promotional mechanics.
        - BOGO: (base_price * buy_qty) / (buy_qty + free_qty)
        - Must Buy @ $X: $X
        - X for $Y: $Y / X
        - Digital Coupon Price: coupon_price
        - Digital Coupon Discount: base_price - discount
        - Points Redemption: 0.0 (Free with points)
        - Points Bonus: spend_threshold - (points_bonus * point_value) or base_price - (points_bonus * point_value)
        - Percent Off: base_price * (1 - discount_pct/100)
        - Dollar Off: base_price - coupon_discount
        - Spend & Save: spend_threshold - discount
        """
        if promo.promo_type == "bogo":
            if base_price is not None and base_price > 0:
                buy = promo.buy_qty or 1
                free = promo.free_qty or 1
                total = buy + free
                if promo.discount_pct is not None:
                    discount_multiplier = 1.0 - (promo.discount_pct / 100.0)
                    total_cost = (base_price * buy) + (base_price * free * discount_multiplier)
                    return round((total_cost / total) + 1e-9, 2)
                else:
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

        if promo.promo_type == "points_redemption":
            return 0.0

        if promo.promo_type == "points_bonus":
            if promo.est_net_price is not None:
                return promo.est_net_price
            if promo.points_bonus and base_price is not None:
                reward = promo.points_bonus * point_value
                return max(0.0, round(base_price - reward + 1e-9, 2))
            return None

        if promo.promo_type == "percent_off":
            if base_price is not None and promo.discount_pct is not None:
                multiplier = 1.0 - (promo.discount_pct / 100.0)
                return max(0.0, round(base_price * multiplier + 1e-9, 2))
            return None

        if promo.promo_type == "dollar_off":
            if base_price is not None and promo.coupon_discount is not None:
                return max(0.0, round(base_price - promo.coupon_discount + 1e-9, 2))
            return None

        if promo.promo_type == "spend_save":
            if promo.est_net_price is not None:
                return promo.est_net_price
            if promo.spend_threshold is not None and promo.coupon_discount is not None:
                return max(0.0, round(promo.spend_threshold - promo.coupon_discount + 1e-9, 2))
            return None

        return None

    @classmethod
    def calculate_dynamic_point_value(
        cls,
        items: List[Any],
        default_value: float = DEFAULT_POINT_VALUE,
        min_points_threshold: int = 50,
        exclude_points: Tuple[int, ...] = (5, 10),
    ) -> float:
        """
        Dynamically calculates the baseline point value ($/point) from standard grocery redemption promotions.
        Explicitly excludes promotional doorbusters/freebies (e.g. 5-point freebies) to avoid skewing standard reward valuation.
        """
        redemption_values = []
        for item in items:
            p_info = None
            if isinstance(item, PromoInfo):
                p_info = item
            elif isinstance(item, dict):
                p_text = f"{item.get('raw_title') or ''} {item.get('promo_detail') or ''}"
                p_info = cls.extract_promo(p_text, [item.get("canonical_name")])

            if p_info and p_info.promo_type == "points_redemption" and p_info.points_cost and p_info.points_saved_val:
                # Specifically ignore 5-point freebies and small loss-leader doorbusters
                if p_info.points_cost not in exclude_points and p_info.points_cost >= min_points_threshold:
                    redemption_values.append(p_info.points_saved_val / p_info.points_cost)

        if redemption_values:
            return round(sum(redemption_values) / len(redemption_values), 4)
        return default_value

