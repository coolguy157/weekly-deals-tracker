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


if __name__ == "__main__":
    unittest.main()
