"""
Time-series pricing queries, commodity unit price baselines, and deal price updates.
"""

import sqlite3
from typing import Optional, List, Dict, Any, Tuple


class AnalyticsMixin:
    """Methods for historical price analytics and price updates."""

    def _get_connection(self) -> sqlite3.Connection:
        raise NotImplementedError

    def get_product_price_history(
        self, product_id: int, trusted_only: bool = False, merchant: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch time-series price history for a given product."""
        query = """
            SELECT 
                d.id as deal_id, d.advertised_price, d.unit_price, d.page_number, d.is_front_page,
                d.promo_type, d.promo_detail, d.qualifying_qty, d.base_price, d.coupon_discount,
                d.is_trusted, d.source_type, d.recorded_at, f.valid_from, f.valid_to, f.flyer_id, f.merchant, f.postal_code,
                p.unit_size, p.unit_type, p.category, p.last_shelf_price, p.upc
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE d.product_id = ?
        """
        params: List[Any] = [product_id]
        if trusted_only:
            query += " AND d.is_trusted = 1"
        if merchant:
            query += " AND f.merchant LIKE ?"
            params.append(f"%{merchant}%")
        query += " ORDER BY f.valid_from ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_flyer_product_histories(self, flyer_id: int) -> Dict[int, List[Dict[str, Any]]]:
        """Batch fetch historical deal observations for all products appearing in a circular flyer."""
        query = """
            SELECT 
                d.id as deal_id, d.advertised_price, d.unit_price, d.page_number, d.is_front_page,
                d.promo_type, d.promo_detail, d.qualifying_qty, d.base_price, d.coupon_discount,
                d.is_trusted, d.source_type, d.recorded_at, f.valid_from, f.valid_to, f.flyer_id, f.merchant, f.postal_code,
                p.unit_size, p.unit_type, p.category, p.last_shelf_price, p.upc, d.product_id
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE d.product_id IN (SELECT DISTINCT product_id FROM deal_observations WHERE flyer_id = ?)
            ORDER BY f.valid_from ASC
        """
        result: Dict[int, List[Dict[str, Any]]] = {}
        with self._get_connection() as conn:
            rows = conn.execute(query, (flyer_id,)).fetchall()
            for r in rows:
                pid = r["product_id"]
                if pid not in result:
                    result[pid] = []
                result[pid].append(dict(r))
        return result

    def get_commodity_unit_price_history(
        self, category: str, unit_type: Optional[str] = None, trusted_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch historical unit price observations across all brands for a commodity category."""
        query = """
            SELECT 
                d.id as deal_id, d.advertised_price,
                COALESCE(d.unit_price, CASE WHEN p.unit_size > 0 THEN ROUND(d.advertised_price / p.unit_size, 4) ELSE NULL END) as unit_price,
                d.page_number, d.is_front_page,
                d.promo_type, d.is_trusted, d.source_type, d.recorded_at, f.valid_from, f.valid_to, f.flyer_id,
                p.product_id, p.canonical_name, p.brand, p.category, p.unit_size, p.unit_type
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE (p.category = ? COLLATE NOCASE OR (p.category IS NULL AND (
                p.canonical_name LIKE ? 
                OR p.canonical_name LIKE ? 
                OR p.canonical_name LIKE ?
                OR p.canonical_name = ?
            )))
              AND (d.unit_price IS NOT NULL OR (d.advertised_price IS NOT NULL AND p.unit_size > 0))
              AND d.advertised_price IS NOT NULL
        """
        params: List[Any] = [category, f"% {category} %", f"% {category}", f"{category} %", category]
        if unit_type:
            query += " AND p.unit_type = ?"
            params.append(unit_type)
        if trusted_only:
            query += " AND d.is_trusted = 1"
        query += " ORDER BY unit_price ASC, f.valid_from DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def update_deal_price(
        self,
        deal_id: int,
        advertised_price: float,
        unit_price: Optional[float] = None,
        base_price: Optional[float] = None,
    ) -> bool:
        """Update calculated effective advertised price and unit price for an observation."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE deal_observations
                SET advertised_price = ?,
                    unit_price = COALESCE(?, unit_price),
                    base_price = COALESCE(?, base_price)
                WHERE id = ?
                """,
                (advertised_price, unit_price, base_price, deal_id),
            )
            return cur.rowcount > 0

    def get_ad_title_price_history(
        self,
        ad_title: str,
        target_flyer_id: Optional[int] = None,
        current_valid_from: Optional[str] = None,
        merchant: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch historical observations matching a parent circular ad title or canonical product name."""
        query = """
            SELECT 
                d.id as deal_id, d.advertised_price, d.unit_price, d.page_number, d.is_front_page,
                d.promo_type, d.promo_detail, d.qualifying_qty, d.base_price, d.coupon_discount,
                d.is_trusted, d.source_type, d.recorded_at, f.valid_from, f.valid_to, f.flyer_id, f.merchant, f.postal_code,
                p.unit_size, p.unit_type, p.category, p.last_shelf_price, p.upc
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE (d.ad_title = ? OR p.canonical_name = ?)
              AND d.advertised_price IS NOT NULL
        """
        params: List[Any] = [ad_title, ad_title]
        if target_flyer_id is not None:
            query += " AND d.flyer_id != ?"
            params.append(target_flyer_id)
        if current_valid_from:
            query += " AND substr(f.valid_from, 1, 10) < ?"
            params.append(current_valid_from)
        if merchant:
            query += " AND f.merchant LIKE ?"
            params.append(f"%{merchant}%")
        query += " ORDER BY f.valid_from ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _compute_history_group_key(r: Dict[str, Any]) -> Tuple[str, str]:
        """
        Compute a general canonical history grouping key and display title for an observation.
        Collapses minor ounce-range variations, pack-size representations (e.g. '6 ct' vs '6-2.4 oz'),
        and synonymous product representations into a single unified timeline.
        """
        import re
        raw_name = (r.get("canonical_name") or "").strip()
        brand = (r.get("brand") or "").strip()
        ad_title = (r.get("ad_title") or "").strip()
        unit_size = r.get("unit_size")
        unit_type = (r.get("unit_type") or "").lower()

        placeholder_names = {
            "assorted products",
            "assorted product",
            "assorted varieties",
            "select varieties",
            "selected varieties",
            "mix or match",
        }

        # Prefer ad_title if provided and not a placeholder, unless ad_title is just a generic fragment
        if ad_title and ad_title.lower() not in placeholder_names:
            name = ad_title
        elif raw_name.lower() in placeholder_names:
            name = (r.get("raw_title") or "").strip()
        else:
            name = raw_name

        # 1. Clean brand artifacts (e.g. "Clif Bar" -> "Clif")
        clean_brand = brand
        if clean_brand.lower() in ("clif bar", "clif bars"):
            clean_brand = "Clif"

        # 2. Extract Multi-Pack Count (ct / pk / pack)
        # Pattern A: e.g. "6 ct", "10 pk", "12 pack", "18 ct", but NOT decimals like "1.69" or "2.40"
        pack_count = None
        m_pack = re.search(r"(?<![\d\.])(\d+)\s*(?:ct|pk|pack|count|roll|rolls|can|cans|bottle|bottles)\b", name, re.I)
        if m_pack:
            pack_count = int(m_pack.group(1))
        else:
            # Pattern B: Supermarket N-count of M-oz format: "6-2.4 oz", "12-12 oz", "24-12 oz"
            m_multioz = re.search(r"(?<![\d\.])(\d+)\s*-\s*\d+(?:\.\d+)?\s*oz\b", name, re.I)
            if m_multioz:
                pack_count = int(m_multioz.group(1))
            elif unit_type in ("ct", "pk", "roll") and unit_size and unit_size > 1:
                pack_count = int(unit_size)

        # 3. Standardize base product line (strip minor ounce ranges & pack tokens)
        # Remove ounce range (e.g. "1.69-2.40 oz", "12-16 oz", "4-6 oz", "8.9-10.8 oz")
        base = re.sub(r"\b\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*(?:oz|ounce)\.?\b", "", name, flags=re.I)
        # Remove single ounce specs (e.g. "2.045 oz", "2.4 oz", "14.4 oz.", "16 oz.")
        # But preserve standard container nouns like "Pint", "Quart", "Half Gallon", "Gallon"
        base = re.sub(r"\b\d+(?:\.\d+)?\s*(?:oz|ounce)\.?\b", "", base, flags=re.I)
        # Remove pack tokens from base (e.g. "6 ct", "10 pk", "6-2.4 oz")
        base = re.sub(r"(?<![\d\.])\d+\s*(?:ct|pk|pack|count|roll|rolls)\.?\b", "", base, flags=re.I)
        base = re.sub(r"(?<![\d\.])\d+\s*-\s*\d+(?:\.\d+)?\s*oz\.?\b", "", base, flags=re.I)

        # Clean whitespace and trailing punctuation
        base = " ".join(base.split()).strip(" ,.-")

        # Head noun restoration if truncated
        if re.match(r"^clif\s+luna\b", base, re.I):
            base = re.sub(r"^clif\s+luna", "LUNA", base, flags=re.I).strip()
        if base.upper() == "CLIF":
            base = "CLIF Bars"
        elif base.upper() == "LUNA":
            base = "LUNA Bars"

        # 4. Formulate canonical pack tier
        tier_suffix = f"{pack_count} ct" if (pack_count and pack_count > 1) else ""

        display_title = f"{base} {tier_suffix}".strip() if tier_suffix else base
        group_key = f"{base.lower()}_{tier_suffix.lower()}".strip("_")
        return group_key, display_title

    def get_grouped_price_history(
        self,
        query: str,
        merchant: Optional[str] = None,
        trusted_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch historical price timeline aggregated by canonical ad/product groups."""
        query_sql = """
            SELECT 
                d.id as deal_id, d.advertised_price, d.unit_price, d.page_number, d.is_front_page,
                d.promo_type, d.promo_detail, d.qualifying_qty, d.base_price, d.coupon_discount,
                d.ad_title, d.is_trusted, d.source_type, d.recorded_at,
                p.product_id, p.canonical_name, p.brand, p.category, p.unit_size, p.unit_type,
                f.flyer_id, f.valid_from, f.valid_to, f.merchant, f.postal_code
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE (p.canonical_name LIKE ? OR p.brand LIKE ? OR p.category LIKE ? OR d.ad_title LIKE ?)
        """
        params: List[Any] = [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"]
        if merchant:
            query_sql += " AND f.merchant LIKE ?"
            params.append(f"%{merchant}%")
        if trusted_only:
            query_sql += " AND d.is_trusted = 1"

        query_sql += " ORDER BY f.valid_from ASC, d.advertised_price ASC"

        with self._get_connection() as conn:
            rows = [dict(r) for r in conn.execute(query_sql, params).fetchall()]

        # Generic placeholder names to avoid lumping into an "Assorted Varieties" group
        placeholder_names = {
            "assorted products",
            "assorted product",
            "assorted varieties",
            "select varieties",
            "selected varieties",
            "mix or match",
        }

        # Group observations by general canonical history key and title
        groups: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            key, group_title = self._compute_history_group_key(r)
            if key not in groups:
                groups[key] = {
                    "title": group_title,
                    "brands": set(),
                    "categories": set(),
                    "runs_map": {},
                }

            g = groups[key]
            if r.get("brand"):
                g["brands"].add(r["brand"])
            if r.get("category"):
                g["categories"].add(r["category"])

            run_key = (
                r["flyer_id"],
                (r.get("valid_from") or "")[:10],
                (r.get("valid_to") or "")[:10],
                r.get("merchant"),
            )
            if run_key not in g["runs_map"]:
                g["runs_map"][run_key] = []
            g["runs_map"][run_key].append(r)

        result: List[Dict[str, Any]] = []
        for key, g in sorted(groups.items(), key=lambda x: x[1]["title"].lower()):
            runs_list = []
            for run_key, obs_list in sorted(g["runs_map"].items(), key=lambda x: x[0][1]):
                fid, v_from, v_to, merch = run_key
                prices = [o["advertised_price"] for o in obs_list if o.get("advertised_price") is not None]
                unit_prices = [o["unit_price"] for o in obs_list if o.get("unit_price") is not None]
                unit_types = [o["unit_type"] for o in obs_list if o.get("unit_type")]
                promos = [o["promo_detail"] for o in obs_list if o.get("promo_detail")]
                pages = sorted(list(set(o.get("page_number") for o in obs_list if o.get("page_number"))))
                unique_varieties = sorted(list(set(o["canonical_name"] for o in obs_list)))

                runs_list.append({
                    "flyer_id": fid,
                    "valid_from": v_from,
                    "valid_to": v_to,
                    "merchant": merch,
                    "min_price": min(prices) if prices else None,
                    "max_price": max(prices) if prices else None,
                    "min_unit_price": min(unit_prices) if unit_prices else None,
                    "max_unit_price": max(unit_prices) if unit_prices else None,
                    "unit_type": unit_types[0] if unit_types else None,
                    "is_front_page": any(o.get("is_front_page") for o in obs_list),
                    "pages": pages,
                    "promo_detail": promos[0] if promos else None,
                    "is_trusted": all(o.get("is_trusted", 1) for o in obs_list),
                    "is_doorbuster": any(o.get("promo_type") in ("doorbuster", "outlier") for o in obs_list),
                    "varieties": unique_varieties,
                    "observations": obs_list,
                })

            result.append({
                "title": g["title"],
                "brands": sorted(list(g["brands"])),
                "categories": sorted(list(g["categories"])),
                "runs": runs_list,
            })

        return result

