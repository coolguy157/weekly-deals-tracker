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


if __name__ == "__main__":
    unittest.main()

