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

    def test_decimal_alignment_across_badges(self):
        from src.formatter import format_price_decimal_aligned, print_deal_card, visual_len
        import re

        # Test format_price_decimal_aligned
        self.assertEqual(format_price_decimal_aligned(1.97, width=7), "  $1.97")
        self.assertEqual(format_price_decimal_aligned(12.00, width=7), " $12.00")
        self.assertEqual(format_price_decimal_aligned(0.97, width=7), "  $0.97")
        self.assertEqual(format_price_decimal_aligned(None, width=7), " See ad")
        self.assertEqual(format_price_decimal_aligned(0.0, is_free=True, width=7), "   FREE")

        # Test visual column alignment to decimal point across different badges
        badges_to_test = ["POINTS_REWARD", "BEAT_AVERAGE", "NEW_ALL_TIME_LOW", "STANDARD_DEAL", "CYCLE_REFRESH"]
        captured_lines = []
        for badge_name in badges_to_test:
            ev = DealEvaluation(
                deal_id=1,
                product_id=1,
                canonical_name="Test Product",
                brand="Test Brand",
                current_price=2.97,
                unit_price=2.97,
                page_number=1,
                is_front_page=True,
                historical_min=2.97,
                historical_avg=3.49,
                historical_max=3.99,
                past_observations_count=5,
                diff_pct_vs_avg=-14.3,
                badge=badge_name,
                summary_reason="Test reason",
            )
            buf = StringIO()
            sys.stdout = buf
            try:
                print_deal_card(ev, verbose=False)
                captured_lines.append(buf.getvalue().strip())
            finally:
                sys.stdout = sys.__stdout__

        dot_columns = []
        for line in captured_lines:
            clean = re.sub(r"\033\[[0-9;]*m", "", line)
            dot_idx = clean.find(".")
            dot_columns.append(visual_len(clean[:dot_idx]))

        # All badges must align the decimal point at the exact same visual column
        self.assertEqual(len(set(dot_columns)), 1)


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
            # Grouped by default
            render_filtered_report([ev], flyer_id=999, title="TEST REPORT", search_query="milk")
            output = captured_output.getvalue()
            self.assertIn("TEST REPORT (Flyer ID: 999) - 1 circular ads (1 items)", output)
            self.assertIn("Search full price history", output)

            # Flat mode
            captured_output.seek(0)
            captured_output.truncate(0)
            render_filtered_report([ev], flyer_id=999, title="TEST REPORT", search_query="milk", flat=True)
            output_flat = captured_output.getvalue()
            self.assertIn("TEST REPORT (Flyer ID: 999) - 1 items", output_flat)
        finally:
            sys.stdout = sys.__stdout__


if __name__ == "__main__":
    unittest.main()
