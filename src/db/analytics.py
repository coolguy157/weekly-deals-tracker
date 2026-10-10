"""
Time-series pricing queries, commodity unit price baselines, and deal price updates.
"""

import sqlite3
from typing import Optional, List, Dict, Any


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

    def get_commodity_unit_price_history(
        self, category: str, unit_type: Optional[str] = None, trusted_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch historical unit price observations across all brands for a commodity category."""
        query = """
            SELECT 
                d.id as deal_id, d.advertised_price, d.unit_price, d.page_number, d.is_front_page,
                d.promo_type, d.is_trusted, d.source_type, d.recorded_at, f.valid_from, f.valid_to, f.flyer_id,
                p.product_id, p.canonical_name, p.brand, p.category, p.unit_size, p.unit_type
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE (p.category LIKE ? OR p.canonical_name LIKE ?)
              AND d.unit_price IS NOT NULL
              AND d.advertised_price IS NOT NULL
        """
        params: List[Any] = [f"%{category}%", f"%{category}%"]
        if unit_type:
            query += " AND p.unit_type = ?"
            params.append(unit_type)
        if trusted_only:
            query += " AND d.is_trusted = 1"
        query += " ORDER BY d.unit_price ASC, f.valid_from DESC"

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
