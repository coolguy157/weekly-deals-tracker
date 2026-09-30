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

    def test_store_brand_egg_cheese_tortilla_disaggregation(self):
        item = FlyerItem(
            id=1041241160,
            flyer_id=8141410,
            name="Lucerne® Cheese 6-8 oz., Large Eggs Grade AA, 18 ct., Select Varieties or Mission Soft Taco Tortilla 10 ct.",
            price=1.79,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne | Mission",
            page_number=1,
            is_front_page=True,
            cutout_image_url="http://image.com/deal.jpg",
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)

        self.assertEqual(deals[0].canonical_name, "Lucerne Cheese 6-8 oz")
        self.assertEqual(deals[0].brand, "Lucerne")
        self.assertEqual(deals[0].advertised_price, 1.79)
        self.assertEqual(deals[0].unit_size, 7.0)
        self.assertEqual(deals[0].unit_type, "oz")

        self.assertEqual(deals[1].canonical_name, "Lucerne Large Eggs 18 ct")
        self.assertEqual(deals[1].brand, "Lucerne")
        self.assertEqual(deals[1].advertised_price, 1.79)
        self.assertEqual(deals[1].unit_size, 18.0)
        self.assertEqual(deals[1].unit_type, "ct")

        self.assertEqual(deals[2].canonical_name, "Mission Soft Taco Tortilla 10 ct")
        self.assertEqual(deals[2].brand, "Mission")
        self.assertEqual(deals[2].advertised_price, 1.79)
        self.assertEqual(deals[2].unit_size, 10.0)
        self.assertEqual(deals[2].unit_type, "ct")

    def test_seasoning_packet_canonicalization(self):
        item = FlyerItem(
            id=1007,
            flyer_id=8141410,
            name="Libby's Canned Vegetables 14.5-15 oz., McCormick Taco Seasoning 1-1.2 oz. or Ro-Tel Tomatoes 10 oz.",
            price=0.47,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Libby's",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)

        self.assertEqual(deals[0].canonical_name, "Libby's Canned Vegetables 14.5-15 oz")
        self.assertEqual(deals[0].brand, "Libby's")
        self.assertEqual(deals[0].advertised_price, 0.47)

        self.assertEqual(deals[1].canonical_name, "McCormick Taco Seasoning")
        self.assertEqual(deals[1].brand, "McCormick")
        self.assertEqual(deals[1].unit_size, 1.1)
        self.assertEqual(deals[1].unit_type, "oz")
        self.assertEqual(deals[1].advertised_price, 0.47)

        self.assertEqual(deals[2].canonical_name, "Ro-Tel Tomatoes 10 oz")
        self.assertEqual(deals[2].brand, "Ro-Tel")
        self.assertEqual(deals[2].advertised_price, 0.47)

    def test_boneless_skinless_comma_disaggregation(self):
        item = FlyerItem(
            id=1041241184,
            flyer_id=8141410,
            name="Boneless, Skinless Chicken Breasts or Thighs",
            price=1.69,
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
        self.assertEqual(len(deals), 2)

        self.assertEqual(deals[0].canonical_name, "Boneless Skinless Chicken Breasts")
        self.assertEqual(deals[0].advertised_price, 1.69)

        self.assertEqual(deals[1].canonical_name, "Boneless Skinless Chicken Thighs")
        self.assertEqual(deals[1].advertised_price, 1.69)

    def test_produce_variety_list_expansion(self):
        item = FlyerItem(
            id=1008,
            flyer_id=8141410,
            name="Signature SELECT® Baby Potatoes Red, Gold or Medley",
            price=3.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Signature SELECT®",
            page_number=3,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)
        self.assertEqual(deals[0].canonical_name, "Signature SELECT Baby Potatoes Red")
        self.assertEqual(deals[0].brand, "Signature SELECT")
        self.assertEqual(deals[1].canonical_name, "Signature SELECT Baby Potatoes Gold")
        self.assertEqual(deals[1].brand, "Signature SELECT")
        self.assertEqual(deals[2].canonical_name, "Signature SELECT Baby Potatoes Medley")
        self.assertEqual(deals[2].brand, "Signature SELECT")

    def test_brand_pair_shared_size_expansion(self):
        item = FlyerItem(
            id=1009,
            flyer_id=8141410,
            name="Doritos, Tostitos 6-13 oz., Miss Vickie's Kettle 8 oz., Simply Naked Chips 8-9.25 oz. or Tostito's Salsa 15.5 oz.",
            price=2.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Doritos | Tostitos | Miss Vickie's | Simply Naked",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 5)
        self.assertEqual(deals[0].canonical_name, "Doritos 6-13 oz")
        self.assertEqual(deals[0].brand, "Doritos")
        self.assertEqual(deals[0].unit_size, 9.5)
        self.assertEqual(deals[1].canonical_name, "Tostitos 6-13 oz")
        self.assertEqual(deals[1].brand, "Tostitos")
        self.assertEqual(deals[1].unit_size, 9.5)

    def test_department_banner_ignored(self):
        item = FlyerItem(
            id=1010,
            flyer_id=8141410,
            name="GROCERIES",
            price=None,
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
        self.assertEqual(len(deals), 0)

    def test_cheap_chicken_monday_standardization(self):
        item1 = FlyerItem(
            id=1011,
            flyer_id=8141410,
            name="Cheap Chicken",
            price=5.99,
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
        deals1 = self.normalizer.disaggregate_and_normalize(item1)
        self.assertEqual(len(deals1), 1)
        self.assertEqual(deals1[0].canonical_name, "Cheap Chicken Monday 8 Piece Dark Meat")
        self.assertEqual(deals1[0].brand, "Signature Cafe")
        self.assertEqual(deals1[0].unit_size, 8.0)
        self.assertEqual(deals1[0].unit_type, "ct")
        self.assertAlmostEqual(deals1[0].unit_price, round(5.99 / 8.0, 4))

        item2 = FlyerItem(
            id=1012,
            flyer_id=8131286,
            name="Cheap Chicken MONDAY",
            price=5.99,
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
        deals2 = self.normalizer.disaggregate_and_normalize(item2)
        self.assertEqual(len(deals2), 1)
        self.assertEqual(deals2[0].canonical_name, "Cheap Chicken Monday 8 Piece Dark Meat")
        self.assertEqual(deals2[0].brand, "Signature Cafe")

    def test_produce_suffix_list_expansion(self):
        item = FlyerItem(
            id=1013,
            flyer_id=8131286,
            name="Organic Sugar Pie Pumpkins or Acorn, Butternut or Spaghetti Squash",
            price=1.69,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 4)
        self.assertEqual(deals[0].canonical_name, "Organic Sugar Pie Pumpkins")
        self.assertEqual(deals[1].canonical_name, "Acorn Squash")
        self.assertEqual(deals[2].canonical_name, "Butternut Squash")
        self.assertEqual(deals[3].canonical_name, "Spaghetti Squash")

    def test_prefix_coordination_pancakes_waffles(self):
        item = FlyerItem(
            id=1014,
            flyer_id=8131286,
            name="Premier Protein Frozen Pancakes or Waffles",
            price=5.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Premier Protein",
            page_number=2,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].canonical_name, "Premier Protein Frozen Pancakes")
        self.assertEqual(deals[0].brand, "Premier Protein")
        self.assertEqual(deals[1].canonical_name, "Premier Protein Frozen Waffles")
        self.assertEqual(deals[1].brand, "Premier Protein")

    def test_leading_decimal_size_parsing(self):
        size, unit = self.normalizer.extract_unit_info("Vitamin Water 6 Pack .5 ltr")
        self.assertEqual(size, 6.0)
        self.assertEqual(unit, "pk")

        size2, unit2 = self.normalizer.extract_unit_info(".5 ltr")
        self.assertEqual(size2, 0.5)
        self.assertEqual(unit2, "ltr")

    def test_adjacent_cheese_types_disaggregation(self):
        item = FlyerItem(
            id=1015,
            flyer_id=8131286,
            name="Lucerne® Shredded Cheese String Cheese 32 oz., Fage Greek Yogurt 32 oz., Horizon Organic Milk Half Gallon",
            price=4.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne®",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 4)
        self.assertEqual(deals[0].canonical_name, "Lucerne Shredded Cheese 32 oz")
        self.assertEqual(deals[0].brand, "Lucerne")
        self.assertEqual(deals[0].unit_size, 32.0)
        self.assertEqual(deals[0].unit_type, "oz")

        self.assertEqual(deals[1].canonical_name, "Lucerne String Cheese 32 oz")
        self.assertEqual(deals[1].brand, "Lucerne")
        self.assertEqual(deals[1].unit_size, 32.0)

        self.assertEqual(deals[2].canonical_name, "Fage Greek Yogurt 32 oz")
        self.assertEqual(deals[2].brand, "Fage")

        self.assertEqual(deals[3].canonical_name, "Horizon Organic Milk Half Gallon")
        self.assertEqual(deals[3].brand, "Horizon")

    def test_coordinated_cheese_list_disaggregation(self):
        item = FlyerItem(
            id=1016,
            flyer_id=20260506,
            name="Lucerne Chunk, Shredded or Sliced Cheese 24-32 oz",
            price=7.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)
        self.assertEqual(deals[0].canonical_name, "Lucerne Chunk Cheese 24-32 oz")
        self.assertEqual(deals[0].brand, "Lucerne")
        self.assertEqual(deals[0].unit_size, 28.0)

        self.assertEqual(deals[1].canonical_name, "Lucerne Shredded Cheese 24-32 oz")
        self.assertEqual(deals[1].brand, "Lucerne")
        self.assertEqual(deals[1].unit_size, 28.0)

        self.assertEqual(deals[2].canonical_name, "Lucerne Sliced Cheese 24-32 oz")
        self.assertEqual(deals[2].brand, "Lucerne")
        self.assertEqual(deals[2].unit_size, 28.0)

    def test_lucerne_shredded_cheese_size_unification(self):
        item_8oz = FlyerItem(
            id=1017,
            flyer_id=20260902,
            name="Lucerne Shredded Cheese 8 oz",
            price=1.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals_8oz = self.normalizer.disaggregate_and_normalize(item_8oz)
        self.assertEqual(len(deals_8oz), 1)
        self.assertEqual(deals_8oz[0].canonical_name, "Lucerne Shredded Cheese 6-8 oz")
        self.assertEqual(deals_8oz[0].unit_size, 7.0)
        self.assertEqual(deals_8oz[0].unit_type, "oz")
        self.assertAlmostEqual(deals_8oz[0].unit_price, round(1.49 / 7.0, 4))

        item_range = FlyerItem(
            id=1018,
            flyer_id=20260527,
            name="Lucerne Shredded Cheese 6-8 oz",
            price=1.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals_range = self.normalizer.disaggregate_and_normalize(item_range)
        self.assertEqual(len(deals_range), 1)
        self.assertEqual(deals_range[0].canonical_name, "Lucerne Shredded Cheese 6-8 oz")
        self.assertEqual(deals_range[0].unit_size, 7.0)


if __name__ == "__main__":
    unittest.main()
