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

    def test_coordinated_poultry_cuts_expansion(self):
        item = FlyerItem(
            id=1003,
            flyer_id=8000,
            name="Signature SELECT Fresh Boneless Skinless Chicken Breasts or Thighs Value Pack",
            price=2.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Signature SELECT",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].canonical_name, "Boneless Skinless Chicken Breasts")
        self.assertEqual(deals[0].brand, "Signature SELECT")
        self.assertEqual(deals[0].advertised_price, 2.99)

        self.assertEqual(deals[1].canonical_name, "Boneless Skinless Chicken Thighs")
        self.assertEqual(deals[1].brand, "Signature SELECT")
        self.assertEqual(deals[1].advertised_price, 2.99)

    def test_coordinated_and_comma_compound_expansion(self):
        item = FlyerItem(
            id=1004,
            flyer_id=8000,
            name="Boneless Skinless Chicken Breasts or Thighs, Pork Chops or Pork Spare Ribs",
            price=1.77,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 4)
        names = [d.canonical_name for d in deals]
        self.assertEqual(
            names,
            [
                "Boneless Skinless Chicken Breasts",
                "Boneless Skinless Chicken Thighs",
                "Pork Chops",
                "Pork Spare Ribs",
            ],
        )

    def test_packaging_and_sales_notes_filtering(self):
        item = FlyerItem(
            id=1005,
            flyer_id=8131286,
            name="WATERFRONT BISTRO® Extra Jumbo Raw Shrimp 16-20 ct., Sold in a 2 lb. bag for $13.98 each Limit 2 or Fresh Whole Atlantic Salmon Fillets Half or Seasoned $7.99 lb.",
            price=6.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="WATERFRONT BISTRO®",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        names = [d.canonical_name for d in deals]
        self.assertEqual(
            names,
            [
                "WATERFRONT BISTRO Extra Jumbo Raw Shrimp 16-20 ct",
                "Whole Atlantic Salmon Fillets Half",
            ],
        )

    def test_store_brand_packaged_produce_retains_brand(self):
        item = FlyerItem(
            id=1006,
            flyer_id=8131286,
            name="Signature Select® Avocados",
            price=4.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Signature SELECT®",
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Signature Select Avocados")
        self.assertEqual(deals[0].brand, "Signature SELECT")
        self.assertEqual(deals[0].advertised_price, 4.49)


if __name__ == "__main__":
    unittest.main()
