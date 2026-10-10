"""
categories.py
Commodity category taxonomy patterns and classification heuristics.
"""

from typing import Optional, List, Tuple, Dict
import re

COMMODITY_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Dairy / Cheese
    (re.compile(r"\bcream\s+cheese\b", re.IGNORECASE), "Cream Cheese"),
    (re.compile(r"\bshredded\s+cheese\b", re.IGNORECASE), "Shredded Cheese"),
    (re.compile(r"\bsliced\s+cheese\b", re.IGNORECASE), "Sliced Cheese"),
    (re.compile(r"\b(?:chunk|block)\s+cheese\b", re.IGNORECASE), "Chunk Cheese"),
    (re.compile(r"\bstring\s+cheese\b", re.IGNORECASE), "String Cheese"),
    (re.compile(r"\bcheese\b", re.IGNORECASE), "Cheese"),
    (re.compile(r"\beggs?\b", re.IGNORECASE), "Eggs"),
    (re.compile(r"\bbutter\b", re.IGNORECASE), "Butter"),
    (re.compile(r"\bmilk\b", re.IGNORECASE), "Milk"),
    (re.compile(r"\byogurt\b", re.IGNORECASE), "Yogurt"),
    (re.compile(r"\bsour\s+cream\b", re.IGNORECASE), "Sour Cream"),
    (re.compile(r"\bice\s+cream\b", re.IGNORECASE), "Ice Cream"),
    # Meats & Poultry
    (re.compile(r"\bbacon\b", re.IGNORECASE), "Bacon"),
    (re.compile(r"\bsausage\b", re.IGNORECASE), "Sausage"),
    (re.compile(r"\bhot\s*dogs?\b", re.IGNORECASE), "Hot Dogs"),
    (re.compile(r"\bchicken\s+breasts?\b", re.IGNORECASE), "Chicken Breasts"),
    (re.compile(r"\bchicken\s+thighs?\b", re.IGNORECASE), "Chicken Thighs"),
    (re.compile(r"\bchicken\s+wings?\b", re.IGNORECASE), "Chicken Wings"),
    (re.compile(r"\bchicken\s+drumsticks?\b", re.IGNORECASE), "Chicken Drumsticks"),
    (re.compile(r"\bwhole\s+chickens?\b", re.IGNORECASE), "Whole Chicken"),
    (re.compile(r"\bchicken\b", re.IGNORECASE), "Chicken"),
    (re.compile(r"\bground\s+beef\b", re.IGNORECASE), "Ground Beef"),
    (re.compile(r"\bpork\s+chops?\b", re.IGNORECASE), "Pork Chops"),
    (re.compile(r"\b(?:pork\s+)?(?:spare\s+)?ribs?\b", re.IGNORECASE), "Ribs"),
    (re.compile(r"\bsteaks?\b", re.IGNORECASE), "Steak"),
    (re.compile(r"\broasts?\b", re.IGNORECASE), "Roast"),
    (re.compile(r"\bturkey\b", re.IGNORECASE), "Turkey"),
    (re.compile(r"\bsalmon\b", re.IGNORECASE), "Salmon"),
    (re.compile(r"\bshrimp\b", re.IGNORECASE), "Shrimp"),
    # Produce
    (re.compile(r"\bpotato(?:es)?\b", re.IGNORECASE), "Potatoes"),
    (re.compile(r"\bapples?\b", re.IGNORECASE), "Apples"),
    (re.compile(r"\bpears?\b", re.IGNORECASE), "Pears"),
    (re.compile(r"\bgrapes?\b", re.IGNORECASE), "Grapes"),
    (re.compile(r"\bavocados?\b", re.IGNORECASE), "Avocados"),
    (re.compile(r"\btomato(?:es)?\b", re.IGNORECASE), "Tomatoes"),
    (re.compile(r"\bstrawberr(?:y|ies)\b", re.IGNORECASE), "Strawberries"),
    (re.compile(r"\bblueberr(?:y|ies)\b", re.IGNORECASE), "Blueberries"),
    (re.compile(r"\bsquash\b", re.IGNORECASE), "Squash"),
    (re.compile(r"\bonions?\b", re.IGNORECASE), "Onions"),
    (re.compile(r"\bpeppers?\b", re.IGNORECASE), "Peppers"),
    # Pantry & Bakery
    (re.compile(r"\bbread\b", re.IGNORECASE), "Bread"),
    (re.compile(r"\btortillas?\b", re.IGNORECASE), "Tortillas"),
    (re.compile(r"\bpasta\s+sauce\b", re.IGNORECASE), "Pasta Sauce"),
    (re.compile(r"\bpasta\b", re.IGNORECASE), "Pasta"),
    (re.compile(r"\bcoffee\b", re.IGNORECASE), "Coffee"),
    (re.compile(r"\bchips\b", re.IGNORECASE), "Chips"),
    (re.compile(r"\bpopcorn\b", re.IGNORECASE), "Popcorn"),
    (re.compile(r"\bsalsa\b", re.IGNORECASE), "Salsa"),
    (re.compile(r"\bpizzas?\b", re.IGNORECASE), "Pizza"),
    (re.compile(r"\bsoups?\b", re.IGNORECASE), "Soup"),
    (re.compile(r"\bbroth\b", re.IGNORECASE), "Broth"),
    (re.compile(r"\b(?:soda|coca-cola|pepsi|dr pepper)\b", re.IGNORECASE), "Soda"),
    (re.compile(r"\b(?:water|drinking water|spring water)\b", re.IGNORECASE), "Water"),
    (re.compile(r"\b(?:gatorade|propel|powerade|sports drink)\b", re.IGNORECASE), "Sports Drinks"),
    (re.compile(r"\bpeanuts\b", re.IGNORECASE), "Nuts & Seeds"),
]


DEPARTMENT_KEYWORDS: Dict[str, str] = {
    "bakery": "Bakery",
    "bread": "Bakery",
    "donut": "Bakery",
    "produce": "Produce",
    "fruit": "Produce",
    "vegetable": "Produce",
    "dairy": "Dairy",
    "milk": "Dairy",
    "cheese": "Dairy",
    "yogurt": "Dairy",
    "meat": "Meat & Seafood",
    "seafood": "Meat & Seafood",
    "beef": "Meat & Seafood",
    "chicken": "Meat & Seafood",
    "pork": "Meat & Seafood",
    "deli": "Deli",
    "prepared": "Deli",
    "soup": "Deli",
    "frozen": "Frozen",
    "cereal": "Cereal & Breakfast",
    "breakfast": "Cereal & Breakfast",
    "beverage": "Beverages",
    "drink": "Beverages",
    "soda": "Beverages",
    "juice": "Beverages",
    "coffee": "Beverages",
    "snack": "Snacks & Candy",
    "chips": "Snacks & Candy",
    "chip": "Snacks & Candy",
    "candy": "Snacks & Candy",
    "canned": "Canned Goods",
    "pantry": "Pantry",
    "pasta": "Pantry",
    "sauce": "Pantry",
    "condiment": "Pantry",
    "personal care": "Personal Care",
    "beauty": "Personal Care",
    "health": "Health",
    "household": "Household",
    "clean": "Household",
    "baby": "Baby",
    "pet": "Pet Care",
    "general": "General Merchandise",
    "kitchen": "General Merchandise",
    "outdoor": "General Merchandise",
    "skewer": "General Merchandise",
}


def infer_department(text: str) -> Optional[str]:
    """Identify broad department from text keywords."""
    if not text:
        return None
    text_lower = text.lower()
    for kw, dept in DEPARTMENT_KEYWORDS.items():
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            return dept
    return None


def infer_category(text: str) -> Optional[str]:
    """Classify a product into a generic commodity category irregardless of brand."""
    if not text:
        return None
    for pat, cat in COMMODITY_PATTERNS:
        if pat.search(text):
            return cat
    return None
