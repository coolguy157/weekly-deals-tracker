"""
Digital coupon storage, coupon clipping status, and matched stacks persistence.
"""

import sqlite3
from typing import Optional, List, Dict, Any


class CouponsMixin:
    """Methods for managing mobile app digital coupons and calculated penny/free stacks."""

    def _get_connection(self) -> sqlite3.Connection:
        raise NotImplementedError

    def upsert_digital_coupon(self, coupon_data: Dict[str, Any]) -> int:
        """Insert or update a scraped mobile app digital coupon."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO app_digital_coupons (
                    coupon_key, title, description, coupon_type,
                    discount_amount, min_spend, category, eligible_brand,
                    is_clipped, valid_to, raw_node_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(coupon_key) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    coupon_type = excluded.coupon_type,
                    discount_amount = excluded.discount_amount,
                    min_spend = excluded.min_spend,
                    category = excluded.category,
                    eligible_brand = excluded.eligible_brand,
                    is_clipped = excluded.is_clipped,
                    valid_to = excluded.valid_to,
                    raw_node_text = excluded.raw_node_text,
                    scraped_at = CURRENT_TIMESTAMP
                """,
                (
                    coupon_data.get("coupon_key"),
                    coupon_data.get("title", ""),
                    coupon_data.get("description"),
                    coupon_data.get("coupon_type", "STORE_COUPON"),
                    coupon_data.get("discount_amount", 0.0),
                    coupon_data.get("min_spend", 0.0),
                    coupon_data.get("category"),
                    coupon_data.get("eligible_brand"),
                    1 if coupon_data.get("is_clipped") else 0,
                    coupon_data.get("valid_to"),
                    coupon_data.get("raw_node_text"),
                ),
            )
            return cur.lastrowid

    def get_digital_coupons(
        self,
        coupon_type: Optional[str] = None,
        unclipped_only: bool = False,
        min_discount: Optional[float] = None,
    ) -> List[sqlite3.Row]:
        """Fetch digital coupons with optional filters."""
        query = "SELECT * FROM app_digital_coupons WHERE 1=1"
        params: List[Any] = []

        if coupon_type:
            query += " AND coupon_type = ?"
            params.append(coupon_type)
        if unclipped_only:
            query += " AND is_clipped = 0"
        if min_discount is not None:
            query += " AND discount_amount >= ?"
            params.append(min_discount)

        query += " ORDER BY discount_amount DESC"

        with self._get_connection() as conn:
            return conn.execute(query, params).fetchall()

    def mark_coupon_clipped(self, coupon_key: str) -> None:
        """Mark a coupon as clipped by coupon_key."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE app_digital_coupons SET is_clipped = 1 WHERE coupon_key = ?",
                (coupon_key,),
            )

    def upsert_matched_stack(self, stack_data: Dict[str, Any]) -> int:
        """Record a calculated stack or free item."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO matched_stacks (
                    product_name, category, retail_price, source_type,
                    store_coupon_discount, mfg_coupon_discount,
                    final_out_of_pocket, is_clipped, coupon_references
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stack_data.get("product_name", ""),
                    stack_data.get("category"),
                    stack_data.get("retail_price", 0.0),
                    stack_data.get("source_type", "FLYER_SALE"),
                    stack_data.get("store_coupon_discount", 0.0),
                    stack_data.get("mfg_coupon_discount", 0.0),
                    stack_data.get("final_out_of_pocket", 0.0),
                    1 if stack_data.get("is_clipped") else 0,
                    stack_data.get("coupon_references", "[]"),
                ),
            )
            return cur.lastrowid

    def get_free_deals(self, max_price: float = 0.00) -> List[sqlite3.Row]:
        """Retrieve all calculated free items or penny deals (<= max_price)."""
        with self._get_connection() as conn:
            return conn.execute(
                """
                SELECT * FROM matched_stacks
                WHERE final_out_of_pocket <= ?
                ORDER BY final_out_of_pocket ASC, retail_price DESC
                """,
                (max_price,),
            ).fetchall()

    def get_all_matched_stacks(self) -> List[sqlite3.Row]:
        """Retrieve all matched stacks."""
        with self._get_connection() as conn:
            return conn.execute(
                "SELECT * FROM matched_stacks ORDER BY final_out_of_pocket ASC"
            ).fetchall()

    def clear_matched_stacks(self) -> None:
        """Clear previous stack calculations."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM matched_stacks")
