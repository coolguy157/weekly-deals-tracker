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

    def test_bulk_package_rate_normalization(self):
        item = FlyerItem(
            id=1046437290,
            flyer_id=8180797,
            name="Signature SELECT® Thick Sliced Bacon Sold in 3 lb. Package for $11.97 ea., Hillshire Farm Lunchmeat 7-9 oz. or Owens Breakfast Sausage 12-16 oz.",
            price=3.99,
            original_price=None,
            page_number=1,
            is_front_page=True,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Signature SELECT | Hillshire Farm | Owens",
            cutout_image_url=None,
            clean_image_url=None,
        )

        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)

        bacon_deal = deals[0]
        self.assertEqual(bacon_deal.canonical_name, "Thick Sliced Bacon")
        self.assertEqual(bacon_deal.brand, "Signature SELECT")
        self.assertEqual(bacon_deal.unit_size, 3.0)
        self.assertEqual(bacon_deal.unit_type, "lb")
        self.assertEqual(bacon_deal.advertised_price, 11.97)
        self.assertEqual(bacon_deal.unit_price, 3.99)
        self.assertEqual(bacon_deal.promo_type, "must_buy")
        self.assertEqual(bacon_deal.promo_detail, "Sold in 3 lb pkg")

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

    def test_cream_cheese_multipack_unit_resolution(self):
        item = FlyerItem(
            id=1019,
            flyer_id=20260506,
            name="Philadelphia Cream Cheese 2 Pack",
            price=4.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Philadelphia",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Philadelphia Cream Cheese 2 Pack")
        self.assertEqual(deals[0].brand, "Philadelphia")
        self.assertEqual(deals[0].unit_size, 16.0)
        self.assertEqual(deals[0].unit_type, "oz")
        self.assertAlmostEqual(deals[0].unit_price, round(4.99 / 16.0, 4))

    def test_deli_cheese_per_lb_resolution(self):
        item = FlyerItem(
            id=1020,
            flyer_id=8159624,
            name="Primo Taglio American Cheese",
            price=7.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Primo Taglio",
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Primo Taglio American Cheese")
        self.assertEqual(deals[0].brand, "Primo Taglio")
        self.assertEqual(deals[0].unit_size, 1.0)
        self.assertEqual(deals[0].unit_type, "lb")
        self.assertAlmostEqual(deals[0].unit_price, 7.99)

    def test_single_serve_yogurt_canonicalization(self):
        # 1. Unsized hero title
        item_unsized = FlyerItem(
            id=1021,
            flyer_id=8131286,
            name="Yoplait Yogurt or Kraft Original Macaroni & Cheese",
            price=0.37,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Yoplait | Kraft",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals1 = self.normalizer.disaggregate_and_normalize(item_unsized)
        yoplait1 = next(d for d in deals1 if d.brand == "Yoplait")
        self.assertEqual(yoplait1.canonical_name, "Yoplait Yogurt 4-6 oz")
        self.assertEqual(yoplait1.unit_size, 5.0)
        self.assertEqual(yoplait1.unit_type, "oz")

        # 2. Sized range title
        item_ranged = FlyerItem(
            id=1022,
            flyer_id=8159624,
            name="Tina's Burritos 4 oz., Yoplait Yogurt 4-6 oz.,",
            price=0.37,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Tina's | Yoplait",
            page_number=3,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals2 = self.normalizer.disaggregate_and_normalize(item_ranged)
        yoplait2 = next(d for d in deals2 if d.brand == "Yoplait")
        self.assertEqual(yoplait2.canonical_name, "Yoplait Yogurt 4-6 oz")
        self.assertEqual(yoplait2.unit_size, 5.0)
        self.assertEqual(yoplait2.unit_type, "oz")

        # 3. 6 oz single size title
        item_6oz = FlyerItem(
            id=1023,
            flyer_id=20260708,
            name="Lucerne Yogurt 6 oz or Yoplait Yogurt 6 oz",
            price=0.39,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne | Yoplait",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals3 = self.normalizer.disaggregate_and_normalize(item_6oz)
        yoplait3 = next(d for d in deals3 if d.brand == "Yoplait")
        lucerne3 = next(d for d in deals3 if d.brand == "Lucerne")
        self.assertEqual(yoplait3.canonical_name, "Yoplait Yogurt 4-6 oz")
        self.assertEqual(lucerne3.canonical_name, "Lucerne Yogurt 4-6 oz")

    def test_infer_category(self):
        self.assertEqual(self.normalizer.infer_category("Lucerne Shredded Cheese 32 oz"), "Shredded Cheese")
        self.assertEqual(self.normalizer.infer_category("Philadelphia Cream Cheese 8 oz"), "Cream Cheese")
        self.assertEqual(self.normalizer.infer_category("Primo Taglio American Cheese"), "Cheese")
        self.assertEqual(self.normalizer.infer_category("Sugardale Bacon 12 oz"), "Bacon")
        self.assertEqual(self.normalizer.infer_category("Boneless Skinless Chicken Breasts"), "Boneless Chicken Breasts")
        self.assertEqual(self.normalizer.infer_category("Boneless Skinless Chicken Thighs"), "Boneless Chicken Thighs")
        self.assertEqual(self.normalizer.infer_category("Bone-In Chicken Thighs"), "Bone-In Chicken Thighs")
        self.assertEqual(self.normalizer.infer_category("Fresh Chicken Thighs"), "Bone-In Chicken Thighs")
        self.assertEqual(self.normalizer.infer_category("Signature SELECT Ground Beef 80/20 1 lb"), "Ground Beef")

    def test_promo_normalization(self):
        # 1. Must Buy 4 @ $2.49 with unpriced item
        mb_item = FlyerItem(
            id=101,
            flyer_id=1,
            name="Dr Pepper 12 Pack MUST BUY 4 @ $2.49",
            price=None,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Dr Pepper",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        mb_deals = self.normalizer.disaggregate_and_normalize(mb_item)
        self.assertEqual(len(mb_deals), 1)
        self.assertEqual(mb_deals[0].promo_type, "must_buy")
        self.assertEqual(mb_deals[0].qualifying_qty, 4)
        self.assertEqual(mb_deals[0].advertised_price, 2.49)
        self.assertIn("MUST BUY 4 @ $2.49", mb_deals[0].promo_detail)
        self.assertEqual(mb_deals[0].canonical_name, "Dr Pepper 12 Pack")

        # 2. Doritos BUY 2 GET 2 FREE with unpriced item
        bogo_item = FlyerItem(
            id=102,
            flyer_id=1,
            name="Doritos Tortilla Chips 9.25 oz BUY 2 GET 2 FREE",
            price=None,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Doritos",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        bogo_deals = self.normalizer.disaggregate_and_normalize(bogo_item)
        self.assertEqual(len(bogo_deals), 1)
        self.assertEqual(bogo_deals[0].promo_type, "bogo")
        self.assertEqual(bogo_deals[0].qualifying_qty, 4)
        self.assertIsNone(bogo_deals[0].advertised_price)  # Awaits base shelf price
        self.assertEqual(bogo_deals[0].promo_detail, "BUY 2 GET 2 FREE")
        self.assertEqual(bogo_deals[0].canonical_name, "Doritos Tortilla Chips 9.25 oz")

    def test_two_variety_produce_suffix_pair_expansion(self):
        item = FlyerItem(
            id=103,
            flyer_id=1,
            name="Fuji or Granny Smith Apples, Bartlett Pears, Roma Tomatoes or Yellow or White Onions",
            price=0.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        names = [d.canonical_name for d in deals]
        self.assertIn("Fuji Apples", names)
        self.assertIn("Granny Smith Apples", names)
        self.assertIn("Bartlett Pears", names)
        self.assertIn("Roma Tomatoes", names)
        self.assertIn("Yellow Onions", names)
        self.assertIn("White Onions", names)
        
        # Verify categories
        deal_map = {d.canonical_name: d.category for d in deals}
        self.assertEqual(deal_map["Fuji Apples"], "Apples")
        self.assertEqual(deal_map["Granny Smith Apples"], "Apples")
        self.assertEqual(deal_map["Bartlett Pears"], "Pears")
        self.assertEqual(deal_map["Roma Tomatoes"], "Tomatoes")
        self.assertEqual(deal_map["Yellow Onions"], "Onions")
        self.assertEqual(deal_map["White Onions"], "Onions")

    def test_department_banner_discard_even_when_priced(self):
        item = FlyerItem(
            id=104,
            flyer_id=1,
            name="From Your Full Service Butcher Block",
            price=1.27,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 0)

    def test_app_marketing_subtitle_and_ellipsis_cleaning(self):
        item_full = FlyerItem(
            id=105,
            flyer_id=1,
            name="On The Vine Red Tomato - Each (Traditionally comes on the vine)",
            price=0.79,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        item_trunc = FlyerItem(
            id=106,
            flyer_id=1,
            name="On The Vine Red Tomato - Each...mes on the vine)",
            price=0.79,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals_full = self.normalizer.disaggregate_and_normalize(item_full)
        deals_trunc = self.normalizer.disaggregate_and_normalize(item_trunc)
        self.assertEqual(len(deals_full), 1)
        self.assertEqual(len(deals_trunc), 1)
        self.assertEqual(deals_full[0].canonical_name, "On The Vine Red Tomato")
        self.assertEqual(deals_trunc[0].canonical_name, "On The Vine Red Tomato")
        self.assertEqual(deals_full[0].category, "Tomatoes")
        self.assertEqual(deals_trunc[0].category, "Tomatoes")

    def test_meat_multicut_chicken_trio_disaggregation(self):
        item = FlyerItem(
            id=1043139658,
            flyer_id=8159694,
            name="Nature's Promise Fresh Boneless Skinless Chicken Breasts, Thin Sliced or Tenders - $2.99 /lb. DIGITAL COUPON",
            price=2.99,
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
        self.assertEqual(len(deals), 3)

        self.assertEqual(deals[0].canonical_name, "Nature's Promise Fresh Boneless Skinless Chicken Breasts")
        self.assertEqual(deals[0].brand, "Nature's Promise")
        self.assertEqual(deals[0].unit_size, 1.0)
        self.assertEqual(deals[0].unit_type, "lb")
        self.assertEqual(deals[0].promo_type, "digital_coupon")

        self.assertEqual(deals[1].canonical_name, "Nature's Promise Fresh Boneless Skinless Thin Sliced Chicken Breasts")
        self.assertEqual(deals[1].brand, "Nature's Promise")
        self.assertEqual(deals[1].unit_size, 1.0)
        self.assertEqual(deals[1].unit_type, "lb")
        self.assertEqual(deals[1].promo_type, "digital_coupon")

        self.assertEqual(deals[2].canonical_name, "Nature's Promise Fresh Chicken Tenders")
        self.assertEqual(deals[2].brand, "Nature's Promise")
        self.assertEqual(deals[2].unit_size, 1.0)
        self.assertEqual(deals[2].unit_type, "lb")
        self.assertEqual(deals[2].promo_type, "digital_coupon")

    def test_perdue_multicut_chicken_disaggregation(self):
        item = FlyerItem(
            id=2001,
            flyer_id=8159694,
            name="Perdue Fresh Boneless Skinless Chicken Breasts, Thin Sliced or Tenders",
            price=3.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Perdue",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)
        self.assertEqual(deals[0].canonical_name, "Perdue Fresh Boneless Skinless Chicken Breasts")
        self.assertEqual(deals[0].brand, "Perdue")
        self.assertEqual(deals[0].unit_size, 1.0)
        self.assertEqual(deals[0].unit_type, "lb")

        self.assertEqual(deals[1].canonical_name, "Perdue Fresh Boneless Skinless Thin Sliced Chicken Breasts")
        self.assertEqual(deals[1].brand, "Perdue")
        self.assertEqual(deals[1].unit_size, 1.0)

        self.assertEqual(deals[2].canonical_name, "Perdue Fresh Chicken Tenders")
        self.assertEqual(deals[2].brand, "Perdue")
        self.assertEqual(deals[2].unit_size, 1.0)

    def test_giant_produce_salad_dressing_tomatoes_bundle(self):
        item = FlyerItem(
            id=3001,
            flyer_id=8159694,
            name="Nature's Promise Greenhouse Grown Dole or Our Brand Salad Blend or Kit, Bolthouse Dressing or NatureSweet Cherub or Golden Cherub Tomatoes",
            price=2.99,
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
        self.assertEqual(len(deals), 6)

        self.assertEqual(deals[0].canonical_name, "Nature's Promise Greenhouse Grown Salad Blend or Kit")
        self.assertEqual(deals[0].brand, "Nature's Promise")
        self.assertEqual(deals[0].category, "Salad")
        self.assertEqual(deals[0].advertised_price, 2.99)

        self.assertEqual(deals[1].canonical_name, "Dole Salad Blend or Kit")
        self.assertEqual(deals[1].brand, "Dole")
        self.assertEqual(deals[1].category, "Salad")
        self.assertEqual(deals[1].advertised_price, 2.99)

        self.assertEqual(deals[2].canonical_name, "Our Brand Salad Blend or Kit")
        self.assertEqual(deals[2].brand, "Our Brand")
        self.assertEqual(deals[2].category, "Salad")
        self.assertEqual(deals[2].advertised_price, 2.99)

        self.assertEqual(deals[3].canonical_name, "Bolthouse Dressing")
        self.assertEqual(deals[3].brand, "Bolthouse")
        self.assertEqual(deals[3].category, "Salad Dressing")
        self.assertEqual(deals[3].advertised_price, 2.99)

        self.assertEqual(deals[4].canonical_name, "NatureSweet Cherub Tomatoes")
        self.assertEqual(deals[4].brand, "NatureSweet")
        self.assertEqual(deals[4].category, "Tomatoes")
        self.assertEqual(deals[4].advertised_price, 2.99)

        self.assertEqual(deals[5].canonical_name, "NatureSweet Golden Cherub Tomatoes")
        self.assertEqual(deals[5].brand, "NatureSweet")
        self.assertEqual(deals[5].category, "Tomatoes")
        self.assertEqual(deals[5].advertised_price, 2.99)

    def test_salad_blend_kit_coordination_expansion(self):
        item = FlyerItem(
            id=3002,
            flyer_id=8159694,
            name="Dole or Our Brand Salad Blend or Kit",
            price=2.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=2,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].canonical_name, "Dole Salad Blend or Kit")
        self.assertEqual(deals[0].brand, "Dole")
        self.assertEqual(deals[0].category, "Salad")
        self.assertEqual(deals[1].canonical_name, "Our Brand Salad Blend or Kit")
        self.assertEqual(deals[1].brand, "Our Brand")
        self.assertEqual(deals[1].category, "Salad")

    def test_salad_kit_bowl_coordination_expansion(self):
        item = FlyerItem(
            id=3003,
            flyer_id=8159694,
            name="Fresh Express or Taylor Farms Salad Kit or Bowl",
            price=3.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=2,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].canonical_name, "Fresh Express Salad Kit or Bowl")
        self.assertEqual(deals[0].brand, "Fresh Express")
        self.assertEqual(deals[1].canonical_name, "Taylor Farms Salad Kit or Bowl")
        self.assertEqual(deals[1].brand, "Taylor Farms")

    def test_naturesweet_cherub_tomatoes_variety_expansion(self):
        item = FlyerItem(
            id=3004,
            flyer_id=8159694,
            name="NatureSweet Cherub or Golden Cherub Tomatoes",
            price=2.99,
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
        self.assertEqual(deals[0].canonical_name, "NatureSweet Cherub Tomatoes")
        self.assertEqual(deals[0].brand, "NatureSweet")
        self.assertEqual(deals[0].category, "Tomatoes")
        self.assertEqual(deals[1].canonical_name, "NatureSweet Golden Cherub Tomatoes")
        self.assertEqual(deals[1].brand, "NatureSweet")
        self.assertEqual(deals[1].category, "Tomatoes")

    def test_points_freebie_normalization(self):
        # 5-Point Freebie product title cleaning and normalization
        item = FlyerItem(
            id=4001,
            flyer_id=8159694,
            name="Bob Evans 18g Protein Macaroni & Cheese Refrigerated - 5-POINT FREEBIE, Save at least $5.79",
            price=5.79,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Bob Evans",
            page_number=5,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Bob Evans 18g Protein Macaroni & Cheese Refrigerated")
        self.assertEqual(deals[0].brand, "Bob Evans")
        self.assertEqual(deals[0].promo_detail, "FREE with 5 CHOICE points (Save $5.79)")

    def test_poultry_trio_with_whole_chicken(self):
        item = FlyerItem(
            id=5001,
            flyer_id=8180797,
            name="Signature SELECT® Fresh Whole Chickens, Thighs or Drumsticks",
            price=0.97,
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
        self.assertEqual(len(deals), 3)

        self.assertEqual(deals[0].canonical_name, "Whole Chickens")
        self.assertEqual(deals[0].brand, "Signature SELECT")
        self.assertEqual(deals[0].category, "Whole Chicken")
        self.assertEqual(deals[0].unit_size, 1.0)
        self.assertEqual(deals[0].unit_type, "lb")
        self.assertEqual(deals[0].unit_price, 0.97)

        self.assertEqual(deals[1].canonical_name, "Bone-In Chicken Thighs")
        self.assertEqual(deals[1].brand, "Signature SELECT")
        self.assertEqual(deals[1].category, "Bone-In Chicken Thighs")
        self.assertEqual(deals[1].unit_size, 1.0)
        self.assertEqual(deals[1].unit_type, "lb")
        self.assertEqual(deals[1].unit_price, 0.97)

        self.assertEqual(deals[2].canonical_name, "Chicken Drumsticks")
        self.assertEqual(deals[2].brand, "Signature SELECT")
        self.assertEqual(deals[2].category, "Chicken Drumsticks")
        self.assertEqual(deals[2].unit_size, 1.0)
        self.assertEqual(deals[2].unit_type, "lb")
        self.assertEqual(deals[2].unit_price, 0.97)

    def test_fresh_atlantic_salmon_portions(self):
        item = FlyerItem(
            id=5002,
            flyer_id=8180797,
            name="Fresh Atlantic Salmon Portions",
            price=4.99,
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
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Fresh Atlantic Salmon Portions 5 oz Skinless")
        self.assertEqual(deals[0].unit_size, 5.0)
        self.assertEqual(deals[0].unit_type, "oz")
        self.assertAlmostEqual(deals[0].unit_price, round(4.99 / 5.0, 4))
        self.assertEqual(deals[0].category, "Salmon")

    def test_wine_josh_cellars_normalization(self):
        item = FlyerItem(
            id=5003,
            flyer_id=8189860,
            name="Kendall-Jackson VR Chardonnay or Josh",
            price=9.89,
            original_price=12.49,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)

        self.assertEqual(deals[0].canonical_name, "Kendall-Jackson VR Chardonnay")
        self.assertEqual(deals[0].brand, "Kendall-Jackson")
        self.assertEqual(deals[0].category, "Wine")
        self.assertEqual(deals[0].advertised_price, 9.89)

        self.assertEqual(deals[1].canonical_name, "Josh Cellars Wine")
        self.assertEqual(deals[1].brand, "Josh Cellars")
        self.assertEqual(deals[1].category, "Wine")
        self.assertEqual(deals[1].advertised_price, 9.89)

    def test_five_for_five_mix_and_match_collage(self):
        item = FlyerItem(
            id=5004,
            flyer_id=8189860,
            name="Kraft, Maruchan, Michelina's, Idahoan, Bowl, Crest, Banquet, Snack Pack, Chef Boyardee, Ragu",
            price=5.0,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 10)
        for d in deals:
            self.assertEqual(d.advertised_price, 1.0)
            self.assertEqual(d.promo_type, "must_buy")
            self.assertEqual(d.promo_detail, "5 for $5.00 ($1.00 ea)")
            self.assertEqual(d.qualifying_qty, 5)

        names = [d.canonical_name for d in deals]
        self.assertIn("Kraft Macaroni & Cheese", names)
        self.assertIn("Maruchan Ramen Bowl", names)
        self.assertIn("Crest Toothpaste", names)
        self.assertIn("Ragu Pasta Sauce", names)

    def test_size_range_comma_preservation(self):
        item = FlyerItem(
            id=5005,
            flyer_id=8189860,
            name="Lay's, 4.75-6 oz., Baked 6.25-7.62 oz., Cheetos 7-10 oz., Smartfood Popcorn 5-10 oz. or Frito Lay Dip Bean Bag 8.5-9 oz.",
            price=1.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 5)
        names = [d.canonical_name for d in deals]
        self.assertEqual(names[0], "Lay's 4.75-6 oz")
        self.assertEqual(names[1], "Lay's Baked 6.25-7.62 oz")
        self.assertNotIn("4.75-6 oz", names)

    def test_produce_variety_noun_expansion(self):
        item = FlyerItem(
            id=5006,
            flyer_id=8189860,
            name="New Crop Pears Bartlett, Red, Bosc or Danjou",
            price=2.29,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=5,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 4)
        names = [d.canonical_name for d in deals]
        self.assertEqual(names[0], "New Crop Pears Bartlett")
        self.assertEqual(names[1], "New Crop Pears Red")
        self.assertEqual(names[2], "New Crop Pears Bosc")
        self.assertEqual(names[3], "New Crop Pears Danjou")

    def test_unit_alternative_brand_expansion(self):
        item = FlyerItem(
            id=5007,
            flyer_id=8189860,
            name="Oxiclean 3 lb. or 24 ct., Arm & Hammer Laundry Detergent 75-110 oz. or Power Paks 32-42 ct.",
            price=5.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        names = [d.canonical_name for d in deals]
        self.assertIn("Oxiclean 3 lb", names)
        self.assertIn("Oxiclean 24 ct", names)
        self.assertNotIn("24 ct", names)

    def test_short_token_soda_split(self):
        item = FlyerItem(
            id=5008,
            flyer_id=8189860,
            name="Crush, Mug or Starry",
            price=7.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=1,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        names = [d.canonical_name for d in deals]
        self.assertEqual(len(deals), 3)
        self.assertEqual(names, ["Crush", "Mug", "Starry"])

    def test_apples_multi_word_variety_expansion(self):
        item = FlyerItem(
            id=5009,
            flyer_id=8189860,
            name="O Organics Apples Gala, Granny Smith or Fuji",
            price=4.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=5,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)
        names = [d.canonical_name for d in deals]
        self.assertEqual(names[0], "O Organics Apples Gala")
        self.assertEqual(names[1], "O Organics Apples Granny Smith")
        self.assertEqual(names[2], "O Organics Apples Fuji")

    def test_coordinated_prefix_adjective_noun(self):
        item_mushrooms = FlyerItem(
            id=5010,
            flyer_id=8189860,
            name="Sliced or Whole White Mushrooms",
            price=2.79,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=5,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals_mushrooms = self.normalizer.disaggregate_and_normalize(item_mushrooms)
        names_m = [d.canonical_name for d in deals_mushrooms]
        self.assertEqual(names_m, ["Sliced White Mushrooms", "Whole White Mushrooms"])

        item_parfaits = FlyerItem(
            id=5011,
            flyer_id=8189860,
            name="Yogurt or Oatmeal parfaits",
            price=3.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=5,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals_parfaits = self.normalizer.disaggregate_and_normalize(item_parfaits)
        names_p = [d.canonical_name for d in deals_parfaits]
        self.assertEqual(names_p, ["Yogurt parfaits", "Oatmeal parfaits"])

    def test_stray_number_and_count_noise_discarded(self):
        item = FlyerItem(
            id=5012,
            flyer_id=8189860,
            name="Blue Bell Ice Cream Half Gallon, Ice Cream Sandwiches 12 ct, 3.25 or 16 ct. minis or Cups 12 ct, 3 oz.",
            price=6.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        names = [d.canonical_name for d in deals]
        self.assertNotIn("3.25", names)
        self.assertNotIn("16 ct. minis", names)
        self.assertEqual(names, ["Blue Bell Ice Cream Half Gallon", "Ice Cream Sandwiches 12 ct", "Cups 12 ct 3 oz"])

    def test_standalone_wine_brand_categorization(self):
        item = FlyerItem(
            id=5013,
            flyer_id=8189860,
            name="Menage A Trois or Bogle",
            price=8.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].brand, "Menage A Trois")
        self.assertEqual(deals[0].category, "Wine")
        self.assertEqual(deals[1].brand, "Bogle")
        self.assertEqual(deals[1].category, "Wine")

    def test_our_brand_sugar_right_distribution(self):
        item = FlyerItem(
            id=5014,
            flyer_id=1195674,
            name="Our Brand Confectioners' or Brown Sugar - $2.39",
            price=2.39,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=6,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].canonical_name, "Our Brand Confectioners' Sugar")
        self.assertEqual(deals[0].brand, "Our Brand")
        self.assertEqual(deals[1].canonical_name, "Our Brand Brown Sugar")
        self.assertEqual(deals[1].brand, "Our Brand")

    def test_duncan_hines_baking_mix_and_frosting_brand_distribution(self):
        item = FlyerItem(
            id=5015,
            flyer_id=1195674,
            name="Duncan Hines Cake or Brownie Mix or Frosting - 2/ $3.00",
            price=1.50,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=6,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 3)
        self.assertEqual(deals[0].canonical_name, "Duncan Hines Cake")
        self.assertEqual(deals[0].brand, "Duncan Hines")
        self.assertEqual(deals[1].canonical_name, "Duncan Hines Brownie Mix")
        self.assertEqual(deals[1].brand, "Duncan Hines")
        self.assertEqual(deals[2].canonical_name, "Duncan Hines Frosting")
        self.assertEqual(deals[2].brand, "Duncan Hines")


    def test_lucerne_eggs_standardization(self):
        # 1. Eggs without "Large" modifier (18 ct)
        item1 = FlyerItem(
            id=101,
            flyer_id=1,
            name="Philadelphia Cream Cheese 8 oz, Lucerne Eggs 18 ct, Pillsbury Dough 8-16.3 oz",
            price=1.97,
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
        deals1 = self.normalizer.disaggregate_and_normalize(item1)
        egg_deal1 = next(d for d in deals1 if "egg" in d.canonical_name.lower())
        self.assertEqual(egg_deal1.canonical_name, "Lucerne Large Eggs 18 ct")
        self.assertEqual(egg_deal1.brand, "Lucerne")
        self.assertEqual(egg_deal1.unit_size, 18.0)
        self.assertEqual(egg_deal1.unit_type, "ct")
        self.assertAlmostEqual(egg_deal1.unit_price, 0.1094, places=4)

        # 2. Eggs without count specified defaults to 12 ct
        item2 = FlyerItem(
            id=102,
            flyer_id=2,
            name="Lucerne Large Eggs",
            price=0.97,
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
        deals2 = self.normalizer.disaggregate_and_normalize(item2)
        self.assertEqual(len(deals2), 1)
        self.assertEqual(deals2[0].canonical_name, "Lucerne Large Eggs 12 ct")
        self.assertEqual(deals2[0].brand, "Lucerne")
        self.assertEqual(deals2[0].unit_size, 12.0)
        self.assertEqual(deals2[0].unit_type, "ct")
        self.assertAlmostEqual(deals2[0].unit_price, 0.0808, places=4)

        # 3. Bulk 60 count standardization
        item3 = FlyerItem(
            id=103,
            flyer_id=3,
            name="Lucerne Large Eggs 60 Count",
            price=5.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Lucerne",
            page_number=1,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals3 = self.normalizer.disaggregate_and_normalize(item3)
        self.assertEqual(deals3[0].canonical_name, "Lucerne Large Eggs 60 ct")
        self.assertEqual(deals3[0].unit_size, 60.0)
        self.assertEqual(deals3[0].unit_type, "ct")

    def test_generalized_egg_standardization_other_brands(self):
        # Vital Farms eggs without count defaults to 12 ct
        item1 = FlyerItem(
            id=201,
            flyer_id=1,
            name="Vital Farms Pasture Raised Large Eggs",
            price=5.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Vital Farms",
            page_number=1,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals1 = self.normalizer.disaggregate_and_normalize(item1)
        self.assertEqual(deals1[0].canonical_name, "Vital Farms Pasture Raised Large Eggs 12 ct")
        self.assertEqual(deals1[0].unit_size, 12.0)
        self.assertEqual(deals1[0].unit_type, "ct")
        self.assertAlmostEqual(deals1[0].unit_price, round(5.49 / 12.0, 4), places=4)

        # Eggland's Best Large Eggs 24 Count standardizes unit suffix to ct
        item2 = FlyerItem(
            id=202,
            flyer_id=2,
            name="Eggland's Best Large Eggs 24 Count",
            price=6.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Eggland's Best",
            page_number=1,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals2 = self.normalizer.disaggregate_and_normalize(item2)
        self.assertEqual(deals2[0].canonical_name, "Eggland's Best Large Eggs 24 ct")
        self.assertEqual(deals2[0].unit_size, 24.0)
        self.assertEqual(deals2[0].unit_type, "ct")

        # Non-shell egg products (e.g., egg bites, noodles, omelets) are not converted
        item3 = FlyerItem(
            id=203,
            flyer_id=3,
            name="Eggland's Best Three Cheese Omelets 7.8 oz",
            price=3.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Eggland's Best",
            page_number=1,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals3 = self.normalizer.disaggregate_and_normalize(item3)
        self.assertEqual(deals3[0].canonical_name, "Eggland's Best Three Cheese Omelets 7.8 oz")
        self.assertEqual(deals3[0].unit_size, 7.8)
        self.assertEqual(deals3[0].unit_type, "oz")

    def test_universal_unit_suffix_standardization(self):
        from deals_tracker.src.normalizer.cleaner import standardize_unit_tokens
        self.assertEqual(standardize_unit_tokens("Product 60 Count"), "Product 60 ct")
        self.assertEqual(standardize_unit_tokens("Product 24 count"), "Product 24 ct")
        self.assertEqual(standardize_unit_tokens("Product 16 Ounces"), "Product 16 oz")
        self.assertEqual(standardize_unit_tokens("Product 2 Pounds"), "Product 2 lb")
        self.assertEqual(standardize_unit_tokens("Product 1 Gallon"), "Product 1 gal")
        self.assertEqual(standardize_unit_tokens("Product 6-8 Ounces"), "Product 6-8 oz")

    def test_multibuy_bundle_price_normalization(self):
        item = FlyerItem(
            id=1044979398,
            flyer_id=1195672,
            name="Turkey Hill Ice Cream - 2/ $6.00",
            price=6.0,
            original_price=None,
            pre_price_text="2/ $6.00",
            post_price_text=None,
            description=None,
            brand="Turkey Hill",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].canonical_name, "Turkey Hill Ice Cream")
        self.assertEqual(deals[0].advertised_price, 3.0)
        self.assertEqual(deals[0].promo_type, "must_buy")
        self.assertEqual(deals[0].promo_detail, "2 FOR $6.00")
        self.assertEqual(deals[0].qualifying_qty, 2)

    def test_pork_cut_standardization(self):
        item = FlyerItem(
            id=9991,
            flyer_id=8197163,
            name="Signature SELECT® Fresh Boneless Skinless Chicken Breasts or Value Pack Pork Loin Chops",
            price=2.77,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Signature SELECT",
            page_number=3,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].canonical_name, "Boneless Skinless Chicken Breasts")
        self.assertEqual(deals[1].canonical_name, "Pork Loin Chops")
        self.assertIsNone(deals[1].brand)
        self.assertEqual(deals[1].category, "Pork Chops")
        self.assertEqual(deals[1].unit_size, 1.0)
        self.assertEqual(deals[1].unit_type, "lb")

    def test_national_brand_store_brand_isolation(self):
        # 1. Plain Swanson Broth with store brand passed in item.brand
        item1 = FlyerItem(
            id=1049095426,
            flyer_id=8197163,
            name="Swanson Broth",
            price=2.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Our Brand",
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals1 = self.normalizer.disaggregate_and_normalize(item1)
        self.assertEqual(len(deals1), 1)
        self.assertEqual(deals1[0].canonical_name, "Swanson Broth")
        self.assertEqual(deals1[0].brand, "Swanson")

        # 2. Contaminated 'Our Brand Swanson Broth' string
        item2 = FlyerItem(
            id=1049095427,
            flyer_id=8197163,
            name="Our Brand Swanson Broth",
            price=2.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand="Our Brand",
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals2 = self.normalizer.disaggregate_and_normalize(item2)
        self.assertEqual(len(deals2), 1)
        self.assertEqual(deals2[0].canonical_name, "Swanson Broth")
        self.assertEqual(deals2[0].brand, "Swanson")

        # 3. Compound promo containing both store brand and national brand
        item3 = FlyerItem(
            id=1044979822,
            flyer_id=1195672,
            name="Our Brand Rice & Pasta Blend or Swanson Broth - 5/ $5.00",
            price=5.0,
            original_price=None,
            pre_price_text="5/ $5.00",
            post_price_text=None,
            description=None,
            brand="Our Brand",
            page_number=1,
            is_front_page=True,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals3 = self.normalizer.disaggregate_and_normalize(item3)
        self.assertEqual(len(deals3), 2)
        self.assertEqual(deals3[0].canonical_name, "Our Brand Rice & Pasta Blend")
        self.assertEqual(deals3[0].brand, "Our Brand")
        self.assertEqual(deals3[1].canonical_name, "Swanson Broth")
        self.assertEqual(deals3[1].brand, "Swanson")

        # 4. Green Giant must match Green Giant, not store brand Giant
        item4 = FlyerItem(
            id=9992,
            flyer_id=8197163,
            name="Green Giant Simply Steam Vegetables",
            price=1.99,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description=None,
            brand=None,
            page_number=2,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals4 = self.normalizer.disaggregate_and_normalize(item4)
        self.assertEqual(len(deals4), 1)
        self.assertEqual(deals4[0].canonical_name, "Green Giant Simply Steam Vegetables")
        self.assertEqual(deals4[0].brand, "Green Giant")

    def test_is_alcohol_deal(self):
        from src.normalizer.categories import is_alcohol_deal

        # Positive alcohol deals by category
        self.assertTrue(is_alcohol_deal({"category": "Wine", "canonical_name": "Red Blend"}))
        self.assertTrue(is_alcohol_deal({"category": "Beer", "canonical_name": "Craft Ale"}))

        # Positive alcohol deals by brand
        self.assertTrue(is_alcohol_deal({"canonical_name": "LaMarca Prosecco 750 ml", "brand": "LaMarca"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Kim Crawford Sauvignon Blanc", "brand": "Kim Crawford"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Bud, Miller or Coors 24 pk", "brand": "Budweiser"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Michelob Ultra 12 pk", "brand": "Michelob"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Shiner Bock Beer", "brand": "Shiner"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "White Claw Variety Pack", "brand": "White Claw"}))

        # Positive alcohol deals by keywords
        self.assertTrue(is_alcohol_deal({"canonical_name": "Josh Cellars Cabernet Sauvignon", "brand": "Josh Cellars"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Mionetto Prosecco Rose", "brand": "Mionetto"}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Chardonnay White Wine 750 ml", "brand": None}))
        self.assertTrue(is_alcohol_deal({"canonical_name": "Local Craft IPA 6 pk", "brand": None}))

        # Negative non-alcohol items / exclusions
        self.assertFalse(is_alcohol_deal({"canonical_name": "Fresh Made Cupcakes 6 ct", "brand": "Bakery"}))
        self.assertFalse(is_alcohol_deal({"canonical_name": "Wicked Rose Bouquet", "brand": "Floral"}))
        self.assertFalse(is_alcohol_deal({"canonical_name": "Pompeian Red Wine Vinegar 16 oz", "brand": "Pompeian"}))
        self.assertFalse(is_alcohol_deal({"canonical_name": "Canada Dry Ginger Ale 12 pk", "brand": "Canada Dry"}))
        self.assertFalse(is_alcohol_deal({"canonical_name": "Sweet Baby Ray's Honey Bourbon BBQ Sauce", "brand": "Sweet Baby Ray's"}))
        self.assertFalse(is_alcohol_deal({"canonical_name": "Boneless Skinless Chicken Breasts", "brand": "Signature SELECT"}))
        self.assertFalse(is_alcohol_deal({"canonical_name": "Lucerne Large Eggs 12 ct", "brand": "Lucerne"}))

    def test_distribute_head_noun_splits(self):
        from src.normalizer.expander import distribute_head_noun_splits

        # 1. Bare brands sharing a head noun
        splits1 = ["CLIF", "LUNA Bars"]
        self.assertEqual(distribute_head_noun_splits(splits1), ["CLIF Bars", "LUNA Bars"])

        splits2 = ["Bud", "Miller", "Coors Beer"]
        self.assertEqual(distribute_head_noun_splits(splits2), ["Bud Beer", "Miller Beer", "Coors Beer"])

        # 2. Multi-item with size suffix
        splits3 = ["CLIF", "LUNA", "Builders Bars 1.69-2.40 oz"]
        self.assertEqual(
            distribute_head_noun_splits(splits3),
            ["CLIF Bars 1.69-2.40 oz", "LUNA Bars 1.69-2.40 oz", "Builders Bars 1.69-2.40 oz"],
        )

        # 3. Both items already have head nouns
        splits4 = ["Campbell's Soup", "Progresso Soup"]
        self.assertEqual(distribute_head_noun_splits(splits4), ["Campbell's Soup", "Progresso Soup"])

    def test_basket_coupon_normalization(self):
        """Store-wide basket coupons (e.g. $20 off $100 with for U Digital Coupon)
        must NOT be normalized as a fake $20 item named 'Exclusive'."""
        item = FlyerItem(
            id=1049095295,
            flyer_id=8197163,
            name="Exclusive Digital Coupon for U",
            price=None,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description="$20 OFF or $100 or more with digital coupon",
            brand=None,
            page_number=3,
            is_front_page=True,
            cutout_image_url="http://example.com/coupon.jpg",
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        deal = deals[0]
        self.assertEqual(deal.canonical_name, "Exclusive Digital Coupon - $20 off $100")
        self.assertIsNone(deal.advertised_price)
        self.assertEqual(deal.promo_type, "basket_coupon")
        self.assertEqual(deal.coupon_discount, 20.0)
        self.assertEqual(deal.base_price, 100.0)
        self.assertIn("SAVE $20.00 ON $100.00+", deal.promo_detail)

    def test_starbucks_pairing_combo(self):
        """In-store Starbucks drink + food pairing combos must not be split into
        separate fake $9 items like 'lunch sandwich', 'wrap', 'egg bites', or 'pocket'."""
        item = FlyerItem(
            id=1049095558,
            flyer_id=8197163,
            name="Any grande handcrafted drink*, breakfast sandwich, lunch sandwich, wrap, egg bites or pocket",
            price=9.0,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description="At Selected Stores",
            brand=None,
            page_number=5,
            is_front_page=False,
            cutout_image_url="http://example.com/sbux.jpg",
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        self.assertEqual(len(deals), 1)
        deal = deals[0]
        self.assertEqual(deal.canonical_name, "Starbucks Grande Drink & Breakfast or Lunch Food Pairing")
        self.assertEqual(deal.brand, "Starbucks")
        self.assertEqual(deal.advertised_price, 9.0)
        self.assertEqual(deal.promo_type, "bundle")
        self.assertEqual(deal.qualifying_qty, 2)

    def test_clean_unit_size_floating_point_precision(self):
        """Range size averaging (e.g. 8.4-14.8 oz) must not introduce floating point
        artifacts like 11.600000000000001 oz into canonical names."""
        item = FlyerItem(
            id=1049095311,
            flyer_id=8197163,
            name="Kellogg's® Eggo® Waffles, Pancakes or Toaster Sticks",
            price=3.49,
            original_price=None,
            pre_price_text=None,
            post_price_text=None,
            description="8.4-14.8 oz.",
            brand=None,
            page_number=4,
            is_front_page=False,
            cutout_image_url=None,
            clean_image_url=None,
        )
        deals = self.normalizer.disaggregate_and_normalize(item)
        for d in deals:
            self.assertNotIn("11.600000000000001", d.canonical_name)
            self.assertIn("11.6 oz", d.canonical_name)
            self.assertEqual(d.unit_size, 11.6)




if __name__ == "__main__":
    unittest.main()


