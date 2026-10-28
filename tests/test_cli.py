"""
Unit tests for CLI store presets, environment parsing, and store resolution.
"""

import unittest
from unittest.mock import patch, MagicMock
import argparse
from src.cli import resolve_store, parse_store_configs, STORE_PRESETS, cmd_sync


class TestCLIStoreConfiguration(unittest.TestCase):

    def test_store_presets_definitions(self):
        self.assertIn("giant", STORE_PRESETS)
        self.assertIn("lewisburg", STORE_PRESETS)
        self.assertIn("tomthumb", STORE_PRESETS)

        giant = resolve_store("giant")
        self.assertIsNotNone(giant)
        self.assertEqual(giant["zip"], "17837")
        self.assertEqual(giant["merchant"], "Giant Food Stores")

        lewisburg = resolve_store("Lewisburg")
        self.assertEqual(lewisburg["zip"], "17837")

    def test_parse_store_configs(self):
        configs = parse_store_configs("17837:Giant Food Stores, 75080:Tom Thumb")
        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0], ("17837", "Giant Food Stores"))
        self.assertEqual(configs[1], ("75080", "Tom Thumb"))

    @patch("src.cli._sync_single_store")
    def test_cmd_sync_preset(self, mock_sync_single):
        args = argparse.Namespace(
            store="giant",
            zip=None,
            merchant=None,
            all_stores=False,
            front_page_only=False,
            enrich_app=False,
            db=":memory:",
        )
        cmd_sync(args)
        mock_sync_single.assert_called_once_with("17837", "Giant Food Stores", front_page_only=False, enrich_app=False, db_path=":memory:")

    @patch("src.cli._sync_single_store")
    def test_cmd_sync_all_stores(self, mock_sync_single):
        args = argparse.Namespace(
            store=None,
            zip=None,
            merchant=None,
            all_stores=True,
            front_page_only=True,
            enrich_app=False,
            db=":memory:",
        )
        cmd_sync(args)
        self.assertEqual(mock_sync_single.call_count, 2)

    @patch("src.cli._sync_single_store")
    def test_cmd_sync_default_tomthumb(self, mock_sync_single):
        """Verify that cmd_sync defaults to Tom Thumb when no flags are provided."""
        args = argparse.Namespace(
            store=None,
            zip=None,
            merchant=None,
            all_stores=False,
            front_page_only=False,
            enrich_app=False,
            db=":memory:",
        )
        with patch.dict("os.environ", {}, clear=True):
            cmd_sync(args)
        mock_sync_single.assert_called_once_with("75080", "Tom Thumb", front_page_only=False, enrich_app=False, db_path=":memory:")

    def test_resolve_merchant_filter(self):
        from src.cli import _resolve_merchant_filter
        # Default
        args_empty = argparse.Namespace(store=None, merchant=None)
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(_resolve_merchant_filter(args_empty), "Tom Thumb")

        # Preset store override
        args_giant = argparse.Namespace(store="giant", merchant=None)
        self.assertEqual(_resolve_merchant_filter(args_giant), "Giant Food Stores")

        # Explicit merchant override
        args_merchant = argparse.Namespace(store=None, merchant="Safeway")
        self.assertEqual(_resolve_merchant_filter(args_merchant), "Safeway")

    def test_cmd_history_grouped_and_skus(self):
        from src.cli import cmd_history
        from io import StringIO
        import sys

        mock_db = MagicMock()
        mock_db.get_grouped_price_history.return_value = [
            {
                "title": "Turkey Hill Ice Cream",
                "brands": ["Turkey Hill"],
                "categories": ["Ice Cream"],
                "runs": [
                    {
                        "valid_from": "2026-10-23",
                        "valid_to": "2026-10-30",
                        "merchant": "Giant Food Stores",
                        "min_price": 3.49,
                        "max_price": 3.49,
                        "min_unit_price": None,
                        "max_unit_price": None,
                        "unit_type": None,
                        "promo_detail": None,
                        "pages": [1],
                        "is_front_page": True,
                        "is_trusted": True,
                        "is_doorbuster": False,
                        "varieties": ["Vanilla", "Chocolate"],
                        "observations": [
                            {"canonical_name": "Vanilla", "advertised_price": 3.49, "deal_id": 1, "unit_price": None, "unit_type": None},
                            {"canonical_name": "Chocolate", "advertised_price": 3.49, "deal_id": 2, "unit_price": None, "unit_type": None},
                        ],
                    }
                ],
            }
        ]

        # 1. Default grouped call
        args_grouped = argparse.Namespace(
            db=":memory:",
            query="ice cream",
            store="giant",
            merchant=None,
            trusted_only=False,
            limit=None,
            skus=False,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_history(args_grouped)
            output = buf.getvalue()
            self.assertIn("Group: Turkey Hill Ice Cream", output)
            self.assertIn("2 varieties", output)
            self.assertNotIn("[Deal ID: 1]", output)

        # 2. Detailed SKUs call
        args_skus = argparse.Namespace(
            db=":memory:",
            query="ice cream",
            store="giant",
            merchant=None,
            trusted_only=False,
            limit=None,
            skus=True,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_history(args_skus)
            output = buf.getvalue()
            self.assertIn("Group: Turkey Hill Ice Cream", output)
            self.assertIn("[Deal ID: 1]", output)
            self.assertIn("[Deal ID: 2]", output)

    def test_cmd_deals_grouped_and_skus_and_flat(self):
        from src.cli import cmd_deals
        from src.analyzer import DealEvaluation
        from io import StringIO

        mock_db = MagicMock()
        mock_db.get_latest_flyer_id.return_value = 12345

        ev1 = DealEvaluation(
            deal_id=1,
            product_id=10,
            canonical_name="Turkey Hill Vanilla Ice Cream",
            brand="Turkey Hill",
            current_price=3.49,
            unit_price=0.07,
            page_number=1,
            is_front_page=True,
            historical_min=3.49,
            historical_avg=4.00,
            historical_max=4.50,
            past_observations_count=5,
            diff_pct_vs_avg=-12.5,
            badge="NEW_ALL_TIME_LOW",
            summary_reason="🌟 New All-Time Low",
            ad_title="Turkey Hill Ice Cream",
        )
        ev2 = DealEvaluation(
            deal_id=2,
            product_id=11,
            canonical_name="Turkey Hill Chocolate Ice Cream",
            brand="Turkey Hill",
            current_price=3.49,
            unit_price=0.07,
            page_number=1,
            is_front_page=True,
            historical_min=3.49,
            historical_avg=4.00,
            historical_max=4.50,
            past_observations_count=5,
            diff_pct_vs_avg=-12.5,
            badge="NEW_ALL_TIME_LOW",
            summary_reason="🌟 New All-Time Low",
            ad_title="Turkey Hill Ice Cream",
        )

        mock_analyzer = MagicMock()
        mock_analyzer.evaluate_flyer.return_value = [ev1, ev2]

        # 1. Default grouped call
        args_grouped = argparse.Namespace(
            db=":memory:",
            store="giant",
            merchant=None,
            flyer_id=12345,
            front_page_only=False,
            query=None,
            category=None,
            atl_only=False,
            cat_best_only=False,
            price_hikes_only=False,
            all_pages=False,
            include_see_ad=False,
            sort_unit_price=False,
            verbose=False,
            skus=False,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db), patch("src.cli.DealAnalyzer", return_value=mock_analyzer):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_deals(args_grouped)
            output = buf.getvalue()
            self.assertIn("Turkey Hill Ice Cream", output)
            self.assertIn("2 varieties", output)
            self.assertNotIn("[Deal ID: 1]", output)

        # 2. Detailed SKUs call
        args_skus = argparse.Namespace(
            db=":memory:",
            store="giant",
            merchant=None,
            flyer_id=12345,
            front_page_only=False,
            query=None,
            category=None,
            atl_only=False,
            cat_best_only=False,
            price_hikes_only=False,
            all_pages=False,
            include_see_ad=False,
            sort_unit_price=False,
            verbose=False,
            skus=True,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db), patch("src.cli.DealAnalyzer", return_value=mock_analyzer):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_deals(args_skus)
            output = buf.getvalue()
            self.assertIn("Turkey Hill Ice Cream", output)
            self.assertIn("[Deal ID: 1]", output)
            self.assertIn("[Deal ID: 2]", output)

        # 3. Flat legacy call
        args_flat = argparse.Namespace(
            db=":memory:",
            store="giant",
            merchant=None,
            flyer_id=12345,
            front_page_only=False,
            query=None,
            category=None,
            atl_only=False,
            cat_best_only=False,
            price_hikes_only=False,
            all_pages=False,
            include_see_ad=False,
            sort_unit_price=False,
            verbose=False,
            skus=False,
            flat=True,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db), patch("src.cli.DealAnalyzer", return_value=mock_analyzer):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_deals(args_flat)
            output = buf.getvalue()
            self.assertIn("Turkey Hill Vanilla Ice Cream", output)
            self.assertIn("Turkey Hill Chocolate Ice Cream", output)
            self.assertNotIn("[2 varieties", output)

    def test_cmd_deals_alcohol_filtering(self):
        from src.cli import cmd_deals
        from src.analyzer import DealEvaluation
        from io import StringIO

        mock_db = MagicMock()
        mock_db.get_latest_flyer_id.return_value = 12345

        food_deal = DealEvaluation(
            deal_id=1,
            product_id=10,
            canonical_name="Boneless Skinless Chicken Breasts",
            brand="Signature SELECT",
            category="Meat & Seafood",
            current_price=2.77,
            unit_price=2.77,
            page_number=1,
            is_front_page=True,
            historical_min=1.97,
            historical_avg=2.85,
            historical_max=3.99,
            past_observations_count=5,
            diff_pct_vs_avg=-2.8,
            badge="DEAL",
            summary_reason="🏷️ Standard Deal",
            ad_title="Chicken Breasts",
        )
        beer_deal = DealEvaluation(
            deal_id=2,
            product_id=11,
            canonical_name="Bud Light 24 pk",
            brand="Budweiser",
            category="Beer",
            current_price=21.99,
            unit_price=None,
            page_number=1,
            is_front_page=True,
            historical_min=19.99,
            historical_avg=22.99,
            historical_max=24.99,
            past_observations_count=4,
            diff_pct_vs_avg=-4.3,
            badge="DEAL",
            summary_reason="🏷️ Standard Deal",
            ad_title="Bud, Miller or Coors Beer",
        )
        wine_deal = DealEvaluation(
            deal_id=3,
            product_id=12,
            canonical_name="LaMarca Prosecco 750 ml",
            brand="LaMarca",
            category="Wine",
            current_price=14.99,
            unit_price=None,
            page_number=1,
            is_front_page=True,
            historical_min=13.99,
            historical_avg=15.99,
            historical_max=16.99,
            past_observations_count=3,
            diff_pct_vs_avg=-6.2,
            badge="DEAL",
            summary_reason="🏷️ Standard Deal",
            ad_title="LaMarca Sparkling Wine",
        )

        mock_analyzer = MagicMock()
        mock_analyzer.evaluate_flyer.return_value = [food_deal, beer_deal, wine_deal]

        # 1. Default deals call excludes alcohol deals
        args_default = argparse.Namespace(
            db=":memory:",
            store="tomthumb",
            merchant=None,
            flyer_id=12345,
            front_page_only=False,
            query=None,
            category=None,
            atl_only=False,
            cat_best_only=False,
            price_hikes_only=False,
            all_pages=False,
            include_see_ad=False,
            include_alcohol=False,
            sort_unit_price=False,
            verbose=False,
            skus=False,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db), patch("src.cli.DealAnalyzer", return_value=mock_analyzer):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_deals(args_default)
            output = buf.getvalue()
            self.assertIn("Chicken Breasts", output)
            self.assertNotIn("Bud, Miller or Coors", output)
            self.assertNotIn("LaMarca Sparkling Wine", output)

        # 2. Including alcohol shows both food and alcohol
        args_with_alcohol = argparse.Namespace(
            db=":memory:",
            store="tomthumb",
            merchant=None,
            flyer_id=12345,
            front_page_only=False,
            query=None,
            category=None,
            atl_only=False,
            cat_best_only=False,
            price_hikes_only=False,
            all_pages=False,
            include_see_ad=False,
            include_alcohol=True,
            sort_unit_price=False,
            verbose=False,
            skus=False,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db), patch("src.cli.DealAnalyzer", return_value=mock_analyzer):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_deals(args_with_alcohol)
            output = buf.getvalue()
            self.assertIn("Chicken Breasts", output)
            self.assertIn("Bud, Miller or Coors", output)
            self.assertIn("LaMarca Sparkling Wine", output)

        # 3. Querying for beer explicitly shows beer even if include_alcohol is False
        args_query_beer = argparse.Namespace(
            db=":memory:",
            store="tomthumb",
            merchant=None,
            flyer_id=12345,
            front_page_only=False,
            query="beer",
            category=None,
            atl_only=False,
            cat_best_only=False,
            price_hikes_only=False,
            all_pages=False,
            include_see_ad=False,
            include_alcohol=False,
            sort_unit_price=False,
            verbose=False,
            skus=False,
            flat=False,
        )
        with patch("src.cli.DealsDatabase", return_value=mock_db), patch("src.cli.DealAnalyzer", return_value=mock_analyzer):
            buf = StringIO()
            with patch("sys.stdout", buf):
                cmd_deals(args_query_beer)
            output = buf.getvalue()
            self.assertIn("Bud, Miller or Coors", output)




if __name__ == "__main__":
    unittest.main()

