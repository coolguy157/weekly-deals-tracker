"""
Main DealsDatabase engine coordinating connection management, schema initialization, and DAOs.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from .schema import SCHEMA_SQL, apply_migrations
from .flyers import FlyersMixin
from .products import ProductsMixin
from .coupons import CouponsMixin
from .analytics import AnalyticsMixin


class DealsDatabase(FlyersMixin, ProductsMixin, CouponsMixin, AnalyticsMixin):
    """Manages persistence and queries for circular snapshots and historical pricing."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            top_data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
            local_data_dir = Path(__file__).resolve().parent.parent.parent / "data"
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
            conn.executescript(SCHEMA_SQL)
            self._apply_migrations(conn)

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        """Add missing columns dynamically if upgrading an existing database."""
        apply_migrations(conn)
