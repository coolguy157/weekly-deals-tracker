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
    def test_cmd_sync_enrich_app_flag(self, mock_sync_single):
        args = argparse.Namespace(
            store="tomthumb",
            zip=None,
            merchant=None,
            all_stores=False,
            front_page_only=False,
            enrich_app=True,
            db=":memory:",
        )
        cmd_sync(args)
        mock_sync_single.assert_called_once_with("75080", "Tom Thumb", front_page_only=False, enrich_app=True, db_path=":memory:")


if __name__ == "__main__":
    unittest.main()
