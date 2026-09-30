"""
Deal intelligence and historical price trend analyzer.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from .database import DealsDatabase


@dataclass
class PromoEpisode:
    price: float
    unit_price: Optional[float]
    valid_from: str
    valid_to: str
    promo_type: str
    observations_count: int


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
    unit_size: Optional[float] = None
    unit_type: Optional[str] = None


class DealAnalyzer:
    """Calculates deal quality scores, All-Time Lows (ATL), and historical discounts."""

    def __init__(self, db: DealsDatabase, max_episode_gap_days: int = 10):
        self.db = db
        self.max_episode_gap_days = max_episode_gap_days

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> datetime:
        if not date_str:
            return datetime.min
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return datetime.min

    def cluster_episodes(self, observations: List[Dict[str, Any]]) -> List[PromoEpisode]:
        """
        Groups contiguous circular observations with the same price into a single promotional episode.
        """
        valid_obs = [obs for obs in observations if obs.get("advertised_price") is not None]
        if not valid_obs:
            return []

        sorted_obs = sorted(valid_obs, key=lambda o: self._parse_date(o.get("valid_from") or o.get("recorded_at")))
        episodes: List[PromoEpisode] = []

        for obs in sorted_obs:
            price = obs["advertised_price"]
            obs_start = self._parse_date(obs.get("valid_from") or obs.get("recorded_at"))

            if not episodes:
                episodes.append(
                    PromoEpisode(
                        price=price,
                        unit_price=obs.get("unit_price"),
                        valid_from=obs.get("valid_from") or "",
                        valid_to=obs.get("valid_to") or "",
                        promo_type=obs.get("promo_type") or "standard",
                        observations_count=1,
                    )
                )
                continue

            last_ep = episodes[-1]
            last_end = self._parse_date(last_ep.valid_to or last_ep.valid_from)
            days_gap = (obs_start - last_end).days if (obs_start != datetime.min and last_end != datetime.min) else 999

            # Same price and contiguous within max_episode_gap_days
            if abs(price - last_ep.price) < 0.005 and 0 <= days_gap <= self.max_episode_gap_days:
                last_ep.valid_to = obs.get("valid_to") or last_ep.valid_to
                last_ep.observations_count += 1
                if obs.get("promo_type") in ("doorbuster", "outlier"):
                    last_ep.promo_type = obs.get("promo_type")
            else:
                episodes.append(
                    PromoEpisode(
                        price=price,
                        unit_price=obs.get("unit_price"),
                        valid_from=obs.get("valid_from") or "",
                        valid_to=obs.get("valid_to") or "",
                        promo_type=obs.get("promo_type") or "standard",
                        observations_count=1,
                    )
                )

        return episodes

    def evaluate_deal(
        self, deal_record: Dict[str, Any], current_flyer_id: Optional[int] = None
    ) -> DealEvaluation:
        """Evaluate a deal against its recorded history using episode clustering."""
        product_id = deal_record["product_id"]
        current_price = deal_record.get("advertised_price")
        history = self.db.get_product_price_history(product_id)

        # Exclude observations from current flyer and concurrent/overlapping date window
        target_flyer_id = current_flyer_id or deal_record.get("flyer_id")
        current_valid_from = (deal_record.get("valid_from") or "")[:10]
        past_obs = [
            h for h in history
            if h.get("flyer_id") != target_flyer_id
            and (not current_valid_from or (h.get("valid_from") or "")[:10] < current_valid_from)
            and h.get("advertised_price") is not None
        ]

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
                past_observations_count=len(past_obs),
                diff_pct_vs_avg=None,
                badge="SEE_AD",
                summary_reason="Price not listed numerically in circular",
                unit_size=deal_record.get("unit_size"),
                unit_type=deal_record.get("unit_type"),
            )

        if not past_obs:
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
                unit_size=deal_record.get("unit_size"),
                unit_type=deal_record.get("unit_type"),
            )

        episodes = self.cluster_episodes(past_obs)
        past_prices = [h["advertised_price"] for h in past_obs]
        h_min = min(past_prices)
        h_max = max(past_prices)

        # Baseline non-doorbuster episodes for averages & hike comparisons
        baseline_episodes = [
            ep for ep in episodes if ep.promo_type not in ("doorbuster", "outlier")
        ]
        if not baseline_episodes:
            baseline_episodes = episodes

        b_min = min(ep.price for ep in baseline_episodes)
        b_max = max(ep.price for ep in baseline_episodes)
        b_avg = sum(ep.price for ep in baseline_episodes) / len(baseline_episodes)
        diff_vs_avg = ((current_price - b_avg) / b_avg) * 100.0

        # Check for contiguous multi-week continuation
        sorted_past = sorted(past_obs, key=lambda o: self._parse_date(o.get("valid_from") or o.get("recorded_at")))
        last_obs = sorted_past[-1]
        last_end = self._parse_date(last_obs.get("valid_to") or last_obs.get("valid_from"))
        curr_start = self._parse_date(current_valid_from)
        days_since_last = (curr_start - last_end).days if (curr_start != datetime.min and last_end != datetime.min) else 999
        is_contiguous_continuation = (
            abs(current_price - last_obs["advertised_price"]) < 0.005
            and 0 <= days_since_last <= self.max_episode_gap_days
        )

        badge = "STANDARD_DEAL"
        reason = f"Past sale range: ${b_min:.2f} - ${b_max:.2f} (avg ${b_avg:.2f})"

        # Has historical variation beyond a single flat price?
        has_price_variation = (h_max - h_min) >= 0.05

        if is_contiguous_continuation:
            # Multi-week promotion continuation
            if current_price <= h_min and has_price_variation:
                badge = "ALL_TIME_LOW"
                reason = f"🌟 Multi-week sale at All-Time Low (${h_min:.2f})"
            else:
                badge = "CYCLE_REFRESH"
                reason = f"🔄 Ongoing multi-week promotion (${current_price:.2f})"
        elif current_price < (h_min - 0.005):
            badge = "ALL_TIME_LOW"
            diff_min = ((current_price - h_min) / h_min) * 100.0
            reason = f"🌟 New All-Time Low! {abs(diff_min):.1f}% below past low of ${h_min:.2f}"
        elif abs(current_price - h_min) <= 0.005:
            if has_price_variation:
                badge = "ALL_TIME_LOW"
                reason = f"🌟 Matches All-Time Low (${h_min:.2f})"
            else:
                badge = "CYCLE_REFRESH"
                reason = f"🔄 Standard promo cycle (typical: ${h_min:.2f})"
        elif current_price <= (b_avg * 0.85):
            badge = "BEAT_AVERAGE"
            reason = f"🔥 {abs(diff_vs_avg):.1f}% below historical average of ${b_avg:.2f}"
        elif current_price <= b_avg or abs(current_price - b_min) < 0.05:
            badge = "CYCLE_REFRESH"
            if abs(b_min - b_max) < 0.01:
                reason = f"🔄 Standard promo cycle (typical: ${b_min:.2f})"
            else:
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
            unit_size=deal_record.get("unit_size"),
            unit_type=deal_record.get("unit_type"),
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
