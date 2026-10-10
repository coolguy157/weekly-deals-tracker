"""
Schema definitions, table creations, performance indexes, and database migrations.
"""

import sqlite3


SCHEMA_SQL = """
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


def apply_migrations(conn: sqlite3.Connection) -> None:
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
