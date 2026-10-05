"""
SQLite storage engine for weekly circulars, product entities, and deal price history.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from .fetcher import FlyerMetadata, FlyerItem
from .normalizer import NormalizedDeal


class DealsDatabase:
    """Manages persistence and queries for circular snapshots and historical pricing."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            top_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
            local_data_dir = Path(__file__).resolve().parent.parent / "data"
            if (top_data_dir / "deals.db").exists():
                self.db_path = str(top_data_dir / "deals.db")
            elif (local_data_dir / "deals.db").exists():
                self.db_path = str(local_data_dir / "deals.db")
            else:
                top_data_dir.mkdir(parents=True, exist_ok=True)
                self.db_path = str(top_data_dir / "deals.db")
        else:
            self.db_path = db_path
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.is_memory = (self.db_path == ":memory:")
        self._memory_conn = None
        if self.is_memory:
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.row_factory = sqlite3.Row
            self._memory_conn.execute("PRAGMA foreign_keys = ON")

        self.init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if self.is_memory and self._memory_conn:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        """Create tables and performance indexes if they don't already exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS flyer_runs (
                    flyer_id INTEGER PRIMARY KEY,
                    postal_code TEXT NOT NULL,
                    merchant TEXT NOT NULL DEFAULT 'Tom Thumb',
                    name TEXT NOT NULL,
                    valid_from TIMESTAMP NOT NULL,
                    valid_to TIMESTAMP NOT NULL,
                    is_trusted BOOLEAN DEFAULT 1,
                    source_type TEXT DEFAULT 'flipp_api',
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS products (
                    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_name TEXT NOT NULL UNIQUE,
                    brand TEXT,
                    category TEXT,
                    unit_size REAL,
                    unit_type TEXT,
                    last_shelf_price REAL,
                    upc TEXT
                );

                CREATE TABLE IF NOT EXISTS deal_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flyer_id INTEGER NOT NULL REFERENCES flyer_runs(flyer_id),
                    product_id INTEGER NOT NULL REFERENCES products(product_id),
                    raw_deal_id INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    is_front_page BOOLEAN DEFAULT 1,
                    advertised_price REAL,
                    unit_price REAL,
                    promo_type TEXT DEFAULT 'standard',
                    promo_detail TEXT,
                    qualifying_qty INTEGER DEFAULT 1,
                    base_price REAL,
                    coupon_discount REAL,
                    raw_title TEXT NOT NULL,
                    image_url TEXT,
                    is_trusted BOOLEAN DEFAULT 1,
                    source_type TEXT DEFAULT 'flipp_api',
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(flyer_id, product_id, raw_deal_id)
                );

                CREATE TABLE IF NOT EXISTS app_digital_coupons (
                    coupon_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coupon_key TEXT UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    coupon_type TEXT NOT NULL,
                    discount_amount REAL NOT NULL,
                    min_spend REAL DEFAULT 0.0,
                    category TEXT,
                    eligible_brand TEXT,
                    is_clipped BOOLEAN DEFAULT 0,
                    valid_to TIMESTAMP,
                    raw_node_text TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS matched_stacks (
                    stack_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    category TEXT,
                    retail_price REAL NOT NULL,
                    source_type TEXT NOT NULL,
                    store_coupon_discount REAL DEFAULT 0.0,
                    mfg_coupon_discount REAL DEFAULT 0.0,
                    final_out_of_pocket REAL NOT NULL,
                    is_free BOOLEAN GENERATED ALWAYS AS (final_out_of_pocket <= 0.00),
                    is_clipped BOOLEAN DEFAULT 0,
                    coupon_references TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_obs_product_rec 
                    ON deal_observations(product_id, recorded_at);
                CREATE INDEX IF NOT EXISTS idx_obs_flyer 
                    ON deal_observations(flyer_id);
                CREATE INDEX IF NOT EXISTS idx_coupon_type 
                    ON app_digital_coupons(coupon_type);
                CREATE INDEX IF NOT EXISTS idx_coupon_cat 
                    ON app_digital_coupons(category);
                CREATE INDEX IF NOT EXISTS idx_stacks_is_free 
                    ON matched_stacks(is_free);
                """
            )
            # Safe schema migrations for existing database files
            self._apply_migrations(conn)

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        """Add missing columns dynamically if upgrading an existing database."""
        # Check flyer_runs columns
        cur = conn.execute("PRAGMA table_info(flyer_runs)")
        flyer_cols = {row["name"] for row in cur.fetchall()}
        if "is_trusted" not in flyer_cols:
            conn.execute("ALTER TABLE flyer_runs ADD COLUMN is_trusted BOOLEAN DEFAULT 1")
        if "source_type" not in flyer_cols:
            conn.execute("ALTER TABLE flyer_runs ADD COLUMN source_type TEXT DEFAULT 'flipp_api'")

        # Check products columns
        cur = conn.execute("PRAGMA table_info(products)")
        prod_cols = {row["name"] for row in cur.fetchall()}
        if "last_shelf_price" not in prod_cols:
            conn.execute("ALTER TABLE products ADD COLUMN last_shelf_price REAL")
        if "upc" not in prod_cols:
            conn.execute("ALTER TABLE products ADD COLUMN upc TEXT")

        # Check deal_observations columns
        cur = conn.execute("PRAGMA table_info(deal_observations)")
        obs_cols = {row["name"] for row in cur.fetchall()}
        if "is_trusted" not in obs_cols:
            conn.execute("ALTER TABLE deal_observations ADD COLUMN is_trusted BOOLEAN DEFAULT 1")
        if "source_type" not in obs_cols:
            conn.execute("ALTER TABLE deal_observations ADD COLUMN source_type TEXT DEFAULT 'flipp_api'")
        if "promo_detail" not in obs_cols:
            conn.execute("ALTER TABLE deal_observations ADD COLUMN promo_detail TEXT")
        if "qualifying_qty" not in obs_cols:
            conn.execute("ALTER TABLE deal_observations ADD COLUMN qualifying_qty INTEGER DEFAULT 1")
        if "base_price" not in obs_cols:
            conn.execute("ALTER TABLE deal_observations ADD COLUMN base_price REAL")
        if "coupon_discount" not in obs_cols:
            conn.execute("ALTER TABLE deal_observations ADD COLUMN coupon_discount REAL")

    def upsert_flyer_run(
        self, metadata: FlyerMetadata, is_trusted: bool = True, source_type: str = "flipp_api"
    ) -> None:
        """Insert or replace a weekly ad circular batch."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO flyer_runs (flyer_id, postal_code, merchant, name, valid_from, valid_to, is_trusted, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(flyer_id) DO UPDATE SET
                    valid_from = excluded.valid_from,
                    valid_to = excluded.valid_to,
                    is_trusted = excluded.is_trusted,
                    source_type = excluded.source_type,
                    scraped_at = CURRENT_TIMESTAMP
                """,
                (
                    metadata.id,
                    metadata.postal_code,
                    metadata.merchant,
                    metadata.name,
                    metadata.valid_from,
                    metadata.valid_to,
                    1 if is_trusted else 0,
                    source_type,
                ),
            )

    def mark_flyer_trust(self, flyer_id: int, is_trusted: bool, source_type: Optional[str] = None) -> None:
        """Update the trust status for a specific flyer and all its deals."""
        with self._get_connection() as conn:
            params_flyer = [1 if is_trusted else 0]
            params_obs = [1 if is_trusted else 0]
            query_flyer = "UPDATE flyer_runs SET is_trusted = ?"
            query_obs = "UPDATE deal_observations SET is_trusted = ?"

            if source_type:
                query_flyer += ", source_type = ?"
                query_obs += ", source_type = ?"
                params_flyer.append(source_type)
                params_obs.append(source_type)

            query_flyer += " WHERE flyer_id = ?"
            query_obs += " WHERE flyer_id = ?"
            params_flyer.append(flyer_id)
            params_obs.append(flyer_id)

            conn.execute(query_flyer, params_flyer)
            conn.execute(query_obs, params_obs)

    def mark_all_past_deals_trust(self, is_trusted: bool, except_flyer_ids: Optional[List[int]] = None) -> int:
        """Mark past circulars/deals as untrusted or trusted."""
        except_ids = except_flyer_ids or []
        placeholders = ",".join("?" * len(except_ids)) if except_ids else ""
        where_clause = f" WHERE flyer_id NOT IN ({placeholders})" if except_ids else ""

        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE flyer_runs SET is_trusted = ?{where_clause}",
                [1 if is_trusted else 0] + except_ids,
            )
            cur = conn.execute(
                f"UPDATE deal_observations SET is_trusted = ?{where_clause}",
                [1 if is_trusted else 0] + except_ids,
            )
            return cur.rowcount

    def delete_flyer(self, flyer_id: int) -> Tuple[int, int]:
        """Delete a flyer run and all associated deal observations. Also cleans up orphaned products."""
        with self._get_connection() as conn:
            obs_cur = conn.execute("DELETE FROM deal_observations WHERE flyer_id = ?", (flyer_id,))
            deleted_obs = obs_cur.rowcount
            flyer_cur = conn.execute("DELETE FROM flyer_runs WHERE flyer_id = ?", (flyer_id,))
            deleted_flyers = flyer_cur.rowcount
            conn.execute("""
                DELETE FROM products
                WHERE product_id NOT IN (SELECT DISTINCT product_id FROM deal_observations)
            """)
            return deleted_flyers, deleted_obs

    def purge_overlapping_untrusted_flyers(
        self, merchant: str, valid_from: str, valid_to: str, keep_flyer_id: Optional[int] = None
    ) -> List[int]:
        """
        Find and delete any untrusted/backfill flyers for the same merchant whose dates overlap
        with the given date range, superseded by a live/trusted flyer.
        """
        v_from = (valid_from or "")[:10]
        v_to = (valid_to or "")[:10]
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT flyer_id, valid_from, valid_to, is_trusted, source_type
                FROM flyer_runs
                WHERE merchant LIKE ? AND is_trusted = 0
                """,
                (f"%{merchant}%",),
            ).fetchall()

            to_delete = []
            for r in rows:
                if keep_flyer_id and r["flyer_id"] == keep_flyer_id:
                    continue
                r_from = (r["valid_from"] or "")[:10]
                r_to = (r["valid_to"] or "")[:10]
                if not (r_to < v_from or r_from > v_to):
                    to_delete.append(r["flyer_id"])

            for fid in to_delete:
                conn.execute("DELETE FROM deal_observations WHERE flyer_id = ?", (fid,))
                conn.execute("DELETE FROM flyer_runs WHERE flyer_id = ?", (fid,))

            if to_delete:
                conn.execute("""
                    DELETE FROM products
                    WHERE product_id NOT IN (SELECT DISTINCT product_id FROM deal_observations)
                """)

            return to_delete

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

    def _upsert_deal_observation(
        self,
        conn: sqlite3.Connection,
        deal: NormalizedDeal,
        promo_type: Optional[str] = None,
        is_trusted: Optional[bool] = None,
        source_type: Optional[str] = None,
        recorded_at: Optional[str] = None,
    ) -> bool:
        """Helper to get/create product entity and upsert a single deal observation."""
        product_id = self.get_or_create_product(
            canonical_name=deal.canonical_name,
            brand=deal.brand,
            unit_size=deal.unit_size,
            unit_type=deal.unit_type,
            category=getattr(deal, "category", None),
            conn=conn,
        )
        cur = conn.execute(
            """
            INSERT OR REPLACE INTO deal_observations
            (flyer_id, product_id, raw_deal_id, page_number, is_front_page,
             advertised_price, unit_price, promo_type, promo_detail, qualifying_qty,
             base_price, coupon_discount, raw_title, image_url,
             is_trusted, source_type, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (
                deal.flyer_id,
                product_id,
                deal.raw_deal_id,
                deal.page_number,
                1 if deal.is_front_page else 0,
                deal.advertised_price,
                deal.unit_price,
                promo_type if promo_type is not None else getattr(deal, "promo_type", "standard"),
                getattr(deal, "promo_detail", None),
                getattr(deal, "qualifying_qty", 1),
                getattr(deal, "base_price", None),
                getattr(deal, "coupon_discount", None),
                deal.raw_title,
                deal.image_url,
                (1 if is_trusted else 0) if is_trusted is not None else (1 if getattr(deal, "is_trusted", True) else 0),
                source_type if source_type is not None else getattr(deal, "source_type", "flipp_api"),
                recorded_at,
            ),
        )
        return cur.rowcount > 0

    def record_deals(self, deals: List[NormalizedDeal], conn: Optional[sqlite3.Connection] = None) -> int:
        """Persist normalized deal observations in a single transaction."""
        def _execute(c: sqlite3.Connection) -> int:
            inserted_count = 0
            for deal in deals:
                if self._upsert_deal_observation(c, deal):
                    inserted_count += 1
            return inserted_count

        if conn is not None:
            return _execute(conn)
        with self._get_connection() as c:
            return _execute(c)

    def get_latest_flyer_id(self, merchant: Optional[str] = None) -> Optional[int]:
        """Return the flyer_id of the most recent circular recorded."""
        with self._get_connection() as conn:
            if merchant:
                row = conn.execute(
                    """
                    SELECT flyer_id FROM flyer_runs
                    WHERE merchant LIKE ?
                    ORDER BY valid_from DESC, scraped_at DESC
                    LIMIT 1
                    """,
                    (f"%{merchant}%",),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT flyer_id FROM flyer_runs
                    ORDER BY valid_from DESC, scraped_at DESC
                    LIMIT 1
                    """,
                ).fetchone()
            return row["flyer_id"] if row else None

    def get_deals_for_flyer(
        self, flyer_id: int, front_page_only: bool = False, trusted_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch all deals for a given circular run."""
        query = """
            SELECT 
                d.id, d.flyer_id, d.product_id, d.raw_deal_id, d.page_number, d.is_front_page,
                d.advertised_price, d.unit_price, d.promo_type, d.promo_detail, d.qualifying_qty,
                d.base_price, d.coupon_discount, d.raw_title, d.image_url, d.is_trusted, d.source_type, d.recorded_at,
                p.canonical_name, p.brand, p.category, p.unit_size, p.unit_type, p.last_shelf_price, p.upc,
                f.valid_from, f.valid_to, f.merchant, f.postal_code
            FROM deal_observations d
            JOIN products p ON d.product_id = p.product_id
            JOIN flyer_runs f ON d.flyer_id = f.flyer_id
            WHERE d.flyer_id = ?
        """
        params: List[Any] = [flyer_id]
        if front_page_only:
            query += " AND d.is_front_page = 1"
        if trusted_only:
            query += " AND d.is_trusted = 1"
        query += " ORDER BY d.page_number ASC, d.advertised_price ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

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

    def mark_deal_doorbuster(self, deal_id: int, is_doorbuster: bool = True) -> bool:
        """Mark a specific deal observation as a doorbuster / outlier promo."""
        promo = "doorbuster" if is_doorbuster else "standard"
        with self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE deal_observations SET promo_type = ? WHERE id = ?",
                (promo, deal_id),
            )
            return cur.rowcount > 0

    def mark_flyer_doorbuster(self, flyer_id: int, is_doorbuster: bool = True) -> int:
        """Mark all deals in a circular flyer as doorbusters."""
        promo = "doorbuster" if is_doorbuster else "standard"
        with self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE deal_observations SET promo_type = ? WHERE flyer_id = ?",
                (promo, flyer_id),
            )
            return cur.rowcount

    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """Search products by canonical name or brand."""
        with self._get_connection() as conn:
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

    def renormalize_all_deals(self, normalizer=None) -> Tuple[int, int, int]:
        """
        Disaggregate all compound deals across circular history, link to canonical product entities,
        and remove obsolete/orphaned compound records.
        Returns: (disaggregated_observations_count, new_observations_count, deleted_orphaned_products_count)
        """
        if normalizer is None:
            from .normalizer import ProductNormalizer
            normalizer = ProductNormalizer()

        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT d.id as obs_id, d.flyer_id, d.raw_deal_id, d.page_number, d.is_front_page,
                       d.advertised_price, d.unit_price, d.promo_type, d.raw_title, d.image_url, d.is_trusted, d.source_type,
                       d.recorded_at, p.product_id, p.canonical_name, p.brand, p.category
                FROM deal_observations d
                JOIN products p ON d.product_id = p.product_id
            """).fetchall()

            disaggregated_obs = 0
            new_obs_total = 0

            for r in rows:
                item = FlyerItem(
                    id=r["raw_deal_id"],
                    flyer_id=r["flyer_id"],
                    name=r["raw_title"],
                    price=r["advertised_price"],
                    original_price=None,
                    pre_price_text=None,
                    post_price_text=None,
                    description=None,
                    brand=r["brand"],
                    page_number=r["page_number"],
                    is_front_page=bool(r["is_front_page"]),
                    cutout_image_url=r["image_url"],
                    clean_image_url=None,
                )
                deals = normalizer.disaggregate_and_normalize(item)

                if len(deals) > 1 or (len(deals) == 1 and (deals[0].canonical_name != r["canonical_name"] or deals[0].unit_price != r["unit_price"] or deals[0].category != r["category"])):
                    disaggregated_obs += 1
                    new_obs_total += len(deals)

                    # Remove old compound observation
                    conn.execute("DELETE FROM deal_observations WHERE id = ?", (r["obs_id"],))

                    # Insert disaggregated single-item deals
                    for deal in deals:
                        self._upsert_deal_observation(
                            conn=conn,
                            deal=deal,
                            promo_type=r["promo_type"],
                            is_trusted=bool(r["is_trusted"]),
                            source_type=r["source_type"],
                            recorded_at=r["recorded_at"],
                        )

            # Delete orphaned compound products
            del_cur = conn.execute("""
                DELETE FROM products
                WHERE product_id NOT IN (SELECT DISTINCT product_id FROM deal_observations)
            """)
            deleted_orphans = del_cur.rowcount

            return disaggregated_obs, new_obs_total, deleted_orphans

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

