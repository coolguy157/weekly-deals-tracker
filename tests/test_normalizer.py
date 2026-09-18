"""
Unit tests for ProductNormalizer.
"""

import unittest
from src.fetcher import FlyerItem
from src.normalizer import ProductNormalizer


class TestProductNormalizer(unittest.TestCase):

    def setUp(self):
        self.normalizer = ProductNormalizer()

    def test_extract_unit_info_single(self):
        size, unit = self.normalizer.extract_unit_info("Lucerne Large Eggs 12 ct")
        self.assertEqual(size, 12.0)
        self.assertEqual(unit, "ct")

        size, unit = self.normalizer.extract_unit_info("Jimmy Dean Roll Sausage 16 oz.")
        self.assertEqual(size, 16.0)
        self.assertEqual(unit, "oz")

        size, unit = self.normalizer.extract_unit_info("Signature SELECT Ice Cream 1.5 Quart")
        self.assertEqual(size, 1.5)
        self.assertEqual(unit, "qt")

    def test_extract_unit_info_range(self):
        size, unit = self.normalizer.extract_unit_info("Hillshire Farm Smoked Sausage 12-14 oz.")
        self.assertEqual(size, 13.0)  # average of 12 and 14
        self.assertEqual(unit, "oz")

    def test_disaggregate_multi_item_title(self):
        item = FlyerItem(
            id=1001,
            flyer_id=8000,
            name="Sugardale Bacon 12 oz., Jimmy Dean Roll Sausage 16 oz. or Hillshire Farm Smoked Sausage 12-14 oz.",
            price=2.99,
            original_price=5.99,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Sugardale | Jimmy Dean | Hillshire Farm",
            page_number=1,
            is_front_page=True,
            cutout_image_url="http://image.com/deal.jpg",
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)

        self.assertEqual(deals[0].canonical_name, "Sugardale Bacon 12 oz")
        self.assertEqual(deals[0].brand, "Sugardale")
        self.assertEqual(deals[0].unit_size, 12.0)
        self.assertEqual(deals[0].unit_type, "oz")
        self.assertEqual(deals[0].advertised_price, 2.99)
        self.assertAlmostEqual(deals[0].unit_price, round(2.99 / 12.0, 4))

        self.assertEqual(deals[1].canonical_name, "Jimmy Dean Roll Sausage 16 oz")
        self.assertEqual(deals[1].brand, "Jimmy Dean")
        self.assertEqual(deals[1].unit_size, 16.0)
        self.assertEqual(deals[1].unit_type, "oz")
        self.assertAlmostEqual(deals[1].unit_price, round(2.99 / 16.0, 4))

        self.assertEqual(deals[2].canonical_name, "Hillshire Farm Smoked Sausage 12-14 oz")
        self.assertEqual(deals[2].brand, "Hillshire Farm")
        self.assertEqual(deals[2].unit_size, 13.0)
        self.assertEqual(deals[2].unit_type, "oz")

    def test_single_item_normalization(self):
        item = FlyerItem(
            id=1002,
            flyer_id=8000,
            name="Lucerne® Large Eggs 12 ct",
            price=0.97,
            original_price=2.49,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne®",
            page_number=1,
            is_front_page=True,
            cutout_image_url="http://image.com/eggs.jpg",
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Lucerne Large Eggs 12 ct")
        self.assertEqual(deals[0].advertised_price, 0.97)
        self.assertEqual(deals[0].unit_size, 12.0)
        self.assertEqual(deals[0].unit_type, "ct")


if __name__ == "__main__":
    unittest.main()
