"""
Unit tests for DealAnalyzer.
"""

import unittest
from src.database import DealsDatabase
from src.analyzer import DealAnalyzer
from src.fetcher import FlyerMetadata
from src.normalizer import NormalizedDeal


class TestDealAnalyzer(unittest.TestCase):

    def setUp(self):
        self.db = DealsDatabase(":memory:")
        self.analyzer = DealAnalyzer(self.db)

        # Create two past weekly flyer runs
        flyer_1 = FlyerMetadata(
            id=101,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-08-01T00:00:00",
            valid_to="2026-08-07T23:59:59",
        )
        flyer_2 = FlyerMetadata(
            id=102,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-08-15T00:00:00",
            valid_to="2026-08-21T23:59:59",
        )
        self.db.upsert_flyer_run(flyer_1)
        self.db.upsert_flyer_run(flyer_2)

        # Seed past pricing observations for "Bacon" ($3.49 and $3.99, avg $3.74)
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=1,
                    flyer_id=101,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Sugardale Bacon 12 oz.",
                    brand="Sugardale",
                    advertised_price=3.99,
                    unit_size=12.0,
                    unit_type="oz",
                    unit_price=0.33,
                    raw_title="Sugardale Bacon",
                    image_url=None,
                ),
                NormalizedDeal(
                    raw_deal_id=2,
                    flyer_id=102,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Sugardale Bacon 12 oz.",
                    brand="Sugardale",
                    advertised_price=3.49,
                    unit_size=12.0,
                    unit_type="oz",
                    unit_price=0.29,
                    raw_title="Sugardale Bacon",
                    image_url=None,
                ),
            ]
        )

    def test_all_time_low_evaluation(self):
        # In current flyer 103, Bacon is $2.99 (lower than past $3.49 min)
        flyer_3 = FlyerMetadata(
            id=103,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-01T00:00:00",
            valid_to="2026-09-07T23:59:59",
        )
        self.db.upsert_flyer_run(flyer_3)
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=3,
                    flyer_id=103,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Sugardale Bacon 12 oz.",
                    brand="Sugardale",
                    advertised_price=2.99,
                    unit_size=12.0,
                    unit_type="oz",
                    unit_price=0.25,
                    raw_title="Sugardale Bacon",
                    image_url=None,
                )
            ]
        )

        evaluations = self.analyzer.evaluate_flyer(103)
        self.assertEqual(len(evaluations), 1)
        ev = evaluations[0]
        self.assertEqual(ev.badge, "ALL_TIME_LOW")
        self.assertEqual(ev.current_price, 2.99)
        self.assertEqual(ev.historical_min, 3.49)
        self.assertIn("New All-Time Low", ev.summary_reason)

    def test_first_seen_evaluation(self):
        flyer_3 = FlyerMetadata(
            id=103,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-01T00:00:00",
            valid_to="2026-09-07T23:59:59",
        )
        self.db.upsert_flyer_run(flyer_3)
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=4,
                    flyer_id=103,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="New Organic Dragonfruit",
                    brand=None,
                    advertised_price=4.99,
                    unit_size=None,
                    unit_type=None,
                    unit_price=None,
                    raw_title="New Organic Dragonfruit",
                    image_url=None,
                )
            ]
        )

        evaluations = self.analyzer.evaluate_flyer(103)
        dragonfruit = next(e for e in evaluations if "Dragonfruit" in e.canonical_name)
        self.assertEqual(dragonfruit.badge, "FIRST_SEEN")
        self.assertEqual(dragonfruit.past_observations_count, 0)

    def test_price_hike_and_doorbuster_baseline(self):
        # In past, Bacon was $3.49 and $3.99 (avg $3.74).
        # If in current flyer 104, Bacon is $4.99 (> 3.74 * 1.15), it should be a PRICE_HIKE.
        flyer_4 = FlyerMetadata(
            id=104,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-08T00:00:00",
            valid_to="2026-09-14T23:59:59",
        )
        self.db.upsert_flyer_run(flyer_4)
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=5,
                    flyer_id=104,
                    page_number=1,
                    is_front_page=True,
                    canonical_name="Sugardale Bacon 12 oz.",
                    brand="Sugardale",
                    advertised_price=4.99,
                    unit_size=12.0,
                    unit_type="oz",
                    unit_price=0.41,
                    raw_title="Sugardale Bacon",
                    image_url=None,
                )
            ]
        )

        evaluations = self.analyzer.evaluate_flyer(104)
        bacon = next(e for e in evaluations if "Bacon" in e.canonical_name)
        self.assertEqual(bacon.badge, "PRICE_HIKE")
        self.assertIn("Higher than typical promo average", bacon.summary_reason)

    def test_concurrent_same_week_deal_ignored_in_history(self):
        # Suppose a concurrent flyer exists for the same week (e.g. scanned flyer 105 and live flyer 106)
        flyer_scanned = FlyerMetadata(
            id=105,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Scanned Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00",
            valid_to="2026-09-22T23:59:59",
        )
        flyer_live = FlyerMetadata(
            id=106,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Live Weekly Ad",
            postal_code="00000",
            valid_from="2026-09-16T00:00:00-04:00",
            valid_to="2026-09-22T23:59:59-04:00",
        )
        self.db.upsert_flyer_run(flyer_scanned, is_trusted=False)
        self.db.upsert_flyer_run(flyer_live, is_trusted=True)

        # Record Roma Tomatoes in scanned flyer
        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=1,
                    flyer_id=105,
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
                ),
                # Record Roma Tomatoes in live flyer
                NormalizedDeal(
                    raw_deal_id=2,
                    flyer_id=106,
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
                ),
            ]
        )

        evaluations = self.analyzer.evaluate_flyer(106)
        roma = next(e for e in evaluations if e.canonical_name == "Roma Tomatoes")
        # Should be FIRST_SEEN because the concurrent flyer 105 is from the same week, not past history
        self.assertEqual(roma.badge, "FIRST_SEEN")
        self.assertEqual(roma.past_observations_count, 0)


if __name__ == "__main__":
    unittest.main()
