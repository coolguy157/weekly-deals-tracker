"""
vocabulary.py
Centralized domain vocabularies, brand registries, head nouns, and categorization keywords
for the circular and product normalizer subsystems.
"""

STORE_BRANDS = [
    "Signature SELECT", "Signature Farms", "Lucerne", "O Organics", "Open Nature",
    "Waterfront BISTRO", "Primo Taglio", "Value Corner", "Soleil", "ReadyMeals",
    "Signature Care", "Signature Cafe", "Debi Lilly Design",
    "Our Brand", "Giant", "Martin's", "Nature's Promise", "Taste of Inspirations",
    "Guiding Stars", "CareOne", "Smart Way", "Companion", "Guaranteed Value",
]

NATIONAL_BRANDS = [
    "McCormick", "Kraft", "Pillsbury", "Ro-Tel", "Libby's", "Bush's", "Mission",
    "Fage", "Horizon", "Daisy", "Philadelphia", "Lays", "Lay's", "Cheetos", "Ruffles",
    "Doritos", "Tostitos", "Smartfood", "Frito Lay", "Utz", "Planters",
    "Cheez-It", "Cheez It", "Goldfish", "Pringles", "Ritz", "Triscuit", "Wheat Thins", "Club", "Town House",
    "Coca-Cola", "Pepsi", "Gatorade", "Propel", "Budweiser", "Bud",
    "Canada Dry", "Schweppes", "Polar",
    "Shiner", "Corona", "Modelo", "Dos Equis", "Decoy", "Conundrum",
    "Kendall-Jackson", "Josh Cellars", "Josh", "La Crema", "Meiomi", "Kim Crawford",
    "Chateau Ste. Michelle", "Bogle", "Robert Mondavi", "Barefoot", "Woodbridge",
    "Sutter Home", "Yellow Tail", "Cupcake", "Stella Rosa", "14 Hands", "Headsnapper",
    "Andre", "Firefly Ridge", "Menage A Trois", "Ménage à Trois", "Chloe", "Nobilo", "Rold Gold",
    "Miss Vickie's", "Soleil", "Snapple", "Poppi", "Ozarka", "Sunny Delight",
    "Premier Protein", "Dr Pepper", "Powerade", "Vitamin Water", "Dasani", "Snuggle", "Purex",
    "Tina's", "Yoplait", "Chobani", "Dannon", "Oikos", "Tillamook", "Turkey Hill",
    "Banquet", "BelGioioso", "Aleia's", "Sparkle", "Artesano",
    "Quaker", "Cap'n Crunch", "Life", "Campbell's", "Chef Boyardee", "Barilla",
    "Dole", "Bolthouse", "Bolthouse Farms", "NatureSweet", "Fresh Express", "Taylor Farms",
    "Earthbound Farm", "Organic Girl", "Green Giant", "Birds Eye",
    "Driscoll's", "Sunkist", "Halo", "Cuties", "Chiquita", "Del Monte",
    "Stouffer's", "Lean Cuisine", "Perdue", "Tyson", "Oscar Mayer",
    "Hormel", "Eckrich", "Johnsonville", "Smithfield", "Farmland", "Aidells", "Hatfield", "Butterball", "Jennie-O",
    "Sugardale", "Jimmy Dean", "Hillshire Farm", "Applegate", "Hebrew National", "Ball Park", "Nathan's",
    "General Mills", "Kellogg's", "Post", "Sargento", "Cabot", "Hidden Valley", "Ken's",
    "Ken's Steak House", "Marzetti", "Newman's Own", "Wish-Bone", "Heinz", "French's",
    "Hellmann's", "Best Foods",
    "Duncan Hines", "Betty Crocker", "Ghirardelli", "Nestle Toll House", "Nestlé Toll House", "Toll House",
    "Carnation", "Baker's", "Hershey's", "Hershey", "Domino", "C&H", "Crisco", "Gold Medal", "King Arthur",
    "Jell-O", "Jello", "PAM", "Fleischmann's", "Arm & Hammer", "Morton", "Smucker's", "Jif", "Skippy",
    "Peter Pan", "Nutella", "Log Cabin", "Mrs. Butterworth's", "Pearl Milling Company",
    "Cape Cod", "Snyder's of Hanover", "Late July",
]

DEPARTMENT_BANNERS = {
    "meat", "meat & seafood", "produce", "deli", "bakery", "dairy",
    "frozen", "grocery", "groceries", "floral", "general merchandise", "beer & wine", "beer", "wine",
    "fresh produce", "fresh meat & seafood", "deli & bakery", "pharmacy", "freshpass",
    "personal care & health", "pet care", "household essentials",
    "from your full service butcher block",
    "full service butcher block",
    "butcher block",
    "service butcher block",
    "from our service butcher block",
    "from your butcher block",
    "from our butcher block",
    "full service meat counter",
    "service seafood counter",
    "from our bakery",
    "from our deli",
}

HEAD_NOUN_PATTERNS = [
    r"Greenhouse\s+Grown\s+(?:Salad\s+(?:Blends?|Kits?|Bowls?))",
    r"Salad\s+(?:Blends?|Kits?|Bowls?)(?:\s+or\s+(?:Salad\s+)?(?:Blends?|Kits?|Bowls?))?",
    r"(?:Baby\s+Bella\s+|White\s+|Portabella\s+|Button\s+)?Mushrooms?",
    r"(?:Chicken\s+)?Breasts?",
    r"Whole\s+Chickens?",
    r"Chicken\s+(?:Thighs|Drumsticks|Wings|Tenders|Cutlets)",
    r"Pork\s+Loin\s+Chops?|Pork\s+Loin|Pork\s+Chops?|Pork\s+(?:Butt|Shoulder)(?:\s+Roasts?)?|Pork\s+Tenderloins?|Pork\s+(?:Spare\s*)?Ribs?|Baby\s+Back\s+Ribs?|Catfish(?:\s+Nuggets?|\s+Fillets?)?",
    r"Cheese|Cheddar|Mozzarella|Swiss|Provolone|Parmesan\s+Cheese",
    r"Squash|Pumpkin(?:s)?|Potato(?:es)?|Apple(?:s)?|Grape(?:s)?|Pear(?:s)?|Melon(?:s)?",
    r"Pepper(?:s)?|Onion(?:s)?|Tomato(?:es)?|Orange(?:s)?|Citrus|Peach(?:es)?|Plum(?:s)?",
    r"(?:Straw|Blue|Rasp|Black)?berr(?:ies|y)|Parfaits?|Tortillas?|Pizza\s+Crusts?|Crusts?",
    r"Bread|Buns|Rolls|Butter|Yogurt|Milk|Eggs",
    r"Sugar|Flour|Frosting|Cakes?|Brownies?|Muffins?|Cookies?",
    r"Sausage\s+(?:Links|Patties|Rolls)|Sausage|Bacon",
    r"Dressing",
    r"(?:Potato\s+|Tortilla\s+)?Chips?",
    r"Pretzels?",
    r"Crackers?",
    r"Trays?|Platters?",
]

COMMON_HEAD_NOUNS_PATTERN = "|".join(HEAD_NOUN_PATTERNS)

KNOWN_HEAD_NOUN_WORDS = set(
    "pumpkins pumpkin squash potatoes potato apples apple grapes grape pears pear melons melon peppers pepper onions onion tomatoes tomato oranges orange citrus peaches peach plums plum berries berry strawberries strawberry blueberries blueberry raspberries raspberry blackberries blackberry cheese mushrooms parfait parfaits tortillas crust crusts bread buns rolls butter yogurt milk eggs bacon chicken breasts thighs drumsticks tenders cutlets wings chops roast roasts pork loin butt shoulder tenderloin catfish nuggets ribs sugar flour frosting cake cakes brownie brownies muffins muffin cookies cookie chips chip pretzels pretzel crackers cracker tray trays platter platters".split()
)

MEAT_KEYWORDS = (
    "chicken", "beef", "pork", "turkey", "roast", "steak", "steaks",
    "chop", "chops", "rib", "ribs", "thigh", "thighs", "breast", "breasts",
    "drumstick", "drumsticks", "wing", "wings", "tenderloin", "brisket",
    "sausage", "bacon", "loin",
)

FOOD_KEYWORDS = {
    "bacon", "lunchmeat", "sausage", "chicken", "beef", "pork", "steak",
    "roast", "fillet", "fillets", "shrimp", "salmon", "cheese", "eggs",
    "milk", "butter", "bread",
}

SEASONING_KEYWORDS = (
    "taco seasoning", "seasoning mix", "gravy mix", "fajita seasoning",
    "chili seasoning", "sloppy joe seasoning",
)

DELI_BRANDS = (
    "Primo Taglio", "Dietz & Watson", "Dietz Watson", "Boar's Head",
)
