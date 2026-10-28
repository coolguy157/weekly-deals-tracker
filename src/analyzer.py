"""
Deal intelligence and historical price trend analyzer.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from .database import DealsDatabase
from .normalizer.cleaner import GENERIC_PLACEHOLDER_NAMES


@dataclass
class PromoEpisode:
    price: float
    unit_price: Optional[float]
    valid_from: str
    valid_to: str
    promo_type: str
    observations_count: int
    is_trusted: bool = True


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
    category: Optional[str] = None
    category_min_unit_price: Optional[float] = None
    category_avg_unit_price: Optional[float] = None
    promo_type: str = "standard"
    promo_detail: Optional[str] = None
    qualifying_qty: int = 1
    base_price: Optional[float] = None
    raw_deal_id: Optional[int] = None
    ad_id: Optional[str] = None
    ad_title: Optional[str] = None
    raw_title: Optional[str] = None
    image_url: Optional[str] = None

    @property
    def is_category_best(self) -> bool:
        """Returns True if this deal is the lowest unit price across all brands in its commodity category."""
        if self.category and self.unit_price is not None and self.category_min_unit_price is not None:
            return self.unit_price <= (self.category_min_unit_price + 0.005)
        return False


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
            obs_trusted = bool(obs.get("is_trusted", 1))

            if not episodes:
                episodes.append(
                    PromoEpisode(
                        price=price,
                        unit_price=obs.get("unit_price"),
                        valid_from=obs.get("valid_from") or "",
                        valid_to=obs.get("valid_to") or "",
                        promo_type=obs.get("promo_type") or "standard",
                        observations_count=1,
                        is_trusted=obs_trusted,
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
                if obs_trusted:
                    last_ep.is_trusted = True
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
                        is_trusted=obs_trusted,
                    )
                )

        return episodes

    def evaluate_deal(
        self,
        deal_record: Dict[str, Any],
        current_flyer_id: Optional[int] = None,
        flyer_cat_mins: Optional[Dict[Tuple[str, str], float]] = None,
        point_value: float = 0.0274,
        history_override: Optional[List[Dict[str, Any]]] = None,
        ad_title_cache: Optional[Dict[Any, List[Dict[str, Any]]]] = None,
        cat_cache: Optional[Dict[Tuple[str, str], List[Dict[str, Any]]]] = None,
    ) -> DealEvaluation:
        """Evaluate a deal against its recorded history using episode clustering."""
        product_id = deal_record["product_id"]
        current_price = deal_record.get("advertised_price")
        if history_override is not None:
            history = history_override
        else:
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

        # Scope price history: prioritize same-merchant history to prevent cross-banner distortions
        merchant = (deal_record.get("merchant") or "").strip().lower()
        if merchant:
            same_merchant_obs = [
                h for h in past_obs
                if (h.get("merchant") or "").strip().lower() == merchant
            ]
            if same_merchant_obs:
                past_obs = same_merchant_obs
            else:
                # Only fall back to other banners if unit size and type strictly match
                cur_u_size = deal_record.get("unit_size")
                cur_u_type = deal_record.get("unit_type")
                if cur_u_size and cur_u_type:
                    past_obs = [
                        h for h in past_obs
                        if h.get("unit_size") == cur_u_size and h.get("unit_type") == cur_u_type
                    ]
                else:
                    past_obs = []

        # Check parent ad_title history when individual SKU has no prior exact-match history
        ad_title = (deal_record.get("ad_title") or "").strip()
        if not past_obs and ad_title and ad_title.lower() not in GENERIC_PLACEHOLDER_NAMES:
            if ad_title_cache is not None:
                cache_key = (ad_title.lower(), target_flyer_id, current_valid_from, merchant)
                if cache_key not in ad_title_cache:
                    ad_title_cache[cache_key] = self.db.get_ad_title_price_history(
                        ad_title,
                        target_flyer_id=target_flyer_id,
                        current_valid_from=current_valid_from,
                        merchant=merchant,
                    )
                parent_past = ad_title_cache[cache_key]
            else:
                parent_past = self.db.get_ad_title_price_history(
                    ad_title,
                    target_flyer_id=target_flyer_id,
                    current_valid_from=current_valid_from,
                    merchant=merchant,
                )
            if parent_past:
                past_obs = parent_past

        # Tier 3: Category Unit Benchmark across all brands
        category = deal_record.get("category")
        unit_size = deal_record.get("unit_size")
        unit_type = deal_record.get("unit_type")
        unit_price = deal_record.get("unit_price")
        if unit_price is None and current_price is not None and unit_size and unit_size > 0:
            unit_price = round(current_price / unit_size, 4)

        cat_min_unit = None
        cat_avg_unit = None
        if category and unit_price is not None and unit_type:
            cat_key = (category.lower(), unit_type.lower())
            if cat_cache is not None:
                if cat_key not in cat_cache:
                    cat_history = self.db.get_commodity_unit_price_history(category, unit_type=unit_type)
                    cat_cache[cat_key] = [
                        h for h in cat_history
                        if h.get("flyer_id") != target_flyer_id
                        and (not current_valid_from or (h.get("valid_from") or "")[:10] < current_valid_from)
                        and h.get("unit_price") is not None
                    ]
                cat_past_obs = cat_cache[cat_key]
            else:
                cat_history = self.db.get_commodity_unit_price_history(category, unit_type=unit_type)
                cat_past_obs = [
                    h for h in cat_history
                    if h.get("flyer_id") != target_flyer_id
                    and (not current_valid_from or (h.get("valid_from") or "")[:10] < current_valid_from)
                    and h.get("unit_price") is not None
                ]
            cat_unit_prices = [h["unit_price"] for h in cat_past_obs] if cat_past_obs else []
            if flyer_cat_mins:
                f_min = flyer_cat_mins.get(cat_key)
                if f_min is not None:
                    cat_unit_prices = list(cat_unit_prices) + [f_min]
            if cat_unit_prices:
                cat_min_unit = min(cat_unit_prices)
                cat_avg_unit = sum(cat_unit_prices) / len(cat_unit_prices)

        promo_type = deal_record.get("promo_type") or "standard"
        promo_detail = deal_record.get("promo_detail")
        qualifying_qty = deal_record.get("qualifying_qty") or 1
        base_price = deal_record.get("base_price") or deal_record.get("last_shelf_price")
        raw_title = deal_record.get("raw_title") or ""
        canonical_name = deal_record.get("canonical_name") or ""
        raw_deal_id = deal_record.get("raw_deal_id")
        image_url = deal_record.get("image_url")

        # Derive parent ad_id
        ad_id = None
        if raw_deal_id is not None:
            raw_id_str = str(raw_deal_id)
            if len(raw_id_str) >= 11:
                ad_id = raw_id_str[:10]
            else:
                ad_id = raw_id_str

        # Extract structured promo info if present
        from .promo_extractor import PromoExtractor
        promo_info = PromoExtractor.extract_promo(promo_detail or raw_title, [raw_title, canonical_name], point_value=point_value)
        if promo_info:
            promo_type = promo_info.promo_type
            if not promo_detail or promo_type in ("points_redemption", "points_bonus", "spend_save", "percent_off"):
                promo_detail = promo_info.promo_detail
            qualifying_qty = promo_info.qualifying_qty

        promo_note = ""
        if promo_type == "bogo":
            if base_price:
                promo_note = f" • [{promo_detail or 'BOGO Free'} (Base ${base_price:.2f})]"
            else:
                promo_note = f" • [{promo_detail or 'BOGO Free'}]"
        elif promo_type == "must_buy":
            promo_note = f" • [{promo_detail or f'Must Buy {qualifying_qty}'}]"
        elif promo_type == "digital_coupon":
            promo_note = f" • [{promo_detail or 'Digital Coupon'}]"
        elif promo_type == "points_redemption":
            promo_note = f" • [{promo_detail or 'Buy with Points'}]"
        elif promo_type == "points_bonus":
            promo_note = f" • [{promo_detail or 'Points Reward'}]"
        elif promo_type == "spend_save":
            promo_note = f" • [{promo_detail or 'Spend & Save'}]"
        elif promo_type == "percent_off":
            promo_note = f" • [{promo_detail or 'Percent Off'}]"
        elif promo_type == "meal_deal":
            promo_note = f" • [{promo_detail or 'Weekly Meal Deal'}]"

        cat_note = ""
        if cat_min_unit is not None and cat_avg_unit is not None and unit_price is not None:
            if unit_price <= (cat_min_unit + 0.005):
                cat_note = f" • 🏆 Best {category} price/{unit_type} across all brands"
            elif unit_price <= (cat_avg_unit * 0.85):
                diff_cat = abs(int(((unit_price - cat_avg_unit) / cat_avg_unit) * 100.0))
                cat_note = f" • 🔥 {diff_cat}% below {category} category avg"
            elif unit_price > (cat_avg_unit * 1.15):
                diff_cat = int(((unit_price - cat_avg_unit) / cat_avg_unit) * 100.0)
                cat_note = f" • ⚠️ Above {category} category avg (+{diff_cat}%)"

        # Dispatch to specialized promo evaluators if applicable
        if promo_type == "points_redemption" and promo_info:
            return self._evaluate_points_redemption(
                deal_record, product_id, canonical_name, base_price, promo_info,
                point_value, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
                qualifying_qty, raw_deal_id, ad_id, raw_title, image_url, past_obs,
            )

        if promo_type == "points_bonus" and promo_info:
            return self._evaluate_points_bonus(
                deal_record, product_id, canonical_name, current_price, promo_info,
                point_value, unit_price, unit_type, category, cat_min_unit,
                cat_avg_unit, promo_type, promo_detail, qualifying_qty, base_price,
                raw_deal_id, ad_id, raw_title, image_url, past_obs,
            )

        if promo_type == "spend_save" and promo_info:
            return self._evaluate_spend_save(
                deal_record, product_id, canonical_name, unit_price, unit_type,
                category, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
                qualifying_qty, raw_deal_id, ad_id, raw_title, image_url, past_obs,
                promo_info,
            )

        if promo_type == "percent_off" and promo_info:
            return self._evaluate_percent_off(
                deal_record, product_id, canonical_name, base_price, promo_info,
                unit_type, category, cat_min_unit, cat_avg_unit, promo_type,
                promo_detail, qualifying_qty, raw_deal_id, ad_id, raw_title,
                image_url, past_obs,
            )

        if current_price is None:
            return self._evaluate_unpriced_deal(
                deal_record, product_id, canonical_name, unit_price, unit_type,
                category, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
                qualifying_qty, base_price, raw_deal_id, ad_id, raw_title,
                image_url, past_obs,
            )

        if not past_obs:
            return self._evaluate_first_seen_deal(
                deal_record, product_id, current_price, unit_price, unit_type,
                category, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
                qualifying_qty, base_price, raw_deal_id, ad_id, raw_title,
                image_url, promo_note, cat_note,
            )

        return self._evaluate_historical_deal(
            deal_record, product_id, canonical_name, current_price, unit_price,
            unit_type, category, cat_min_unit, cat_avg_unit, promo_type,
            promo_detail, qualifying_qty, base_price, raw_deal_id, ad_id,
            raw_title, image_url, promo_note, cat_note, past_obs,
            current_valid_from,
        )

    def _evaluate_points_redemption(
        self, deal_record, product_id, canonical_name, base_price, promo_info,
        point_value, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
        qualifying_qty, raw_deal_id, ad_id, raw_title, image_url, past_obs,
    ) -> DealEvaluation:
        pts = promo_info.points_cost or 0
        saved = promo_info.points_saved_val or base_price or deal_record.get("advertised_price")
        yield_val = (saved / pts) if (saved and pts > 0) else None
        yield_cents = (yield_val * 100) if yield_val else None
        unit_size = deal_record.get("unit_size")
        unit_type = deal_record.get("unit_type")
        category = deal_record.get("category")

        if pts <= 10 or (yield_val is not None and yield_val >= 0.10):
            badge = "POINTS_FREEBIE"
            cur_price = 0.0
            u_price = 0.0
            val_str = f" (Save ${saved:.2f} • {yield_cents:.1f}¢/pt)" if (saved and pts > 0) else ""
            summary_reason = f"🪙 FREE with {pts} CHOICE points{val_str}"
        elif yield_val is not None and yield_val >= (point_value * 1.3) and yield_val >= 0.03:
            badge = "POINTS_DEAL"
            cur_price = round(pts * 0.01, 2)
            u_price = round(cur_price / unit_size, 4) if (unit_size and unit_size > 0) else None
            summary_reason = f"🪙 High-Yield Points Deal: {pts} CHOICE points for ${saved:.2f} value ({yield_cents:.1f}¢/pt vs {point_value*100:.1f}¢ avg)"
        else:
            badge = "POINTS_REDEMPTION"
            cur_price = round(pts * 0.01, 2) if pts > 0 else (saved or 0.0)
            u_price = round(cur_price / unit_size, 4) if (unit_size and unit_size > 0) else None
            val_str = f" for ${saved:.2f} value ({yield_cents:.1f}¢/pt)" if (saved and pts > 0) else ""
            summary_reason = f"🪙 Points Redemption: {pts} CHOICE points{val_str}"

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=canonical_name,
            brand=deal_record.get("brand"),
            current_price=cur_price,
            unit_price=u_price,
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=cur_price,
            historical_avg=cur_price,
            historical_max=cur_price,
            past_observations_count=len(past_obs),
            diff_pct_vs_avg=0.0,
            badge=badge,
            summary_reason=summary_reason,
            unit_size=unit_size,
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=base_price,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def _evaluate_points_bonus(
        self, deal_record, product_id, canonical_name, current_price, promo_info,
        point_value, unit_price, unit_type, category, cat_min_unit, cat_avg_unit,
        promo_type, promo_detail, qualifying_qty, base_price, raw_deal_id, ad_id,
        raw_title, image_url, past_obs,
    ) -> DealEvaluation:
        pts = promo_info.points_bonus or 0
        spend = promo_info.spend_threshold
        rew = promo_info.est_reward_val or (pts * point_value)
        net_p = promo_info.est_net_price or (round(spend - rew, 2) if spend else None)
        if net_p is not None:
            current_price = net_p
        if promo_info.points_multiplier:
            mult = int(promo_info.points_multiplier)
            pct_back = round(mult * point_value * 100, 1)
            reason_pts = f"🪙 Earn {mult}X CHOICE Points (~{pct_back}% back in grocery rewards @ {point_value*100:.2f}¢/pt) [Est. with Points Reward]"
        elif spend and net_p:
            reason_pts = f"🪙 Est. Net ${net_p:.2f} after ~${rew:.2f} in CHOICE Points reward (${spend:.0f} spend, {pts} pts @ {point_value*100:.2f}¢/pt) [Est. with Points Reward]"
        else:
            reason_pts = f"🪙 {pts} CHOICE Points (~${rew:.2f} reward value @ {point_value*100:.2f}¢/pt) [Est. with Points Reward]"

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=canonical_name,
            brand=deal_record.get("brand"),
            current_price=current_price,
            unit_price=unit_price,
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=current_price,
            historical_avg=current_price,
            historical_max=current_price,
            past_observations_count=len(past_obs),
            diff_pct_vs_avg=0.0,
            badge="POINTS_REWARD",
            summary_reason=reason_pts,
            unit_size=deal_record.get("unit_size"),
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=base_price,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def _evaluate_spend_save(
        self, deal_record, product_id, canonical_name, unit_price, unit_type,
        category, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
        qualifying_qty, raw_deal_id, ad_id, raw_title, image_url, past_obs,
        promo_info,
    ) -> DealEvaluation:
        save_a = promo_info.coupon_discount or 0.0
        spend_a = promo_info.spend_threshold or 0.0
        pct = int((save_a / spend_a) * 100) if (save_a and spend_a) else 0

        adv_p = deal_record.get("advertised_price")
        if adv_p is not None and adv_p > 0:
            discount_pct = (save_a / spend_a) if (spend_a > 0 and save_a > 0) else 0.0
            effective_item_price = max(0.0, round(adv_p * (1.0 - discount_pct) + 1e-9, 2))
            u_size = deal_record.get("unit_size")
            item_unit_price = round(effective_item_price / u_size, 4) if (u_size and u_size > 0) else unit_price
            price_to_use = effective_item_price
        else:
            price_to_use = None
            item_unit_price = None

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=canonical_name,
            brand=deal_record.get("brand"),
            current_price=price_to_use,
            unit_price=item_unit_price,
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=price_to_use,
            historical_avg=price_to_use,
            historical_max=price_to_use,
            past_observations_count=len(past_obs),
            diff_pct_vs_avg=0.0,
            badge="SPEND_SAVE",
            summary_reason=f"🏷️ Save ${save_a:.2f} when you spend ${spend_a:.2f} ({pct}% off participating items)",
            unit_size=deal_record.get("unit_size"),
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=adv_p,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def _evaluate_percent_off(
        self, deal_record, product_id, canonical_name, base_price, promo_info,
        unit_type, category, cat_min_unit, cat_avg_unit, promo_type,
        promo_detail, qualifying_qty, raw_deal_id, ad_id, raw_title,
        image_url, past_obs,
    ) -> DealEvaluation:
        pct = promo_info.discount_pct or 0.0
        eff_p = round(base_price * (1.0 - pct / 100.0), 2) if (base_price and base_price > 0) else None
        unit_p = round(eff_p / deal_record.get("unit_size"), 4) if (eff_p and deal_record.get("unit_size")) else None
        reason = f"🏷️ {int(pct)}% Off regular ${base_price:.2f} -> Net ${eff_p:.2f}" if (base_price and eff_p) else f"🏷️ {int(pct)}% Off"

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=canonical_name,
            brand=deal_record.get("brand"),
            current_price=eff_p,
            unit_price=unit_p,
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=eff_p,
            historical_avg=eff_p,
            historical_max=eff_p,
            past_observations_count=len(past_obs),
            diff_pct_vs_avg=0.0,
            badge="PERCENT_OFF",
            summary_reason=reason,
            unit_size=deal_record.get("unit_size"),
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=base_price,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def _evaluate_unpriced_deal(
        self, deal_record, product_id, canonical_name, unit_price, unit_type,
        category, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
        qualifying_qty, base_price, raw_deal_id, ad_id, raw_title,
        image_url, past_obs,
    ) -> DealEvaluation:
        unpriced_reason = "Price not listed numerically in circular"
        if promo_detail:
            unpriced_reason = f"Promo: {promo_detail} (needs shelf price to compute unit cost)"
        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=canonical_name,
            brand=deal_record.get("brand"),
            current_price=None,
            unit_price=unit_price,
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=None,
            historical_avg=None,
            historical_max=None,
            past_observations_count=len(past_obs),
            diff_pct_vs_avg=None,
            badge="SEE_AD",
            summary_reason=unpriced_reason,
            unit_size=deal_record.get("unit_size"),
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=base_price,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def _evaluate_first_seen_deal(
        self, deal_record, product_id, current_price, unit_price, unit_type,
        category, cat_min_unit, cat_avg_unit, promo_type, promo_detail,
        qualifying_qty, base_price, raw_deal_id, ad_id, raw_title,
        image_url, promo_note, cat_note,
    ) -> DealEvaluation:
        first_badge = "FIRST_SEEN"
        first_reason = f"First time tracked in circular database{promo_note}{cat_note}"
        if cat_min_unit is not None and cat_avg_unit is not None and unit_price is not None:
            if unit_price <= (cat_min_unit + 0.005):
                first_badge = "NEW_ALL_TIME_LOW"
                first_reason = f"🌟 Best {category} price! ${unit_price:.2f}/{unit_type} (lowest across all brands){promo_note}"
            elif unit_price <= (cat_avg_unit * 0.85):
                first_badge = "BEAT_AVERAGE"
                diff_cat = abs(int(((unit_price - cat_avg_unit) / cat_avg_unit) * 100.0))
                first_reason = f"🔥 Great value! {diff_cat}% below {category} category avg of ${cat_avg_unit:.2f}/{unit_type}{promo_note}"
            elif unit_price <= (cat_avg_unit * 1.15):
                first_badge = "STANDARD_DEAL"
                first_reason = f"Standard deal within normal range for {category} (${unit_price:.2f}/{unit_type} vs ${cat_avg_unit:.2f} avg){promo_note}"
            else:
                first_badge = "FIRST_SEEN"
                diff_cat = int(((unit_price - cat_avg_unit) / cat_avg_unit) * 100.0)
                first_reason = f"First time tracked in circular database ({category} avg: ${cat_avg_unit:.2f}/{unit_type}, +{diff_cat}%){promo_note}"

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=deal_record.get("canonical_name", ""),
            brand=deal_record.get("brand"),
            current_price=current_price,
            unit_price=unit_price,
            page_number=deal_record.get("page_number", 1),
            is_front_page=bool(deal_record.get("is_front_page", 1)),
            historical_min=current_price,
            historical_avg=current_price,
            historical_max=current_price,
            past_observations_count=0,
            diff_pct_vs_avg=0.0,
            badge=first_badge,
            summary_reason=first_reason,
            unit_size=deal_record.get("unit_size"),
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=base_price,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def _evaluate_historical_deal(
        self, deal_record, product_id, canonical_name, current_price, unit_price,
        unit_type, category, cat_min_unit, cat_avg_unit, promo_type,
        promo_detail, qualifying_qty, base_price, raw_deal_id, ad_id,
        raw_title, image_url, promo_note, cat_note, past_obs,
        current_valid_from,
    ) -> DealEvaluation:
        episodes = self.cluster_episodes(past_obs)
        past_prices = [h["advertised_price"] for h in past_obs]
        h_min = min(past_prices)
        h_max = max(past_prices)

        baseline_episodes = [
            ep for ep in episodes if ep.promo_type not in ("doorbuster", "outlier")
        ]
        if not baseline_episodes:
            baseline_episodes = episodes

        b_min = min(ep.price for ep in baseline_episodes)
        b_max = max(ep.price for ep in baseline_episodes)

        # Time-decayed baseline average:
        # Weights recent promotional episodes more heavily than older ones to account for
        # inflation and macro price drift, with an exponential half-life of 90 days.
        # Untrusted backfill records receive an additional 0.5x discount to phase them out over time.
        curr_dt = self._parse_date(current_valid_from)
        if curr_dt == datetime.min:
            curr_dt = datetime.now()

        weights = []
        for ep in baseline_episodes:
            ep_dt = self._parse_date(ep.valid_to or ep.valid_from)
            days_ago = max(0, (curr_dt - ep_dt).days) if ep_dt != datetime.min else 0
            w = math.pow(0.5, days_ago / 90.0)
            if not getattr(ep, "is_trusted", True):
                w *= 0.5
            weights.append(w)

        total_weight = sum(weights)
        if total_weight > 0:
            b_avg = sum(ep.price * w for ep, w in zip(baseline_episodes, weights, strict=False)) / total_weight
        else:
            b_avg = sum(ep.price for ep in baseline_episodes) / len(baseline_episodes)

        diff_vs_avg = ((current_price - b_avg) / b_avg) * 100.0 if b_avg > 0 else 0.0

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
        reason = f"Past sale range: ${b_min:.2f} - ${b_max:.2f} (avg ${b_avg:.2f}){promo_note}{cat_note}"
        has_price_variation = (h_max - h_min) >= 0.05
        is_generic_placeholder = canonical_name.strip().lower() in GENERIC_PLACEHOLDER_NAMES

        if is_generic_placeholder:
            badge = "STANDARD_DEAL"
            reason = f"Unbranded/assorted circular promo (${current_price:.2f}){promo_note}{cat_note}"
        elif is_contiguous_continuation:
            if current_price <= h_min and has_price_variation:
                badge = "MATCHES_ATL"
                reason = f"🌟 Multi-week sale at All-Time Low (${h_min:.2f}){promo_note}{cat_note}"
            else:
                badge = "CYCLE_REFRESH"
                reason = f"🔄 Ongoing multi-week promotion (${current_price:.2f}){promo_note}{cat_note}"
        elif current_price < (h_min - 0.005):
            badge = "NEW_ALL_TIME_LOW"
            diff_min = ((current_price - h_min) / h_min) * 100.0
            reason = f"🌟 New All-Time Low! {abs(diff_min):.1f}% below past low of ${h_min:.2f}{promo_note}{cat_note}"
        elif abs(current_price - h_min) <= 0.005:
            if has_price_variation:
                badge = "MATCHES_ATL"
                reason = f"🌟 Matches All-Time Low (${h_min:.2f}){promo_note}{cat_note}"
            else:
                badge = "CYCLE_REFRESH"
                reason = f"🔄 Standard promo cycle (typical: ${h_min:.2f}){promo_note}{cat_note}"
        elif current_price <= (b_avg * 0.85):
            badge = "BEAT_AVERAGE"
            reason = f"🔥 {abs(diff_vs_avg):.1f}% below historical average of ${b_avg:.2f}{promo_note}{cat_note}"
        elif current_price <= b_avg or abs(current_price - b_min) < 0.05:
            badge = "CYCLE_REFRESH"
            if abs(b_min - b_max) < 0.01:
                reason = f"🔄 Standard promo cycle (typical: ${b_min:.2f}){promo_note}{cat_note}"
            else:
                reason = f"🔄 Standard promo cycle (typical: ${b_min:.2f} - ${b_avg:.2f}){promo_note}{cat_note}"
        elif current_price > (b_avg * 1.15) or current_price > b_max:
            badge = "PRICE_HIKE"
            reason = f"⚠️ Higher than typical promo average (+{diff_vs_avg:.1f}% vs avg ${b_avg:.2f}){promo_note}{cat_note}"

        return DealEvaluation(
            deal_id=deal_record.get("id", 0),
            product_id=product_id,
            canonical_name=deal_record.get("canonical_name", ""),
            brand=deal_record.get("brand"),
            current_price=current_price,
            unit_price=unit_price,
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
            unit_type=unit_type,
            category=category,
            category_min_unit_price=round(cat_min_unit, 4) if cat_min_unit is not None else None,
            category_avg_unit_price=round(cat_avg_unit, 4) if cat_avg_unit is not None else None,
            promo_type=promo_type,
            promo_detail=promo_detail,
            qualifying_qty=qualifying_qty,
            base_price=base_price,
            raw_deal_id=raw_deal_id,
            ad_id=ad_id,
            ad_title=deal_record.get("ad_title"),
            raw_title=raw_title,
            image_url=image_url,
        )

    def evaluate_flyer(
        self, flyer_id: int, front_page_only: bool = False
    ) -> List[DealEvaluation]:
        """Evaluate all deals in a circular against historical data."""
        deals = self.db.get_deals_for_flyer(flyer_id, front_page_only=front_page_only)

        # Precompute circular-wide average point valuation from points redemption deals (specifically ignoring 5-point freebies)
        from .promo_extractor import PromoExtractor
        avg_point_val = PromoExtractor.calculate_dynamic_point_value(deals, default_value=PromoExtractor.DEFAULT_POINT_VALUE)

        # Precompute current flyer category min unit prices
        flyer_cat_mins: Dict[Tuple[str, str], float] = {}
        for d in deals:
            c = d.get("category")
            ut = d.get("unit_type")
            up = d.get("unit_price")
            if c and ut and up is not None and up > 0:
                key = (c.lower(), ut.lower())
                if key not in flyer_cat_mins or up < flyer_cat_mins[key]:
                    flyer_cat_mins[key] = up

        # Batch load product histories for all items in the flyer in 1 query (~0.05s)
        prod_histories = self.db.get_flyer_product_histories(flyer_id)

        # Local memoized caches for ad_title and category benchmarks across the flyer run
        ad_title_cache: Dict[Any, List[Dict[str, Any]]] = {}
        cat_cache: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        evaluations = [
            self.evaluate_deal(
                d,
                current_flyer_id=flyer_id,
                flyer_cat_mins=flyer_cat_mins,
                point_value=avg_point_val,
                history_override=prod_histories.get(d["product_id"], []),
                ad_title_cache=ad_title_cache,
                cat_cache=cat_cache,
            )
            for d in deals
        ]

        # Prioritize 5-Point / Points Freebies, All-Time Lows, High-Yield Points Deals, Points Rewards, and Beat Average deals first
        priority_order = {
            "POINTS_FREEBIE": 0,
            "NEW_ALL_TIME_LOW": 1,
            "MATCHES_ATL": 1.1,
            "ALL_TIME_LOW": 1.2,
            "POINTS_DEAL": 2,
            "POINTS_REWARD": 3,
            "SPEND_SAVE": 4,
            "PERCENT_OFF": 5,
            "BEAT_AVERAGE": 6,
            "CYCLE_REFRESH": 7,
            "FIRST_SEEN": 8,
            "POINTS_REDEMPTION": 9,
            "STANDARD_DEAL": 10,
            "PRICE_HIKE": 11,
            "SEE_AD": 12,
        }
        evaluations.sort(key=lambda x: (priority_order.get(x.badge, 99), x.current_price or 999))
        return evaluations

