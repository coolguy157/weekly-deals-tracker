"""
Unit tests for terminal formatting and layout views.
"""

import unittest
from io import StringIO
import sys
from src.formatter import format_badge_fixed, format_badge, format_unit_price, print_deal_card, render_filtered_report, render_smart_digest
from src.analyzer import DealEvaluation


class TestFormatter(unittest.TestCase):

    def test_format_unit_price(self):
        self.assertEqual(format_unit_price(0.1559, "oz"), "$0.16/oz")
        self.assertEqual(format_unit_price(0.069, "oz"), "$0.069/oz")
        self.assertEqual(format_unit_price(7.99, "lb"), "$7.99/lb")
        self.assertEqual(format_unit_price(None, "oz"), "")
        self.assertEqual(format_unit_price(1.50, None), "")

    def test_format_badge_fixed(self):
        atl_badge = format_badge_fixed("ALL_TIME_LOW", width=16)
        self.assertIn("[* ALL-TIME LOW]", atl_badge)
        self.assertIn("\033[92m", atl_badge)

        hike_badge = format_badge_fixed("PRICE_HIKE", width=16)
        self.assertIn("[! PRICE HIKE]", hike_badge)
        self.assertIn("\033[91m", hike_badge)

    def test_format_badge(self):
        badge = format_badge("CYCLE_REFRESH")
        self.assertIn("[~ CYCLE REFRESH]", badge)

    def test_print_deal_card(self):
        ev = DealEvaluation(
            deal_id=1,
            product_id=10,
            canonical_name="Lucerne Milk 1 Gallon",
            brand="Lucerne",
            current_price=2.99,
            unit_price=2.99,
            page_number=1,
            is_front_page=True,
            historical_min=2.99,
            historical_avg=3.49,
            historical_max=3.99,
            past_observations_count=5,
            diff_pct_vs_avg=-14.3,
            badge="ALL_TIME_LOW",
            summary_reason="🌟 Matches All-Time Low ($2.99)",
        )

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            print_deal_card(ev, verbose=False)
            output = captured_output.getvalue()
            self.assertIn("Lucerne Milk 1 Gallon", output)
            self.assertIn("$2.99", output)
            self.assertIn("p.1 (Cover)", output)
            self.assertIn("ALL-TIME LOW", output)
        finally:
            sys.stdout = sys.__stdout__

    def test_render_filtered_report(self):
        ev = DealEvaluation(
            deal_id=1,
            product_id=10,
            canonical_name="Lucerne Milk 1 Gallon",
            brand="Lucerne",
            current_price=2.99,
            unit_price=2.99,
            page_number=1,
            is_front_page=True,
            historical_min=2.99,
            historical_avg=3.49,
            historical_max=3.99,
            past_observations_count=5,
            diff_pct_vs_avg=-14.3,
            badge="ALL_TIME_LOW",
            summary_reason="🌟 Matches All-Time Low ($2.99)",
        )

        captured_output = StringIO()
        sys.stdout = captured_output
        try:
            render_filtered_report([ev], flyer_id=999, title="TEST REPORT", search_query="milk")
            output = captured_output.getvalue()
            self.assertIn("TEST REPORT (Flyer ID: 999) - 1 items", output)
            self.assertIn("Search full price history", output)
        finally:
            sys.stdout = sys.__stdout__


if __name__ == "__main__":
    unittest.main()
