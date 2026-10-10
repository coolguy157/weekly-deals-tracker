"""
Product entity management, shelf price tracking, and product search queries.
"""

import sqlite3
from typing import Optional, List, Dict, Any


class ProductsMixin:
    """Methods for managing canonical products and regular shelf prices."""

    def _get_connection(self) -> sqlite3.Connection:
        raise NotImplementedError

    def get_or_create_product(
        self,
        canonical_name: str,
        brand: Optional[str] = None,
        unit_size: Optional[float] = None,
        unit_type: Optional[str] = None,
        category: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Fetch existing product_id or insert new canonical product record."""
        def _execute(c: sqlite3.Connection) -> int:
            cur = c.execute(
                "SELECT product_id FROM products WHERE canonical_name = ?",
                (canonical_name,),
            )
            row = cur.fetchone()
            if row:
                if unit_size is not None or unit_type is not None or brand is not None or category is not None:
                    c.execute(
                        """
                        UPDATE products
                        SET brand = COALESCE(?, brand),
                            unit_size = COALESCE(?, unit_size),
                            unit_type = COALESCE(?, unit_type),
                            category = COALESCE(?, category)
                        WHERE product_id = ?
                        """,
                        (brand, unit_size, unit_type, category, row["product_id"]),
                    )
                return row["product_id"]

            cur = c.execute(
                """
                INSERT INTO products (canonical_name, brand, unit_size, unit_type, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (canonical_name, brand, unit_size, unit_type, category),
            )
            return cur.lastrowid

        if conn is not None:
            return _execute(conn)
        with self._get_connection() as c:
            return _execute(c)

    def get_product_shelf_price(self, product_id: int) -> Optional[float]:
        """Fetch the cached regular shelf price for a product."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT last_shelf_price FROM products WHERE product_id = ?", (product_id,)).fetchone()
            return row["last_shelf_price"] if row else None

    def update_product_shelf_price(self, product_id: int, price: float) -> bool:
        """Update the cached regular shelf price for a product."""
        with self._get_connection() as conn:
            cur = conn.execute("UPDATE products SET last_shelf_price = ? WHERE product_id = ?", (price, product_id))
            return cur.rowcount > 0

    def search_products(self, query: str, merchant: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search products by canonical name or brand, optionally filtered by merchant."""
        with self._get_connection() as conn:
            if merchant:
                rows = conn.execute(
                    """
                    SELECT DISTINCT p.product_id, p.canonical_name, p.brand, p.unit_size, p.unit_type
                    FROM products p
                    JOIN deal_observations d ON p.product_id = d.product_id
                    JOIN flyer_runs f ON d.flyer_id = f.flyer_id
                    WHERE (p.canonical_name LIKE ? OR p.brand LIKE ?)
                      AND f.merchant LIKE ?
                    ORDER BY p.canonical_name ASC
                    LIMIT 50
                    """,
                    (f"%{query}%", f"%{query}%", f"%{merchant}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT product_id, canonical_name, brand, unit_size, unit_type
                    FROM products
                    WHERE canonical_name LIKE ? OR brand LIKE ?
                    ORDER BY canonical_name ASC
                    LIMIT 50
                    """,
                    (f"%{query}%", f"%{query}%"),
                ).fetchall()
            return [dict(r) for r in rows]
