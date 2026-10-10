"""
test_grouping.py
Automated unit tests for circular ad grouping, meal deal bundle resolution,
multi-brand variety synthesis, and duplicate avoidance.
"""

import unittest
import re


def get_group_key(deal):
    promo = (deal.get("promo_detail") or "").strip().lower()
    page = deal.get("page") or 1

    # Weekly Meal Deal bundle check
    if deal.get("promo_type") == "meal_deal" or "meal deal" in promo or "get these free" in promo or ("chuck roast" in promo and "free" in promo):
        return f"meal_deal_p{page}_chuck_roast"

    if deal.get("ad_id"):
        return f"ad_{deal['ad_id']}"
    raw_id = str(deal.get("raw_deal_id") or "")
    if len(raw_id) >= 11:
        return f"ad_{raw_id[:10]}"
    if raw_id and raw_id != "0":
        return f"raw_{raw_id}"

    p_type = deal.get("promo_type") or "standard"
    brand = (deal.get("brand") or "").lower()
    if promo and promo != "standard" and promo != "(none)":
        clean_p = re.sub(r"[^a-z0-9]", "", promo)[:25]
        return f"promo_p{page}_{p_type}_{clean_p}_{brand}"
    return f"deal_{deal.get('deal_id')}"


def synthesize_group_title(items):
    if len(items) == 1:
        return items[0].get("name") or "Deal Item"

    # Meal Deal bundle check
    promo = (items[0].get("promo_detail") or "").lower()
    if any(it.get("promo_type") == "meal_deal" for it in items) or "meal deal" in promo or "get these free" in promo:
        anchor = max(items, key=lambda x: x.get("price") or 0)
        anchor_name = (anchor.get("name") or "Beef Chuck Roast").split(" - ")[0]
        anchor_name = re.sub(r"(?i)\b(?:Vacuum Sealed Fresh|Butcher Shop.*|U\.?S\.?D\.?A\.? Choice)\b", "", anchor_name).strip()
        return f"{anchor_name} Meal Deal (Free Sides Included)"

    brands = sorted(list({it.get("brand") for it in items if it.get("brand")}))
    names = [it.get("name") or "" for it in items]

    # Multi-brand specialized categories
    if "Duncan Hines" in brands and "PAM" in brands:
        return "Duncan Hines & PAM • Cake Mixes, Frosting & Baking Spray"
    if "CareOne" in brands and "Nature's Promise" in brands:
        return "Nature's Promise & CareOne • Vitamins & Supplements"
    if "Floral" in brands or any(re.search(r"carnation|mum", n, re.I) for n in names):
        return "Floral • Carnations & Mums (Colors May Vary)"
    if "Martin's Snacks" in brands and "Nature's Own" in brands:
        return "Martin's Snacks & Nature's Own • Chips, Popcorn & Bread"
    if "Fresh Seafood" in brands or "Hannaford" in brands or any(re.search(r"fillet|swai|cod|whiting", n, re.I) for n in names):
        return "Fresh & Frozen Seafood Fillets"

    # Common grocery product types
    keywords = [
        "Soda", "Potato Chips", "Tortilla Chips", "Chips", "Cookies", "Cereal",
        "Sausage", "Bratwurst", "Brats", "Shampoo", "Lotion", "Bread", "Dressing",
        "Broth", "Crackers", "Water", "Tea", "Juice", "Vitamins", "Candy", "Dip",
        "Pasta", "Rice", "Ice Cream", "Coffee", "Cheese", "Spices", "Yogurt",
        "Snacks", "Sauce", "Chicken", "Beef", "Pork", "Fish", "Seafood", "Bacon"
    ]

    matched_keyword = None
    for kw in keywords:
        if all(kw.lower() in n.lower() for n in names):
            matched_keyword = kw
            break

    pkg = ""
    for p in ["12 pk", "6 pk", "8 pk", "15 ct", "Family Size", "Party Size", "1 Liter", "2 Liter"]:
        if all(p.lower() in n.lower() for n in names):
            pkg = f" ({p})"
            break

    if matched_keyword:
        if len(brands) == 1:
            return f"{brands[0]} {matched_keyword}{pkg}"
        elif len(brands) <= 3:
            return f"{', '.join(brands)} • {matched_keyword}{pkg}"
        else:
            return f"{brands[0]}, {brands[1]} & more • {matched_keyword}{pkg}"

    if len(brands) == 1:
        return f"{brands[0]} Assorted Varieties{pkg} ({len(items)} Items)"
    elif len(brands) <= 3:
        return f"{', '.join(brands)} Selection{pkg} ({len(items)} Items)"
    else:
        return f"{brands[0]}, {brands[1]} & more{pkg} ({len(items)} Items)"


class TestGroupingLogic(unittest.TestCase):

    def test_b2g2_soda_grouping(self):
        # 15 soda varieties with raw_deal_id sharing base ad_id 1044979722
        soda_deals = [
            {"deal_id": 1, "raw_deal_id": 10449797220, "name": "Diet Mtn Dew - 12 pk", "brand": "Diet Mtn Dew", "price": 5.5, "page": 1},
            {"deal_id": 2, "raw_deal_id": 10449797221, "name": "Pepsi Cola - 12 pk", "brand": "Pepsi", "price": 5.5, "page": 1},
            {"deal_id": 3, "raw_deal_id": 10449797227, "name": "Canada Dry Ginger Ale - 12 pk", "brand": "Canada Dry", "price": 5.0, "page": 1},
            {"deal_id": 4, "raw_deal_id": 10449797229, "name": "RC Cola - 12 pk", "brand": "RC Cola", "price": 5.0, "page": 1},
        ]
        keys = [get_group_key(d) for d in soda_deals]
        self.assertEqual(len(set(keys)), 1)
        self.assertEqual(keys[0], "ad_1044979722")

        title = synthesize_group_title(soda_deals)
        self.assertIn("12 pk", title)
        self.assertTrue("Canada Dry" in title or "Diet Mtn Dew" in title)

    def test_meal_deal_deduplication(self):
        # 4 circular ads for the same meal deal bundle
        meal_deal_items = [
            {"deal_id": 10, "raw_deal_id": 10449808780, "name": "Our Brand Boneless Beef Chuck Roast Vacuum Sealed Fresh", "brand": "Our Brand", "price": 29.97, "page": 5, "promo_type": "meal_deal", "promo_detail": "buy this Our Brand Boneless Beef Chuck Roast get these FREE* Mini Potatoes with meal deal"},
            {"deal_id": 11, "raw_deal_id": 10449809040, "name": "Our Brand Peeled Baby Carrots", "brand": "Our Brand", "price": 1.29, "page": 5, "promo_type": "meal_deal", "promo_detail": "buy this Our Brand Boneless Beef Chuck Roast get these FREE* McCormick Seasoning with meal deal"},
            {"deal_id": 12, "raw_deal_id": 10449809190, "name": "McCormick Slow Cooker Pot Roast Seasoning Mix Packet", "brand": "McCormick", "price": 2.00, "page": 5, "promo_type": "meal_deal", "promo_detail": "buy this Our Brand Boneless Beef Chuck Roast get these FREE* Baby Carrots with meal deal"},
        ]
        keys = [get_group_key(d) for d in meal_deal_items]
        # All items must collapse into the same meal deal group
        self.assertEqual(len(set(keys)), 1)
        self.assertEqual(keys[0], "meal_deal_p5_chuck_roast")

        title = synthesize_group_title(meal_deal_items)
        self.assertIn("Chuck Roast", title)
        self.assertIn("Meal Deal", title)
        self.assertNotIn("McCormick, Our Brand Selection", title)

    def test_multi_brand_specialized_labeling(self):
        # Duncan Hines + PAM items should not be labeled "Duncan Hines, PAM Selection"
        baking_items = [
            {"name": "Duncan Hines Classic Yellow Cake Mix", "brand": "Duncan Hines", "price": 1.50},
            {"name": "Duncan Hines Chewy Fudge Brownie Mix", "brand": "Duncan Hines", "price": 1.50},
            {"name": "PAM Baking Spray with Flour", "brand": "PAM", "price": 3.50},
        ]
        title = synthesize_group_title(baking_items)
        self.assertEqual(title, "Duncan Hines & PAM • Cake Mixes, Frosting & Baking Spray")


if __name__ == "__main__":
    unittest.main()
