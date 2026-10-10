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
    if deal.get("promo_type") == "meal_deal" or "meal deal" in promo or "get these free" in promo:
        return f"meal_deal_p{page}"

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
        return "Weekly Meal Deal"

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


def group_all_deals(deals):
    groups_map = {}
    for d in deals:
        k = get_group_key(d)
        existing = groups_map.setdefault(k, [])
        if not any(it.get('name') == d.get('name') and abs((it.get('price') or 0) - (d.get('price') or 0)) < 0.01 for it in existing):
            existing.append(d)

    # Merge redundant meal deal sub-ads on the same page
    meal_deal_groups = {k: v for k, v in groups_map.items() if k.startswith("meal_deal_")}
    to_delete = []
    for k, items in groups_map.items():
        if k.startswith("meal_deal_"):
            continue
        for md_k, md_items in meal_deal_groups.items():
            match_count = sum(1 for it in items if any(m.get('name') == it.get('name') for m in md_items))
            if items and match_count >= min(3, len(items)) and (match_count / len(items)) >= 0.7:
                for it in items:
                    if not any(m.get('name') == it.get('name') for m in md_items):
                        md_items.append(it)
                to_delete.append(k)
                break

    for k in to_delete:
        del groups_map[k]

    return groups_map


def get_meal_deal_headline_price(items):
    # Headline price for a meal deal must be the anchor item (highest price qualifying purchase)
    if not items:
        return 0.0
    anchor = max(items, key=lambda x: x.get("price") or 0)
    return anchor.get("price") or 0.0


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
        self.assertEqual(keys[0], "meal_deal_p5")

        title = synthesize_group_title(meal_deal_items)
        self.assertEqual(title, "Weekly Meal Deal")
        self.assertNotIn("McCormick, Our Brand Selection", title)

    def test_meal_deal_anchor_pricing_and_sub_ad_merging(self):
        # Full meal deal set including ad_1044980904 (which Flipp published without promo_detail)
        all_ads_items = [
            # Group 1 from ad 1044980878
            {"deal_id": 101, "raw_deal_id": 10449808780, "name": "Our Brand Boneless Beef Chuck Roast", "price": 29.97, "page": 5, "promo_type": "meal_deal", "promo_detail": "meal deal"},
            {"deal_id": 102, "raw_deal_id": 10449808781, "name": "Our Brand Baby Carrots", "price": 1.29, "page": 5, "promo_type": "meal_deal", "promo_detail": "meal deal"},
            {"deal_id": 103, "raw_deal_id": 10449808782, "name": "McCormick Seasoning Mix", "price": 2.00, "page": 5, "promo_type": "meal_deal", "promo_detail": "meal deal"},
            # Group 2 from ad 1044980904 (published as standard without promo tag)
            {"deal_id": 201, "raw_deal_id": 10449809040, "ad_id": 1044980904, "name": "Our Brand Boneless Beef Chuck Roast", "price": 29.97, "page": 5, "promo_type": "standard", "promo_detail": ""},
            {"deal_id": 202, "raw_deal_id": 10449809041, "ad_id": 1044980904, "name": "Our Brand Baby Carrots", "price": 1.29, "page": 5, "promo_type": "standard", "promo_detail": ""},
            {"deal_id": 203, "raw_deal_id": 10449809042, "ad_id": 1044980904, "name": "McCormick Seasoning Mix", "price": 2.00, "page": 5, "promo_type": "standard", "promo_detail": ""},
        ]
        groups = group_all_deals(all_ads_items)
        # Should have collapsed ad_1044980904 into meal_deal_p5
        self.assertEqual(len(groups), 1)
        self.assertIn("meal_deal_p5", groups)
        self.assertNotIn("ad_1044980904", groups)

        # Headline price should be 29.97 (the roast), not 1.29 or a range
        headline_price = get_meal_deal_headline_price(groups["meal_deal_p5"])
        self.assertEqual(headline_price, 29.97)

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

