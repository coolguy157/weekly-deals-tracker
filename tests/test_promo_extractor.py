"""
test_promo_extractor.py
Unit tests for PromoExtractor regex parsing and effective unit price calculations.
"""

import unittest
from src.promo_extractor import PromoExtractor, PromoInfo


class TestPromoExtractor(unittest.TestCase):
    def test_bogo_patterns(self):
        # BUY 2 GET 2 FREE
        p1 = PromoExtractor.extract_promo("Doritos Tortilla Chips BUY 2 GET 2 FREE")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "bogo")
        self.assertEqual(p1.buy_qty, 2)
        self.assertEqual(p1.free_qty, 2)
        self.assertEqual(p1.qualifying_qty, 4)
        self.assertEqual(p1.promo_detail, "BUY 2 GET 2 FREE")

        # BUY 1 GET 1 FREE OF EQUAL OR LESSER VALUE
        p2 = PromoExtractor.extract_promo("Bakery Cookies BUY 1 GET 1 OF EQUAL OR LESSER VALUE FREE")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.promo_type, "bogo")
        self.assertEqual(p2.buy_qty, 1)
        self.assertEqual(p2.free_qty, 1)
        self.assertEqual(p2.qualifying_qty, 2)

        # Word numbers: BUY ONE GET ONE FREE
        p3 = PromoExtractor.extract_promo("Fresh Strawberries BUY ONE GET ONE FREE")
        self.assertIsNotNone(p3)
        self.assertEqual(p3.promo_type, "bogo")
        self.assertEqual(p3.buy_qty, 1)
        self.assertEqual(p3.free_qty, 1)

        # Buy 1 Get 1 50% Off
        p4 = PromoExtractor.extract_promo("Nature Valley Bars BUY 1 GET 1 50% OFF")
        self.assertIsNotNone(p4)
        self.assertEqual(p4.promo_type, "bogo")
        self.assertEqual(p4.buy_qty, 1)
        self.assertEqual(p4.free_qty, 1)
        self.assertEqual(p4.discount_pct, 50.0)

    def test_must_buy_patterns(self):
        # MUST BUY 4 @ $2.49
        p1 = PromoExtractor.extract_promo("Dr Pepper 12 Pack MUST BUY 4 @ $2.49")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "must_buy")
        self.assertEqual(p1.qualifying_qty, 4)
        self.assertEqual(p1.stated_unit_price, 2.49)
        self.assertEqual(p1.promo_detail, "MUST BUY 4 @ $2.49")

        # WHEN YOU BUY 3 $1.99 EA
        p2 = PromoExtractor.extract_promo("Pepsi 2 Liter WHEN YOU BUY 3 $1.99 EA")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.promo_type, "must_buy")
        self.assertEqual(p2.qualifying_qty, 3)
        self.assertEqual(p2.stated_unit_price, 1.99)

        # 2 FOR $5
        p3 = PromoExtractor.extract_promo("Lay's Potato Chips 2 FOR $5")
        self.assertIsNotNone(p3)
        self.assertEqual(p3.promo_type, "must_buy")
        self.assertEqual(p3.qualifying_qty, 2)
        self.assertEqual(p3.stated_unit_price, 2.50)
        self.assertEqual(p3.stated_total_price, 5.00)

        # 3 FOR $10.00
        p4 = PromoExtractor.extract_promo("Coke 12 Pack 3 FOR $10.00")
        self.assertIsNotNone(p4)
        self.assertEqual(p4.promo_type, "must_buy")
        self.assertEqual(p4.qualifying_qty, 3)
        self.assertAlmostEqual(p4.stated_unit_price, 3.33, places=2)

    def test_digital_coupon_patterns(self):
        # WITH DIGITAL COUPON $1.99
        p1 = PromoExtractor.extract_promo("Lucerne Butter 16 oz WITH DIGITAL COUPON $1.99")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "digital_coupon")
        self.assertEqual(p1.coupon_price, 1.99)

        # SAVE $1.00 WITH DIGITAL COUPON
        p2 = PromoExtractor.extract_promo("Cheerios Cereal SAVE $1.00 WITH DIGITAL COUPON")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.promo_type, "digital_coupon")
        self.assertEqual(p2.coupon_discount, 1.00)

    def test_calculate_effective_price(self):
        # Doritos B2G2 Free @ Base $5.89 -> ($5.89 * 2) / 4 = $2.945 -> $2.95
        p_b2g2 = PromoInfo(promo_type="bogo", promo_detail="BUY 2 GET 2 FREE", buy_qty=2, free_qty=2, qualifying_qty=4)
        eff_b2g2 = PromoExtractor.calculate_effective_price(p_b2g2, base_price=5.89)
        self.assertEqual(eff_b2g2, 2.95)

        # B1G1 Free @ Base $4.99 -> ($4.99 * 1) / 2 = $2.495 -> $2.50
        p_b1g1 = PromoInfo(promo_type="bogo", promo_detail="BUY 1 GET 1 FREE", buy_qty=1, free_qty=1, qualifying_qty=2)
        eff_b1g1 = PromoExtractor.calculate_effective_price(p_b1g1, base_price=4.99)
        self.assertEqual(eff_b1g1, 2.50)

        # B1G1 50% Off @ Base $6.00 -> ($6.00 + $3.00) / 2 = $4.50
        p_bogo_50 = PromoInfo(promo_type="bogo", promo_detail="BUY 1 GET 1 50% OFF", buy_qty=1, free_qty=1, discount_pct=50.0, qualifying_qty=2)
        eff_50 = PromoExtractor.calculate_effective_price(p_bogo_50, base_price=6.00)
        self.assertEqual(eff_50, 4.50)

        # Must buy unit price
        p_mb = PromoInfo(promo_type="must_buy", promo_detail="MUST BUY 4 @ $2.49", qualifying_qty=4, stated_unit_price=2.49)
        eff_mb = PromoExtractor.calculate_effective_price(p_mb)
        self.assertEqual(eff_mb, 2.49)

        # 2 FOR $5
        p_2for5 = PromoInfo(promo_type="must_buy", promo_detail="2 FOR $5.00", qualifying_qty=2, stated_unit_price=2.50, stated_total_price=5.00)
        eff_2for5 = PromoExtractor.calculate_effective_price(p_2for5)
        self.assertEqual(eff_2for5, 2.50)

        # Digital Coupon discount: Base $3.99 - $1.00 = $2.99
        p_coup = PromoInfo(promo_type="digital_coupon", promo_detail="SAVE $1.00", coupon_discount=1.00)
        eff_coup = PromoExtractor.calculate_effective_price(p_coup, base_price=3.99)
        self.assertEqual(eff_coup, 2.99)


    def test_points_patterns(self):
        # Free with 75 CHOICE points
        p1 = PromoExtractor.extract_promo("Our Brand Long Grain Rice FREE when you redeem 75 CHOICE points SAVE UP TO $1.89")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "points_redemption")
        self.assertEqual(p1.points_cost, 75)
        self.assertEqual(p1.points_saved_val, 1.89)
        self.assertEqual(PromoExtractor.calculate_effective_price(p1), 0.0)

        # 5-Point Freebie (Hyphenated, "Save at least")
        p_bob = PromoExtractor.extract_promo("Bob Evans 18g Protein Macaroni & Cheese Refrigerated - 5-POINT FREEBIE, Save at least $5.79")
        self.assertIsNotNone(p_bob)
        self.assertEqual(p_bob.promo_type, "points_redemption")
        self.assertEqual(p_bob.points_cost, 5)
        self.assertEqual(p_bob.points_saved_val, 5.79)
        self.assertEqual(PromoExtractor.calculate_effective_price(p_bob), 0.0)

        # 5 Point Freebie (Space separated, "Save up to")
        p_space = PromoExtractor.extract_promo("Barilla Pasta 5 POINT FREEBIE SAVE UP TO $2.49")
        self.assertIsNotNone(p_space)
        self.assertEqual(p_space.promo_type, "points_redemption")
        self.assertEqual(p_space.points_cost, 5)
        self.assertEqual(p_space.points_saved_val, 2.49)
        self.assertEqual(PromoExtractor.calculate_effective_price(p_space), 0.0)

        # 75 CHOICE Points Dressing
        p_dress = PromoExtractor.extract_promo("Our Brand Blue Cheese Dressing - FREE Our Brand Dressing when you redeem 75 CHOICE points, SAVE up to $2.00")
        self.assertIsNotNone(p_dress)
        self.assertEqual(p_dress.promo_type, "points_redemption")
        self.assertEqual(p_dress.points_cost, 75)
        self.assertEqual(p_dress.points_saved_val, 2.00)

        # 300 CHOICE Points when you spend $20
        p2 = PromoExtractor.extract_promo("Purina Tidy Cats 300 CHOICE POINTS When you spend $20 on participating products", point_value=0.0274)
        self.assertIsNotNone(p2)
        self.assertEqual(p2.promo_type, "points_bonus")
        self.assertEqual(p2.points_bonus, 300)
        self.assertEqual(p2.spend_threshold, 20.00)
        self.assertAlmostEqual(p2.est_reward_val, 8.22, places=2)
        self.assertAlmostEqual(p2.est_net_price, 11.78, places=2)

        # 10X Points Multiplier
        p3 = PromoExtractor.extract_promo("Gift Cards EARN 10X CHOICE POINTS", point_value=0.0274)
        self.assertIsNotNone(p3)
        self.assertEqual(p3.promo_type, "points_bonus")
        self.assertEqual(p3.points_multiplier, 10.0)

    def test_spend_save_patterns(self):
        # Save $5 when you spend $20
        p1 = PromoExtractor.extract_promo("Vitamins SAVE $5 When you spend $20 on participating products")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "spend_save")
        self.assertEqual(p1.coupon_discount, 5.0)
        self.assertEqual(p1.spend_threshold, 20.0)
        self.assertEqual(p1.est_net_price, 15.0)

    def test_percent_off_patterns(self):
        # 25% Off
        p1 = PromoExtractor.extract_promo("Our Brand Fish Portions or Fillets 25% Off")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "percent_off")
        self.assertEqual(p1.discount_pct, 25.0)
        # 25% off regular $7.99 -> $5.99
        eff = PromoExtractor.calculate_effective_price(p1, base_price=7.99)
        self.assertEqual(eff, 5.99)

    def test_bullet_and_special_bogo_patterns(self):
        # Bullet separators: BUY 2 • GET 1 FREE! of equal or lesser value
        p1 = PromoExtractor.extract_promo("Sweet Strawberries BUY 2 • GET 1 FREE! of equal or lesser value")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "bogo")
        self.assertEqual(p1.buy_qty, 2)
        self.assertEqual(p1.free_qty, 1)

        # Katakana middle dot: BUY 1・GET 1 FREE! must buy like brand
        p2 = PromoExtractor.extract_promo("General Mills Cereal BUY 1・GET 1 FREE! of equal or lesser value must buy like brand")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.promo_type, "bogo")
        self.assertEqual(p2.buy_qty, 1)
        self.assertEqual(p2.free_qty, 1)

        # BUY 5 GET 1 FREE
        p3 = PromoExtractor.extract_promo("Hass Avocados BUY 5 • GET 1 FREE! of equal or lesser value")
        self.assertIsNotNone(p3)
        self.assertEqual(p3.promo_type, "bogo")
        self.assertEqual(p3.buy_qty, 5)
        self.assertEqual(p3.free_qty, 1)
        self.assertEqual(p3.qualifying_qty, 6)

    def test_dollar_off_patterns(self):
        # $1.00 Off
        p1 = PromoExtractor.extract_promo("Garnier Fructis Hair Care $1.00 Off")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "dollar_off")
        self.assertEqual(p1.coupon_discount, 1.00)
        eff = PromoExtractor.calculate_effective_price(p1, base_price=4.99)
        self.assertEqual(eff, 3.99)

    def test_meal_deal_patterns(self):
        # Weekly Meal Deal: buy this roast get these free potatoes, seasoning, broth (save at least $8.27)
        sales_text = "buy this Our Brand Boneless Beef Chuck Roast get these FREE* Our Brand Mini Potatoes SAVE at least $8.27* with this week's meal deal"
        p1 = PromoExtractor.extract_promo(sales_text)
        self.assertIsNotNone(p1)
        self.assertEqual(p1.promo_type, "meal_deal")
        self.assertIn("Weekly Meal Deal", p1.promo_detail)
        self.assertIn("Beef Chuck Roast", p1.promo_detail)

    def test_dynamic_point_value_calculation_ignores_5_point_freebies(self):
        items = [
            # Standard points redemption: 75 pts, save $2.25 -> 3.00¢/pt
            {"raw_title": "Rice FREE when you redeem 75 CHOICE points SAVE UP TO $2.25", "promo_detail": ""},
            # Standard points redemption: 100 pts, save $2.80 -> 2.80¢/pt
            {"raw_title": "Oats FREE when you redeem 100 CHOICE points SAVE UP TO $2.80", "promo_detail": ""},
            # 5-point freebie: 5 pts, save $2.50 -> 50.0¢/pt (MUST BE IGNORED)
            {"raw_title": "Pasta 5-POINT FREEBIE SAVE UP TO $2.50", "promo_detail": ""},
        ]
        # Expected dynamic valuation is (0.0300 + 0.0280) / 2 = 0.0290, NOT inflated by the 5-point freebie
        dyn_val = PromoExtractor.calculate_dynamic_point_value(items)
        self.assertAlmostEqual(dyn_val, 0.0290, places=4)


if __name__ == "__main__":
    unittest.main()


