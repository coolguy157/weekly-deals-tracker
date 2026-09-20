"""
Unit tests for DealsDatabase.
"""

import unittest
from src.database import DealsDatabase
from src.fetcher import FlyerMetadata
from src.normalizer import NormalizedDeal


class TestDealsDatabase(unittest.TestCase):

    def setUp(self):
        # Use in-memory SQLite database for test isolation
        self.db = DealsDatabase(":memory:")

    def test_upsert_and_retrieve_flyer(self):
        flyer = FlyerMetadata(
            id=9001,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        self.db.upsert_flyer_run(flyer)

        latest_id = self.db.get_latest_flyer_id("Tom Thumb")
        self.assertEqual(latest_id, 9001)

    def test_record_deals_and_history(self):
        # Record flyer
        flyer = FlyerMetadata(
            id=9001,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        self.db.upsert_flyer_run(flyer)

        deal = NormalizedDeal(
            raw_deal_id=501,
            flyer_id=9001,
            page_number=1,
            is_front_page=True,
            canonical_name="Lucerne Large Eggs 12 ct",
            brand="Lucerne",
            advertised_price=0.97,
            unit_size=12.0,
            unit_type="ct",
            unit_price=0.0808,
            raw_title="Lucerne Large Eggs 12 ct",
            image_url="http://img.com/eggs.jpg",
        )

        inserted = self.db.record_deals([deal])
        self.assertEqual(inserted, 1)

        deals = self.db.get_deals_for_flyer(9001, front_page_only=True)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["canonical_name"], "Lucerne Large Eggs 12 ct")
        self.assertEqual(deals[0]["advertised_price"], 0.97)

        # Query history
        history = self.db.get_product_price_history(deals[0]["product_id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["advertised_price"], 0.97)

    def test_search_products(self):
        flyer = FlyerMetadata(
            id=9001,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        self.db.upsert_flyer_run(flyer)

        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=1,
                    flyer_id=9001,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Sugardale Bacon 12 oz.",
                    brand="Sugardale",
                    advertised_price=2.99,
                    unit_size=12.0,
                    unit_type="oz",
                    unit_price=0.249,
                    raw_title="Sugardale Bacon",
                    image_url=None,
                )
            ]
        )

        results = self.db.search_products("Bacon")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["canonical_name"], "Sugardale Bacon 12 oz.")

    def test_renormalize_all_deals(self):
        flyer = FlyerMetadata(
            id=9002,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        self.db.upsert_flyer_run(flyer)

        # Seed a compound deal that wasn't disaggregated
        compound_deal = NormalizedDeal(
            raw_deal_id=888,
            flyer_id=9002,
            page_number=1,
            is_front_page=True,
            canonical_name="Hormel Fully Cooked Bacon 2.52 oz or Eckrich Sausage 13-14 oz",
            brand="Hormel",
            advertised_price=3.99,
            unit_size=None,
            unit_type=None,
            unit_price=None,
            raw_title="Hormel Fully Cooked Bacon 2.52 oz or Eckrich Sausage 13-14 oz",
            image_url=None,
        )
        self.db.record_deals([compound_deal])

        # Verify initial state has 1 compound product
        prods_before = self.db.search_products("Hormel")
        self.assertEqual(len(prods_before), 1)

        # Run renormalize
        disaggregated_obs, new_obs, deleted_orphans = self.db.renormalize_all_deals()
        self.assertEqual(disaggregated_obs, 1)
        self.assertEqual(new_obs, 2)
        self.assertEqual(deleted_orphans, 1)

        # Verify separate clean products exist now
        bacon_res = self.db.search_products("Bacon")
        sausage_res = self.db.search_products("Sausage")
        self.assertEqual(len(bacon_res), 1)
        self.assertEqual(len(sausage_res), 1)
        self.assertEqual(bacon_res[0]["canonical_name"], "Hormel Fully Cooked Bacon 2.52 oz")
        self.assertEqual(sausage_res[0]["canonical_name"], "Eckrich Sausage 13-14 oz")

    def test_delete_flyer(self):
        flyer = FlyerMetadata(
            id=9003,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        self.db.upsert_flyer_run(flyer)
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=999,
                    flyer_id=9003,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Temporary Product",
                    brand=None,
                    advertised_price=1.99,
                    unit_size=None,
                    unit_type=None,
                    unit_price=None,
                    raw_title="Temporary Product",
                    image_url=None,
                )
            ]
        )
        self.assertEqual(len(self.db.get_deals_for_flyer(9003)), 1)
        deleted_flyers, deleted_obs = self.db.delete_flyer(9003)
        self.assertEqual(deleted_flyers, 1)
        self.assertEqual(deleted_obs, 1)
        self.assertEqual(len(self.db.get_deals_for_flyer(9003)), 0)
        # Orphaned product should also be cleaned up
        self.assertEqual(len(self.db.search_products("Temporary Product")), 0)

    def test_purge_overlapping_untrusted_flyers(self):
        # Insert untrusted/scanned flyer
        untrusted_flyer = FlyerMetadata(
            id=20260916,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Scanned PDF Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        self.db.upsert_flyer_run(untrusted_flyer, is_trusted=False, source_type="manual_backfill_untrusted")
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=10,
                    flyer_id=20260916,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Roma Tomatoes",
                    brand=None,
                    advertised_price=0.69,
                    unit_size=None,
                    unit_type=None,
                    unit_price=None,
                    raw_title="Roma Tomatoes",
                    image_url=None,
                )
            ]
        )

        # Ingest new live flyer for same dates
        live_flyer = FlyerMetadata(
            id=8131286,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00-04:00",
            valid_to="2026-09-22T23:59:59-04:00",
        )
        self.db.upsert_flyer_run(live_flyer, is_trusted=True, source_type="flipp_api")

        purged = self.db.purge_overlapping_untrusted_flyers(
            merchant=live_flyer.merchant,
            valid_from=live_flyer.valid_from,
            valid_to=live_flyer.valid_to,
            keep_flyer_id=live_flyer.id,
        )
        self.assertEqual(purged, [20260916])
        self.assertEqual(len(self.db.get_deals_for_flyer(20260916)), 0)


if __name__ == "__main__":
    unittest.main()
