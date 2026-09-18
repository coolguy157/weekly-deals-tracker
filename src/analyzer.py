"""
Deal intelligence and historical price trend analyzer.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from .database import DealsDatabase


@dataclass
class DealEvaluation:
    deal_id: int
    product_id: int
    canonical_name: str
    brand: Optional[str]
    current_price: Optional[float]
    unit_price: Optional[float]
    page_number: int
    is_front_page: bool
    historical_min: Optional[float]
    historical_avg: Optional[float]
    historical_max: Optional[float]
    past_observations_count: int
    diff_pct_vs_avg: Optional[float]
    badge: str
    summary_reason: str


class DealAnalyzer:
    """Calculates deal quality scores, All-Time Lows (ATL), and historical discounts."""

    def __init__(self, db: DealsDatabase):
        self.db = db

    def evaluate_deal(
        self, deal_record: Dict[str, Any], current_flyer_id: Optional[int] = None
    ) -> DealEvaluation:
        """Evaluate a deal against its recorded history."""
        product_id = deal_record["product_id"]
        current_price = deal_record.get("advertised_price")
        history = self.db.get_product_price_history(product_id)

        # Exclude the observation from the current flyer if comparing
        target_flyer_id = current_flyer_id or deal_record.get("flyer_id")
        past_obs = [
            h for h in history
            if h.get("flyer_id") != target_flyer_id and h.get("advertised_price") is not None
        ]
        past_prices = [h["advertised_price"] for h in past_obs]

        # Non-doorbuster baseline for averages & hike comparisons
        baseline_prices = [
            h["advertised_price"] for h in past_obs
            if h.get("promo_type") not in ("doorbuster", "outlier")
        ]
        if not baseline_prices:
            baseline_prices = past_prices

        if current_price is None:
            return DealEvaluation(
                deal_id=deal_record.get("id", 0),
                product_id=product_id,
                canonical_name=deal_record.get("canonical_name", ""),
                brand=deal_record.get("brand"),
                current_price=None,
                unit_price=deal_record.get("unit_price"),
                page_number=deal_record.get("page_number", 1),
                is_front_page=bool(deal_record.get("is_front_page", 1)),
                historical_min=None,
                historical_avg=None,
                historical_max=None,
                past_observations_count=len(past_prices),
                diff_pct_vs_avg=None,
                badge="SEE_AD",
                summary_reason="Price not listed numerically in circular",
            )

        if not past_prices:
            return DealEvaluation(
                deal_id=deal_record.get("id", 0),
                product_id=product_id,
                canonical_name=deal_record.get("canonical_name", ""),
                brand=deal_record.get("brand"),
                current_price=current_price,
                unit_price=deal_record.get("unit_price"),
                page_number=deal_record.get("page_number", 1),
                is_front_page=bool(deal_record.get("is_front_page", 1)),
                historical_min=current_price,
                historical_avg=current_price,
                historical_max=current_price,
                past_observations_count=0,
                diff_pct_vs_avg=0.0,
                badge="FIRST_SEEN",
                summary_reason="First time tracked in circular database",
            )

        h_min = min(past_prices)
        h_max = max(past_prices)

        b_min = min(baseline_prices)
        b_max = max(baseline_prices)
        b_avg = sum(baseline_prices) / len(baseline_prices)
        diff_vs_avg = ((current_price - b_avg) / b_avg) * 100.0

        badge = "STANDARD_DEAL"
        reason = f"Past sale range: ${b_min:.2f} - ${b_max:.2f} (avg ${b_avg:.2f})"

        if current_price <= h_min:
            badge = "ALL_TIME_LOW"
            if current_price < h_min:
                diff_min = ((current_price - h_min) / h_min) * 100.0
                reason = f"🌟 New All-Time Low! {abs(diff_min):.1f}% below past low of ${h_min:.2f}"
            else:
                reason = f"🌟 Matches All-Time Low (${h_min:.2f})"
        elif current_price <= (b_avg * 0.85):
            badge = "BEAT_AVERAGE"
            reason = f"🔥 {abs(diff_vs_avg):.1f}% below historical average of ${b_avg:.2f}"
        elif current_price <= b_avg or abs(current_price - b_min) < 0.05:
            badge = "CYCLE_REFRESH"
            reason = f"🔄 Standard promo cycle (typical: ${b_min:.2f} - ${b_avg:.2f})"
        elif current_price > (b_avg * 1.15) or current_price > b_max:
            badge = "PRICE_HIKE"
            reason = f"⚠️ Higher than typical promo average (+{diff_vs_avg:.1f}% vs avg ${b_avg:.2f})"

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=deal_record.get("canonical_name", ""),
            brand=deal_record.get("brand"),
            current_price=current_price,
            unit_price=deal_record.get("unit_price"),
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=round(h_min, 2),
            historical_avg=round(b_avg, 2),
            historical_max=round(h_max, 2),
            past_observations_count=len(past_prices),
            diff_pct_vs_avg=round(diff_vs_avg, 1),
            badge=badge,
            summary_reason=reason,
        )

    def evaluate_flyer(
        self, flyer_id: int, front_page_only: bool = False
    ) -> List[DealEvaluation]:
        """Evaluate all deals in a circular against historical data."""
        deals = self.db.get_deals_for_flyer(flyer_id, front_page_only=front_page_only)
        evaluations = [self.evaluate_deal(d, current_flyer_id=flyer_id) for d in deals]

        # Prioritize All-Time Lows and Beat Average deals first
        priority_order = {
            "ALL_TIME_LOW": 0,
            "BEAT_AVERAGE": 1,
            "CYCLE_REFRESH": 2,
            "FIRST_SEEN": 3,
            "STANDARD_DEAL": 4,
            "PRICE_HIKE": 5,
            "SEE_AD": 6,
        }
        evaluations.sort(key=lambda x: (priority_order.get(x.badge, 99), x.current_price or 999))
        return evaluations
