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

    def test_flat_price_history_classifies_as_cycle_refresh(self):
        # When an item was seen only at $3.99 previously, a recurring $3.99 deal should be CYCLE_REFRESH
        flyer_past1 = FlyerMetadata(
            id=201,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad 1",
            postal_code="00000",
            valid_from="2026-07-01T00:00:00",
            valid_to="2026-07-07T23:59:59",
        )
        flyer_past2 = FlyerMetadata(
            id=202,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad 2",
            postal_code="00000",
            valid_from="2026-08-01T00:00:00",
            valid_to="2026-08-07T23:59:59",
        )
        flyer_curr = FlyerMetadata(
            id=203,
            merchant="Tom Thumb",
            merchant_id=2381,
            name="Weekly Ad 3",
            postal_code="00000",
            valid_from="2026-09-01T00:00:00",
            valid_to="2026-09-07T23:59:59",
        )
        self.db.upsert_flyer_run(flyer_past1)
        self.db.upsert_flyer_run(flyer_past2)
        self.db.upsert_flyer_run(flyer_curr)

        self.db.record_deals(
            [
                NormalizedDeal(
                    raw_deal_id=10,
                    flyer_id=201,
                    page_number=5,
                    is_front_page=False,
                    canonical_name="Fresh Chicken Wings",
                    brand="Signature SELECT",
                    advertised_price=3.99,
                    unit_size=None,
                    unit_type=None,
                    unit_price=None,
                    raw_title="Fresh Chicken Wings",
                    image_url=None,
                ),
                NormalizedDeal(
                    raw_deal_id=11,
                    flyer_id=202,
                    page_number=5,
                    is_front_page=False,
                    canonical_name="Fresh Chicken Wings",
                    brand="Signature SELECT",
                    advertised_price=3.99,
                    unit_size=None,
                    unit_type=None,
                    unit_price=None,
                    raw_title="Fresh Chicken Wings",
                    image_url=None,
                ),
                NormalizedDeal(
                    raw_deal_id=12,
                    flyer_id=203,
                    page_number=5,
                    is_front_page=False,
                    canonical_name="Fresh Chicken Wings",
                    brand="Signature SELECT",
                    advertised_price=3.99,
                    unit_size=None,
                    unit_type=None,
                    unit_price=None,
                    raw_title="Fresh Chicken Wings",
                    image_url=None,
                ),
            ]
        )

        evals = self.analyzer.evaluate_flyer(203)
        wings = next(e for e in evals if e.canonical_name == "Fresh Chicken Wings")
        self.assertEqual(wings.badge, "CYCLE_REFRESH")
        self.assertIn("Standard promo cycle", wings.summary_reason)

    def test_multi_week_episode_clustering_and_return_to_regular_price(self):
        # Seed 3 consecutive weeks of yogurt at $0.37, then 1 month later at $0.69 (baseline $0.69)
        # Week 1: 2026-06-03 to 2026-06-09 ($0.37)
        # Week 2: 2026-06-10 to 2026-06-16 ($0.37)
        # Week 3: 2026-06-17 to 2026-06-23 ($0.37)
        # Week 8: 2026-07-29 to 2026-08-04 ($0.69)
        f1 = FlyerMetadata(id=301, merchant="Tom Thumb", merchant_id=2381, name="Ad 1", postal_code="00000", valid_from="2026-06-03T00:00:00", valid_to="2026-06-09T23:59:59")
        f2 = FlyerMetadata(id=302, merchant="Tom Thumb", merchant_id=2381, name="Ad 2", postal_code="00000", valid_from="2026-06-10T00:00:00", valid_to="2026-06-16T23:59:59")
        f3 = FlyerMetadata(id=303, merchant="Tom Thumb", merchant_id=2381, name="Ad 3", postal_code="00000", valid_from="2026-06-17T00:00:00", valid_to="2026-06-23T23:59:59")
        f4 = FlyerMetadata(id=304, merchant="Tom Thumb", merchant_id=2381, name="Ad 4", postal_code="00000", valid_from="2026-07-29T00:00:00", valid_to="2026-08-04T23:59:59")
        for f in (f1, f2, f3, f4):
            self.db.upsert_flyer_run(f)

        self.db.record_deals([
            NormalizedDeal(raw_deal_id=31, flyer_id=301, page_number=1, is_front_page=True, canonical_name="Yoplait Yogurt 6 oz", brand="Yoplait", advertised_price=0.37, unit_size=6.0, unit_type="oz", unit_price=0.0617, raw_title="Yoplait Yogurt", image_url=None),
            NormalizedDeal(raw_deal_id=32, flyer_id=302, page_number=1, is_front_page=True, canonical_name="Yoplait Yogurt 6 oz", brand="Yoplait", advertised_price=0.37, unit_size=6.0, unit_type="oz", unit_price=0.0617, raw_title="Yoplait Yogurt", image_url=None),
            NormalizedDeal(raw_deal_id=33, flyer_id=303, page_number=1, is_front_page=True, canonical_name="Yoplait Yogurt 6 oz", brand="Yoplait", advertised_price=0.37, unit_size=6.0, unit_type="oz", unit_price=0.0617, raw_title="Yoplait Yogurt", image_url=None),
        ])

        # Evaluate Week 3 (continuation of multi-week promo)
        evals_w3 = self.analyzer.evaluate_flyer(303)
        yogurt_w3 = next(e for e in evals_w3 if "Yoplait" in e.canonical_name)
        self.assertEqual(yogurt_w3.badge, "CYCLE_REFRESH")
        self.assertIn("Ongoing multi-week promotion", yogurt_w3.summary_reason)

        # Now evaluate Week 8 when regular promo is $0.69
        self.db.record_deals([
            NormalizedDeal(raw_deal_id=34, flyer_id=304, page_number=1, is_front_page=True, canonical_name="Yoplait Yogurt 6 oz", brand="Yoplait", advertised_price=0.69, unit_size=6.0, unit_type="oz", unit_price=0.115, raw_title="Yoplait Yogurt", image_url=None),
        ])

        # Verify cluster_episodes properly grouped weeks 1-3 into 1 single episode
        history = self.db.get_product_price_history(yogurt_w3.product_id)
        past_obs_for_f4 = [h for h in history if h["flyer_id"] in (301, 302, 303)]
        episodes = self.analyzer.cluster_episodes(past_obs_for_f4)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].price, 0.37)
        self.assertEqual(episodes[0].observations_count, 3)

        # Now in flyer 305 (months later), yogurt returns to $0.37 floor after being at $0.69
        f5 = FlyerMetadata(id=305, merchant="Tom Thumb", merchant_id=2381, name="Ad 5", postal_code="00000", valid_from="2026-10-01T00:00:00", valid_to="2026-10-07T23:59:59")
        self.db.upsert_flyer_run(f5)
        self.db.record_deals([
            NormalizedDeal(raw_deal_id=35, flyer_id=305, page_number=1, is_front_page=True, canonical_name="Yoplait Yogurt 6 oz", brand="Yoplait", advertised_price=0.37, unit_size=6.0, unit_type="oz", unit_price=0.0617, raw_title="Yoplait Yogurt", image_url=None),
        ])

        evals_w5 = self.analyzer.evaluate_flyer(305)
        yogurt_w5 = next(e for e in evals_w5 if "Yoplait" in e.canonical_name)
        # Because history has variation ($0.37 and $0.69), returning to $0.37 is a genuine Matches All-Time Low!
        self.assertEqual(yogurt_w5.badge, "ALL_TIME_LOW")
        self.assertIn("Matches All-Time Low", yogurt_w5.summary_reason)


if __name__ == "__main__":
    unittest.main()
