"""
Flyer runs, deal observation storage, trust flags, and re-normalization workflows.
"""

import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from ..fetcher import FlyerMetadata, FlyerItem
from ..normalizer import NormalizedDeal


class FlyersMixin:
    """Methods for managing flyer runs, raw deal observations, and trust lifecycle."""

    def _get_connection(self) -> sqlite3.Connection:
        raise NotImplementedError

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

    def renormalize_all_deals(self, normalizer=None) -> Tuple[int, int, int]:
        """
        Disaggregate all compound deals across circular history, link to canonical product entities,
        and remove obsolete/orphaned compound records.
        Returns: (disaggregated_observations_count, new_observations_count, deleted_orphaned_products_count)
        """
        if normalizer is None:
            from ..normalizer import ProductNormalizer
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
