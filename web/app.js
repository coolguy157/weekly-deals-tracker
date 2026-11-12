/**
 * Giant Weekly Deals - Lewisburg PA Tracker
 * Client-side Controller & Dynamic Filter Engine
 * Supports circular ad grouping with expandable individual item breakdowns
 */

(function () {
  'use strict';

  // State
  let allDeals = [];
  let flyerMeta = null;
  let activeCategory = 'ALL';
  let activeFilter = null; // 'atl', 'great', 'front', 'catbest', 'bogo', 'points'
  let searchQuery = '';
  let activeSort = 'featured';
  let viewMode = 'grid'; // 'grid' | 'table'
  let groupByAd = true; // Group deals by circular ad by default
  let expandedGroupIds = new Set(); // Multi-item groups currently expanded (collapsed by default)
  let singleRateExpandedDealIds = new Set(); // Single-item cards currently showing rating drawer
  let shoppingList = []; // { id, name, price, unit_price, checked, page }
  let itemRatings = {}; // Map of productKey -> 'love' | 'giveaway' | 'hide'

  // Tab & Categorization State
  let activeTab = 'deals'; // 'deals' | 'categorize'
  let pendingFeedRefresh = false; // Deferred re-ordering flag

  let catSearchQuery = '';
  let catActiveStatus = 'all'; // 'all' | 'unrated' | 'love' | 'giveaway' | 'hide'
  let catActiveCategory = 'ALL';
  let catActiveSort = 'name_asc';

  // DOM Elements
  const dealsGrid = document.getElementById('deals-grid');
  const dealsTableContainer = document.getElementById('deals-table-container');
  const dealsTableBody = document.getElementById('deals-table-body');
  const loadingState = document.getElementById('loading-state');
  const emptyState = document.getElementById('empty-state');
  const searchInput = document.getElementById('search-input');
  const searchClearBtn = document.getElementById('search-clear-btn');
  const sortSelect = document.getElementById('sort-select');
  const categoryPillsContainer = document.getElementById('category-pills');
  const filterChips = document.querySelectorAll('.filter-chip');
  const circularValidity = document.getElementById('circular-validity');
  const resultsCountText = document.getElementById('results-count-text');
  const resetFiltersBtn = document.getElementById('reset-filters-btn');
  const emptyResetBtn = document.getElementById('empty-reset-btn');
  const toggleGroupingBtn = document.getElementById('toggle-grouping-btn');
  const expandCollapseAllBtn = document.getElementById('expand-collapse-all-btn');
  const expandCollapseIcon = document.getElementById('expand-collapse-icon');
  const expandCollapseText = document.getElementById('expand-collapse-text');

  // Navigation & Categorize View Elements
  const navTabDeals = document.getElementById('nav-tab-deals');
  const navTabCategorize = document.getElementById('nav-tab-categorize');
  const navRatedBadge = document.getElementById('nav-rated-badge');
  const dealsFeedView = document.getElementById('deals-feed-view');
  const categorizeView = document.getElementById('categorize-view');

  const prefStatLoved = document.getElementById('pref-stat-loved');
  const prefStatGiveaway = document.getElementById('pref-stat-giveaway');
  const prefStatHidden = document.getElementById('pref-stat-hidden');
  const prefStatUnrated = document.getElementById('pref-stat-unrated');

  const catSearchInput = document.getElementById('categorize-search-input');
  const catSearchClear = document.getElementById('categorize-search-clear');
  const catSortSelect = document.getElementById('categorize-sort-select');
  const catCategoryPills = document.getElementById('categorize-category-pills');
  const catItemsList = document.getElementById('categorize-items-list');
  const catCountText = document.getElementById('categorize-count-text');
  const catEmptyState = document.getElementById('categorize-empty-state');
  const catClearAllBtn = document.getElementById('categorize-clear-all-btn');

  // Stats Counters
  const statTotalCount = document.getElementById('stat-total-count');
  const statAtlCount = document.getElementById('stat-atl-count');
  const statFrontpageCount = document.getElementById('stat-frontpage-count');
  const statCatbestCount = document.getElementById('stat-catbest-count');

  // View Toggles
  const viewGridBtn = document.getElementById('view-grid-btn');
  const viewTableBtn = document.getElementById('view-table-btn');

  // Shopping List Elements
  const shoppingListTrigger = document.getElementById('shopping-list-trigger');
  const listCountBadge = document.getElementById('list-count-badge');
  const drawerBackdrop = document.getElementById('shopping-list-backdrop');
  const shoppingDrawer = document.getElementById('shopping-list-drawer');
  const closeDrawerBtn = document.getElementById('close-drawer-btn');
  const shoppingListItems = document.getElementById('shopping-list-items');
  const emptyListView = document.getElementById('empty-list-view');
  const drawerItemCount = document.getElementById('drawer-item-count');
  const drawerTotalPrice = document.getElementById('drawer-total-price');
  const copyListBtn = document.getElementById('copy-list-btn');
  const clearListBtn = document.getElementById('clear-list-btn');
  const toast = document.getElementById('toast');

  function getShoppingListStorageKey() {
    if (flyerMeta && flyerMeta.merchant) {
      const cleanMerchant = flyerMeta.merchant.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
      return `${cleanMerchant}_shopping_list`;
    }
    return 'giant_lewisburg_shopping_list';
  }

  // Load Saved Shopping List from LocalStorage
  function loadSavedShoppingList() {
    try {
      const key = getShoppingListStorageKey();
      const saved = localStorage.getItem(key) || localStorage.getItem('giant_lewisburg_shopping_list');
      if (saved) {
        shoppingList = JSON.parse(saved);
        updateShoppingListUI();
      }
    } catch (e) {
      console.warn('Could not load shopping list from localStorage', e);
    }
  }

  function saveShoppingList() {
    try {
      const key = getShoppingListStorageKey();
      localStorage.setItem(key, JSON.stringify(shoppingList));
    } catch (e) {
      console.warn('Could not save shopping list', e);
    }
    updateShoppingListUI();
  }

  // User Item Preferences & Rating Storage
  const ITEM_RATINGS_STORAGE_KEY = 'grocery_item_ratings_v1';

  function loadSavedItemRatings() {
    try {
      const saved = localStorage.getItem(ITEM_RATINGS_STORAGE_KEY);
      if (saved) {
        itemRatings = JSON.parse(saved);
      }
    } catch (e) {
      console.warn('Could not load item ratings from localStorage', e);
      itemRatings = {};
    }
  }

  function saveItemRatings() {
    try {
      localStorage.setItem(ITEM_RATINGS_STORAGE_KEY, JSON.stringify(itemRatings));
    } catch (e) {
      console.warn('Could not save item ratings to localStorage', e);
    }
  }

  function getProductKey(item) {
    if (!item) return '';
    if (item.product_id != null && item.product_id !== 0) {
      return `pid_${item.product_id}`;
    }
    const cleanName = (item.name || '').toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 50);
    return `name_${cleanName}`;
  }

  function getItemRating(item) {
    const key = getProductKey(item);
    return itemRatings[key] || null;
  }

  function setItemRating(item, rating, source = 'feed') {
    const key = getProductKey(item);
    if (!key) return;
    const current = itemRatings[key];
    const isClearing = current === rating;
    if (isClearing) {
      delete itemRatings[key];
      showToast(`Reset rating for ${item.name.split(' - ')[0]}`);
    } else {
      itemRatings[key] = rating;
      const label = rating === 'love' ? '❤️ Favorite' : (rating === 'deal_only' ? '🎯 Deal Only' : (rating === 'giveaway' ? '🎁 Giveaway' : '🚫 Hidden'));
      showToast(`Marked ${item.name.split(' - ')[0]} as ${label}`);
    }
    saveItemRatings();
    updateRatingBadgesCount();

    if (source === 'categorize') {
      renderCategorizeView();
      pendingFeedRefresh = true;
    } else {
      // In-place feed update without jumping/reordering while interacting with an ad card!
      updateInPlaceFeedRow(key, isClearing ? null : rating);
      pendingFeedRefresh = true;
    }
  }

  function flushPendingFeedRefresh() {
    if (pendingFeedRefresh) {
      pendingFeedRefresh = false;
      renderDeals();
    }
  }

  function updateInPlaceFeedRow(productKey, rating) {
    // 1. Update matching rows in expanded multi-item groups
    document.querySelectorAll(`.group-item-row[data-product-key="${productKey}"]`).forEach(row => {
      const loveBtn = row.querySelector('.btn-rate-icon[data-rate="love"]');
      const dealBtn = row.querySelector('.btn-rate-icon[data-rate="deal_only"]');
      const giveBtn = row.querySelector('.btn-rate-icon[data-rate="giveaway"]');
      const hideBtn = row.querySelector('.btn-rate-icon[data-rate="hide"]');
      if (loveBtn) loveBtn.classList.toggle('active-love', rating === 'love');
      if (dealBtn) dealBtn.classList.toggle('active-deal-only', rating === 'deal_only');
      if (giveBtn) giveBtn.classList.toggle('active-giveaway', rating === 'giveaway');
      if (hideBtn) hideBtn.classList.toggle('active-hide', rating === 'hide');

      const subDiv = row.querySelector('.group-item-sub');
      if (subDiv) {
        const existingTag = subDiv.querySelector('.item-rating-tag');
        if (existingTag) existingTag.remove();
        if (rating) {
          const tag = document.createElement('span');
          tag.className = `item-rating-tag rating-${rating}`;
          tag.textContent = rating === 'love' ? '❤️ Favorite' : (rating === 'deal_only' ? '🎯 Deal Only' : (rating === 'giveaway' ? '🎁 Giveaway' : '🚫 Hidden'));
          subDiv.appendChild(tag);
        }
      }
    });

    // 2. Update matching single-item cards
    document.querySelectorAll(`.deal-card[data-product-key="${productKey}"]`).forEach(card => {
      const toggleBtn = card.querySelector('.btn-rate-toggle');
      if (toggleBtn) {
        toggleBtn.className = `btn-rate-toggle ${rating === 'love' ? 'active-loved' : (rating === 'deal_only' ? 'active-deal-only' : (rating === 'giveaway' ? 'active-giveaway' : (rating === 'hide' ? 'active-hidden' : '')))}`;
        toggleBtn.textContent = rating === 'love' ? '❤️ Favorite' : (rating === 'deal_only' ? '🎯 Deal Only' : (rating === 'giveaway' ? '🎁 Giveaway' : (rating === 'hide' ? '🚫 Hidden' : '⭐ Rate')));
      }
      const loveBtn = card.querySelector('.btn-rate-icon[data-rate="love"]');
      const dealBtn = card.querySelector('.btn-rate-icon[data-rate="deal_only"]');
      const giveBtn = card.querySelector('.btn-rate-icon[data-rate="giveaway"]');
      const hideBtn = card.querySelector('.btn-rate-icon[data-rate="hide"]');
      if (loveBtn) loveBtn.classList.toggle('active-love', rating === 'love');
      if (dealBtn) dealBtn.classList.toggle('active-deal-only', rating === 'deal_only');
      if (giveBtn) giveBtn.classList.toggle('active-giveaway', rating === 'giveaway');
      if (hideBtn) hideBtn.classList.toggle('active-hide', rating === 'hide');
    });
  }

  function getUniqueProducts() {
    const productsMap = new Map();
    allDeals.forEach(d => {
      const key = getProductKey(d);
      if (!productsMap.has(key)) {
        productsMap.set(key, {
          key,
          product_id: d.product_id,
          name: d.name,
          brand: d.brand || '',
          category: d.category || 'Other',
          department: d.department || getGroceryDepartment(d),
          price: d.price,
          unit_price: d.unit_price,
          unit_type: d.unit_type,
          deal_id: d.deal_id,
          badge: d.badge || '',
          is_front_page: d.is_front_page || false,
        });
      } else {
        const existing = productsMap.get(key);
        if (d.price != null && (existing.price == null || d.price < existing.price)) {
          existing.price = d.price;
          existing.unit_price = d.unit_price;
          existing.deal_id = d.deal_id;
        }
      }
    });
    return Array.from(productsMap.values());
  }

  function updateRatingBadgesCount() {
    const keys = Object.keys(itemRatings);
    let loved = 0;
    let dealOnly = 0;
    let giveaway = 0;
    let hidden = 0;
    keys.forEach(k => {
      const r = itemRatings[k];
      if (r === 'love') loved++;
      else if (r === 'deal_only') dealOnly++;
      else if (r === 'giveaway') giveaway++;
      else if (r === 'hide') hidden++;
    });
    const totalRated = loved + dealOnly + giveaway + hidden;

    if (navRatedBadge) {
      navRatedBadge.textContent = totalRated > 0 ? `${totalRated}` : '0';
    }

    const uniqueProducts = getUniqueProducts();
    const totalProducts = uniqueProducts.length;
    const unrated = Math.max(0, totalProducts - totalRated);

    if (prefStatLoved) prefStatLoved.querySelector('span').textContent = loved;
    const prefStatDealOnly = document.getElementById('pref-stat-deal-only');
    if (prefStatDealOnly) prefStatDealOnly.querySelector('span').textContent = dealOnly;
    if (prefStatGiveaway) prefStatGiveaway.querySelector('span').textContent = giveaway;
    if (prefStatHidden) prefStatHidden.querySelector('span').textContent = hidden;
    if (prefStatUnrated) prefStatUnrated.querySelector('span').textContent = unrated;

    const elAll = document.getElementById('cat-count-all');
    const elUnrated = document.getElementById('cat-count-unrated');
    const elLove = document.getElementById('cat-count-love');
    const elDealOnly = document.getElementById('cat-count-deal-only');
    const elGive = document.getElementById('cat-count-giveaway');
    const elHide = document.getElementById('cat-count-hide');

    if (elAll) elAll.textContent = totalProducts;
    if (elUnrated) elUnrated.textContent = unrated;
    if (elLove) elLove.textContent = loved;
    if (elDealOnly) elDealOnly.textContent = dealOnly;
    if (elGive) elGive.textContent = giveaway;
    if (elHide) elHide.textContent = hidden;
  }

  // Toast Notification
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 2500);
  }

  // Data Fetching
  async function fetchDeals() {
    try {
      const response = await fetch('deals.json?t=' + Date.now(), { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();

      if (Array.isArray(data)) {
        allDeals = data;
      } else if (data && data.deals) {
        allDeals = data.deals;
        flyerMeta = data.flyer;
      }

      initData();
    } catch (err) {
      console.warn('Failed to load deals.json, attempting fallback', err);
      loadingState.innerHTML = `
        <div class="empty-icon">⚠️</div>
        <h3>Waiting for Circular Sync</h3>
        <p>No active deals.json file found yet. Run the weekly sync action or CLI to generate deals.</p>
      `;
    }
  }

  const COMMODITY_TO_DEPT = {
    // Produce
    'Apples': 'Produce', 'Avocados': 'Produce', 'Bananas': 'Produce', 'Blueberries': 'Produce',
    'Grapes': 'Produce', 'Onions': 'Produce', 'Pears': 'Produce', 'Peppers': 'Produce',
    'Potatoes': 'Produce', 'Salad': 'Produce', 'Squash': 'Produce', 'Strawberries': 'Produce',
    'Tomatoes': 'Produce',
    // Meat & Seafood
    'Beef': 'Meat & Seafood', 'Boneless Chicken Breasts': 'Meat & Seafood', 'Bone-In Chicken Breasts': 'Meat & Seafood',
    'Chicken Tenders': 'Meat & Seafood', 'Boneless Chicken Thighs': 'Meat & Seafood', 'Bone-In Chicken Thighs': 'Meat & Seafood',
    'Chicken Wings': 'Meat & Seafood', 'Chicken Drumsticks': 'Meat & Seafood', 'Whole Chicken': 'Meat & Seafood',
    'Chicken': 'Meat & Seafood', 'Ground Beef': 'Meat & Seafood', 'Pork Chops': 'Meat & Seafood',
    'Ribs': 'Meat & Seafood', 'Steak': 'Meat & Seafood', 'Roast': 'Meat & Seafood',
    'Salmon': 'Meat & Seafood', 'Shrimp': 'Meat & Seafood', 'Turkey': 'Meat & Seafood',
    'Bacon': 'Meat & Seafood', 'Sausage': 'Meat & Seafood', 'Hot Dogs': 'Meat & Seafood',
    // Dairy & Eggs
    'Butter': 'Dairy & Eggs', 'Cheese': 'Dairy & Eggs', 'Cream Cheese': 'Dairy & Eggs',
    'Shredded Cheese': 'Dairy & Eggs', 'Sliced Cheese': 'Dairy & Eggs', 'Chunk Cheese': 'Dairy & Eggs',
    'String Cheese': 'Dairy & Eggs', 'Eggs': 'Dairy & Eggs', 'Milk': 'Dairy & Eggs',
    'Sour Cream': 'Dairy & Eggs', 'Yogurt': 'Dairy & Eggs',
    // Bakery & Bread
    'Bread': 'Bakery & Bread', 'Tortillas': 'Bakery & Bread',
    // Frozen
    'Ice Cream': 'Frozen Foods', 'Pizza': 'Frozen Foods',
    // Pantry
    'Pasta': 'Pantry & Dry Goods', 'Pasta Sauce': 'Pantry & Dry Goods', 'Soup': 'Pantry & Dry Goods',
    'Broth': 'Pantry & Dry Goods', 'Salad Dressing': 'Pantry & Dry Goods', 'Salsa': 'Pantry & Dry Goods',
    // Snacks & Candy
    'Chips': 'Snacks & Candy', 'Crackers': 'Snacks & Candy', 'Popcorn': 'Snacks & Candy',
    'Nuts & Seeds': 'Snacks & Candy', 'Gum': 'Snacks & Candy',
    // Beverages
    'Coffee': 'Beverages', 'Soda': 'Beverages', 'Water': 'Beverages', 'Sports Drinks': 'Beverages',
    // Beer & Wine
    'Beer': 'Beer, Wine & Spirits', 'Wine': 'Beer, Wine & Spirits',
    // Deli
    'Deli': 'Deli & Prepared'
  };

  const DEPT_TEXT_RULES = [
    // Beer, Wine & Spirits
    [/\b(?:wine|chardonnay|cabernet|pinot|merlot|sauvignon|moscato|prosecco|champagne|beer|ale|lager|ipa|pilsner|stout|hard\s+seltzer|cider|budweiser|bud\s+light|miller\s+lite|coors\s+light|michelob|corona|modelo|heineken|white\s+claw|truly|twisted\s+tea)\b/i, 'Beer, Wine & Spirits'],
    // Meat & Seafood
    [/\b(?:beef|chicken|pork|turkey|steak|bacon|sausage|frank|hot\s*dog|meatball|ham\b|roast\b|ribeye|sirloin|tenderloin|salmon|shrimp|tilapia|cod\b|crab|lobster|tuna|scallop|fillet|seafood|poultry|scrapple|prosciutto|salami|pepperoni|meat\s+stick)\b/i, 'Meat & Seafood'],
    // Produce
    [/\b(?:apple|apples|banana|bananas|berry|berries|grape|grapes|citrus|orange|oranges|lemon|lemons|lime|limes|potato|potatoes|onion|onions|pepper|peppers|tomato|tomatoes|salad|lettuce|spinach|carrot|carrots|broccoli|celery|avocado|avocados|mushroom|mushrooms|cucumber|cucumbers|squash|floral|bouquet|rose|roses|plant|fresh\s+cut|asparagus|corn\b|herbs?|garlic|cantaloupe|watermelon|honeydew|pineapple|mango|clementine|peach|peaches|plum|cabbage|kale|zucchini)\b/i, 'Produce'],
    // Dairy & Eggs
    [/\b(?:milk|cheese|butter|yogurt|cream\s+cheese|sour\s+cream|cottage\s+cheese|half\s*&\s*half|creamer|egg|eggs|parmesan|cheddar|mozzarella|ricotta|provolone|brie|gouda|feta|swiss\s+cheese)\b/i, 'Dairy & Eggs'],
    // Frozen Foods
    [/\b(?:frozen|ice\s+cream|gelato|sorbet|pizza|waffle|waffles|popsicles?|hot\s+pockets?|frozen\s+dinner|entrees?|frozen\s+fruit|frozen\s+vegetable|ice\b|totino|birds\s+eye|green\s+giant\s+steam|stouffer|lean\s+cuisine|marie\s+callender|digiorno)\b/i, 'Frozen Foods'],
    // Bakery & Bread
    [/\b(?:bread|bagel|bagels|muffin|muffins|roll|rolls|buns?|tortilla|tortillas|croissant|donut|doughnut|cake|cakes|pie\b|pies\b|pastry|pastries|bakery|danish|cupcake|cupcakes)\b/i, 'Bakery & Bread'],
    // Beverages
    [/\b(?:coffee|tea\b|juice|soda|water|sparkling\s+water|seltzer|cola|pepsi|coke\b|dr\s+pepper|snapple|lemonade|drink|drinks|gatorade|powerade|beverage|k-cup|cider|kombucha|shake\b|smoothie|bolthouse)\b/i, 'Beverages'],
    // Snacks & Candy
    [/\b(?:chips|crisps|crackers|cookies?|popcorn|pretzel|pretzels|snack|snacks|candy|chocolate|chocolates|gummy|gummies|fudge|nuts|cashews|almonds|peanuts|granola\s*bars?|protein\s*bars?|chewy\s*bars?|bars?\b|fruit\s+snacks?|trail\s+mix|cheez-it|oreo|doritos|lays|tostitos|snack\s+mix|goldfish)\b/i, 'Snacks & Candy'],
    // Pantry & Dry Goods
    [/\b(?:cereal|oatmeal|pasta|macaroni|sauce|marinara|soup|soups|broth|canned|beans|rice|oil|olive\s+oil|flour|sugar|spice|spices|seasoning|mayonnaise|mustard|ketchup|dressing|condiment|condiments|syrup|peanut\s+butter|jelly|jam|pantry|baking|mix\b|mashed\s+potatoes|tuna\s+can|gravy|stuffing|mccormick|oregano|thyme|chili\s+powder|cumin|coriander|cinnamon|paprika|curry\b|garam\s+masala|tarragon|dill\s+weed|vanilla\s+extract|baking\s+soda|yeast|vinegar|honey)\b/i, 'Pantry & Dry Goods'],
    // Household & Cleaning
    [/\b(?:detergent|laundry|bleach|towel|paper\s+towels?|bath\s+tissue|toilet\s+paper|napkin|napkins|cleaner|disinfect|trash\s+bag|trash\s+bags|foil|wrap|ziploc|dish\s+soap|dishwasher|air\s+freshener|dryer\s+sheet|dryer\s+sheets|gain|tide|bounce|bounty|charmin|skewers?|toothpick|toothpicks|thermometer|scent\s+booster|downy|dreft|fabric\s+softener|swiffer|clorox|lysol|glade|febreze|dawn|finish|cascade|storage\s+bags?|aluminum\s+foil|candles?|batter(?:y|ies)|bag\s+clips?|clips?|cups?|plates?|bowls?|straws?|food\s+storage)\b/i, 'Household & Cleaning'],
    // Health & Beauty
    [/\b(?:shampoo|conditioner|body\s+wash|soap|deodorant|toothpaste|toothbrush|lotion|skincare|cosmetic|vitamin|vitamins|supplement|supplements|medicine|cold|flu|pain\s+relief|band-aid|care|pads?|tampons?|liners?|floss|dental|oral-b|colgate|crest|dove|pantene|head\s+&\s+shoulders|tampax|always|razor|razors|shave|antiperspirant)\b/i, 'Health & Beauty'],
    // Baby & Pet
    [/\b(?:diaper|diapers|wipes|baby|baby\s+food|formula|pampers|huggies|gerber|goodnites|pull-ups?|aquaphor|aveeno|dog\s+food|cat\s+food|pet|pets|cat\s+litter|kibble|puppy|kitten|purina|pedigree|friskies|fancy\s+feast|blue\s+buffalo)\b/i, 'Baby & Pet'],
    // Deli & Prepared
    [/\b(?:deli|prepared|rotisserie|hummus|dips?|guacamole|sushi|sandwich|salad\s+bar|ready\s+to\s+eat|take\s*&\s*bake)\b/i, 'Deli & Prepared']
  ];

  function getGroceryDepartment(deal) {
    if (!deal) return 'Other';
    if (deal.department) return deal.department;
    const cat = deal.category;
    if (cat && COMMODITY_TO_DEPT[cat]) {
      return COMMODITY_TO_DEPT[cat];
    }
    const text = `${deal.name || ''} ${deal.brand || ''} ${deal.raw_title || ''} ${deal.ad_title || ''}`;
    for (let i = 0; i < DEPT_TEXT_RULES.length; i++) {
      if (DEPT_TEXT_RULES[i][0].test(text)) {
        return DEPT_TEXT_RULES[i][1];
      }
    }
    return (cat && cat !== 'Other') ? cat : 'Other';
  }

  function parseDateSafely(str) {
    if (!str) return null;
    let clean = String(str).replace(/ZT.*$/, 'Z').split('T')[0];
    let d = new Date(clean + 'T12:00:00');
    if (isNaN(d.getTime())) {
      d = new Date(str);
    }
    return isNaN(d.getTime()) ? null : d;
  }

  function isAtlBadge(badge) {
    return /new_all_time_low|new_atl|matches_atl|match_atl|atl|all[-_]time/i.test(badge || '');
  }
  function isNewAtl(d) {
    if (!d) return false;
    const badge = typeof d === 'string' ? d : (d.badge || '');
    if (/new_all_time_low|new_atl/i.test(badge)) return true;
    const analysis = typeof d === 'object' ? (d.analysis || d.summary_reason || '') : '';
    return isAtlBadge(badge) && /new all-time low/i.test(analysis);
  }
  function isMatchAtl(d) {
    if (!d) return false;
    const badge = typeof d === 'string' ? d : (d.badge || '');
    if (/matches_atl|match_atl/i.test(badge)) return true;
    const analysis = typeof d === 'object' ? (d.analysis || d.summary_reason || '') : '';
    return isAtlBadge(badge) && /matches all-time low|multi-week sale at all-time low/i.test(analysis);
  }
  function isGreatBadge(badge) {
    return /great|beat/i.test(badge || '');
  }
  function isPointsFreebie(d) {
    if (!d) return false;
    const badge = typeof d === 'string' ? d : (d.badge || '');
    if (/points_freebie/i.test(badge)) return true;
    const pDetail = typeof d === 'object' ? (d.promo_detail || '') : '';
    const mPts = pDetail.match(/(\d+)[-\s]+(?:CHOICE\s+)?POINTS/i) || pDetail.match(/(\d+)[-\s]+POINT\s+FREEBIE/i) || pDetail.match(/FREE\s+with\s+(\d+)\s+CHOICE\s+points/i);
    if (mPts && parseInt(mPts[1], 10) <= 10) return true;
    return false;
  }

  function isPointsDeal(d) {
    if (!d) return false;
    const badge = typeof d === 'string' ? d : (d.badge || '');
    return /points_deal/i.test(badge);
  }

  function isPointsRedemption(d) {
    if (!d) return false;
    const badge = typeof d === 'string' ? d : (d.badge || '');
    const pType = typeof d === 'object' ? (d.promo_type || '') : '';
    const pDetail = typeof d === 'object' ? (d.promo_detail || '') : '';
    return /points_redemption/i.test(badge) || pType === 'points_redemption' || /choice points/i.test(pDetail);
  }

  function getPointsExtrapolatedInfo(d) {
    if (!d || (!isPointsFreebie(d) && !isPointsDeal(d) && !isPointsRedemption(d))) return null;

    const text = `${d.promo_detail || ''} ${d.analysis || ''} ${d.raw_title || ''} ${d.name || ''}`;
    let pts = null;
    let savedVal = null;
    let rateCents = null;

    const mPts = text.match(/(\d+)[-\s]+(?:CHOICE\s+)?POINTS/i) || text.match(/(\d+)[-\s]+POINT\s+FREEBIE/i) || text.match(/FREE\s+with\s+(\d+)\s+CHOICE\s+points/i);
    if (mPts) {
      pts = parseInt(mPts[1], 10);
    }

    const mSave = text.match(/SAVE\s+(?:UP\s+TO\s+|AT\s+LEAST\s+)?\$(\d+(?:\.\d{2})?)/i) || text.match(/Save\s+\$(\d+(?:\.\d{2})?)/i) || text.match(/for\s+\$(\d+(?:\.\d{2})?)\s+value/i);
    if (mSave) {
      savedVal = parseFloat(mSave[1]);
    } else if (d.base_price && d.base_price > 0) {
      savedVal = d.base_price;
    } else if (d.price && d.price > 0) {
      savedVal = d.price;
    }

    const mRate = text.match(/([\d\.]+)¢\/pt/i);
    if (mRate) {
      rateCents = parseFloat(mRate[1]).toFixed(1);
    } else if (pts && savedVal && pts > 0) {
      rateCents = ((savedVal / pts) * 100).toFixed(1);
    }

    let yieldTag = '';
    const isFree = isPointsFreebie(d);
    if (pts && savedVal && rateCents) {
      yieldTag = isFree
        ? `🪙 ${pts} pts • Save $${savedVal.toFixed(2)} (${rateCents}¢/pt)`
        : `🪙 ${pts} pts • $${savedVal.toFixed(2)} val (${rateCents}¢/pt)`;
    } else if (pts && savedVal) {
      yieldTag = isFree ? `🪙 ${pts} pts • Save $${savedVal.toFixed(2)}` : `🪙 ${pts} pts • $${savedVal.toFixed(2)} val`;
    } else if (pts) {
      yieldTag = isFree ? `🪙 FREE with ${pts} pts` : `🪙 ${pts} CHOICE pts`;
    }

    return {
      pts,
      savedVal,
      rateCents,
      yieldTag,
    };
  }

  function getBadgeHtml(d) {
    if (!d) return '';
    const rawBadge = (d.badge || '').toUpperCase();
    const badges = [];

    const rating = getItemRating(d);
    if (rating === 'love') {
      badges.push('<span class="deal-badge user-loved">❤️ FAVORITE</span>');
    } else if (rating === 'deal_only') {
      badges.push('<span class="deal-badge user-deal-only">🎯 DEAL PICK</span>');
    } else if (rating === 'giveaway') {
      badges.push('<span class="deal-badge user-giveaway">🎁 GIVEAWAY</span>');
    } else if (rating === 'hide') {
      badges.push('<span class="deal-badge user-hidden">🚫 HIDDEN</span>');
    }

    if (isNewAtl(d)) {
      badges.push('<span class="deal-badge atl new-atl">🔥 NEW ALL-TIME LOW</span>');
    } else if (isMatchAtl(d)) {
      badges.push('<span class="deal-badge match-atl">⭐ MATCHES ATL</span>');
    } else if (/ATL|ALL[-_]TIME/i.test(rawBadge)) {
      badges.push('<span class="deal-badge atl">🔥 ALL-TIME LOW</span>');
    } else if (/POINTS_FREEBIE/i.test(rawBadge)) {
      badges.push('<span class="deal-badge points-freebie">🪙 FREE W/ POINTS</span>');
    } else if (/POINTS_DEAL/i.test(rawBadge)) {
      badges.push('<span class="deal-badge points-deal">🪙 HIGH-YIELD POINTS</span>');
    } else if (/POINTS_REWARD|REWARD/i.test(rawBadge)) {
      badges.push('<span class="deal-badge points-reward">🪙 POINTS REWARD</span>');
    } else if (/POINTS_REDEMPTION/i.test(rawBadge)) {
      badges.push('<span class="deal-badge points-redemption">🪙 REDEEM POINTS</span>');
    } else if (/SPEND_SAVE|SPEND/i.test(rawBadge)) {
      badges.push('<span class="deal-badge spend-save">🏷️ SPEND & SAVE</span>');
    } else if (/PERCENT_OFF|DISCOUNT/i.test(rawBadge)) {
      badges.push('<span class="deal-badge percent-off">🏷️ % OFF</span>');
    } else if (/BEAT/i.test(rawBadge)) {
      badges.push('<span class="deal-badge beat">🔥 BEAT AVG</span>');
    } else if (/CYCLE|REFRESH/i.test(rawBadge)) {
      badges.push('<span class="deal-badge cycle">🔄 CYCLE MATCH</span>');
    } else if (/HIKE/i.test(rawBadge)) {
      badges.push('<span class="deal-badge hike">⚠️ PRICE HIKE</span>');
    } else if (/FIRST_SEEN|FIRST/i.test(rawBadge)) {
      badges.push('<span class="deal-badge firstseen">🌱 FIRST SEEN</span>');
    } else if (/GREAT|SOLID/i.test(rawBadge)) {
      badges.push('<span class="deal-badge great">✨ GREAT DEAL</span>');
    }

    if (d.is_category_best) {
      badges.push('<span class="deal-badge catbest">⭐ CAT BEST</span>');
    }

    return badges.join(' ');
  }

  // Format Helpers
  function formatMoney(val) {
    if (val == null || isNaN(val)) return '—';
    return `$${Number(val).toFixed(2)}`;
  }

  function formatUnitPrice(val, unitType) {
    if (val == null || isNaN(val)) return '';
    const unit = unitType ? `/${unitType}` : '/unit';
    return `$${Number(val).toFixed(2)}${unit}`;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // =========================================================================
  // AD GROUPING LOGIC & DATA MODEL
  // =========================================================================

  function getGroupKey(deal) {
    const promo = (deal.promo_detail || '').trim().toLowerCase();
    const page = deal.page || 1;

    // Check if this is part of the weekly Meal Deal bundle
    if (deal.promo_type === 'meal_deal' || promo.includes('meal deal') || promo.includes('get these free')) {
      return `meal_deal_p${page}`;
    }

    // Holiday Free Turkey / Choice points promotion
    if (promo.includes('400 choice') && (promo.includes('turkey') || promo.includes('tofurky') || (deal.name || '').toLowerCase().includes('turkey') || (deal.name || '').toLowerCase().includes('tofurky'))) {
      return `holiday_turkey_points_p${page}`;
    }

    if (deal.ad_id) {
      return `ad_${deal.ad_id}`;
    }
    const rawId = String(deal.raw_deal_id || '');
    if (rawId.length >= 11) {
      return `ad_${rawId.slice(0, 10)}`;
    }
    if (rawId && rawId !== '0') {
      return `raw_${rawId}`;
    }

    // Fallback: group by page, promo_type, and normalized promo_detail
    const pType = deal.promo_type || 'standard';
    const brand = (deal.brand || '').toLowerCase();
    if (promo && promo !== 'standard' && promo !== '(none)') {
      const cleanP = promo.replace(/[^a-z0-9]/g, '').slice(0, 25);
      return `promo_p${page}_${pType}_${cleanP}_${brand}`;
    }
    return `deal_${deal.deal_id}`;
  }

  function cleanFlyerRawTitle(title) {
    if (!title) return '';
    let t = title.replace(/\ufffd/g, '').replace(/[®™]/g, '').trim();
    t = t.replace(/\s+/g, ' ');
    t = t.replace(/\s*-\s*(\$\d+(\.\d{2})?|\d+\/\s*\$\d+|SAVE\s+\$\d+|DIGITAL\s+COUPON).*$/i, '').trim();
    return t;
  }

  function synthesizeGroupTitle(items) {
    if (items.length === 1) {
      return items[0].name || 'Deal Item';
    }

    // Check if this is a Meal Deal bundle
    const promo = (items[0].promo_detail || '').toLowerCase();
    if (items.some(it => it.promo_type === 'meal_deal') || promo.includes('meal deal') || promo.includes('get these free')) {
      return 'Weekly Meal Deal';
    }

    // Holiday Free Turkey promotion
    if (items.some(it => (it.promo_detail || '').toLowerCase().includes('400 choice') && ((it.promo_detail || '').toLowerCase().includes('turkey') || (it.name || '').toLowerCase().includes('turkey')))) {
      return "Giant Holiday Free Turkey (up to 20 lbs) or Stouffer's / Tofurky Roast";
    }

    // Prefer explicit parent canonical ad title if present
    const adTitle = items.find(it => it.ad_title)?.ad_title;
    if (adTitle && adTitle.trim() && !/^(?:select|assorted|various|mix|match)/i.test(adTitle.trim())) {
      return adTitle.trim();
    }

    // Check for shared concise raw flyer headline across items
    const rawTitles = Array.from(new Set(
      items
        .map(it => cleanFlyerRawTitle(it.raw_title || ''))
        .filter(Boolean)
    ));
    if (rawTitles.length === 1) {
      const sharedRaw = rawTitles[0];
      const commaCount = (sharedRaw.match(/,/g) || []).length;
      if (
        sharedRaw.length <= 80 &&
        commaCount <= 4 &&
        !/^(?:select|assorted|various|mix\s*&\s*match)\b/i.test(sharedRaw)
      ) {
        return sharedRaw;
      }
    }

    const brands = Array.from(new Set(items.map(it => it.brand).filter(Boolean))).sort();
    const names = items.map(it => it.name || '');

    // Common pack packaging
    let pkg = '';
    const packSizes = ['12 pk', '6 pk', '8 pk', '15 ct', 'Family Size', 'Party Size', '1 Liter', '2 Liter'];
    for (const p of packSizes) {
      if (names.every(n => n.toLowerCase().includes(p.toLowerCase()))) {
        pkg = ` (${p})`;
        break;
      }
    }

    // Multi-brand specialized categories
    if (brands.includes('Duncan Hines') && brands.includes('PAM')) {
      return 'Duncan Hines & PAM • Cake Mixes, Frosting & Baking Spray';
    }
    if (brands.includes('CareOne') && brands.includes("Nature's Promise")) {
      return "Nature's Promise & CareOne • Vitamins & Supplements";
    }
    if (brands.includes('Floral') || names.some(n => /carnation|mum/i.test(n))) {
      return 'Floral • Carnations & Mums (Colors May Vary)';
    }
    if (brands.includes("Martin's Snacks") && brands.includes("Nature's Own")) {
      return "Martin's Snacks & Nature's Own • Chips, Popcorn & Bread";
    }
    if (names.some(n => /potato chips|tortilla chips|pretzels/i.test(n)) && (brands.includes('Cape Cod') || brands.includes("Snyder's of Hanover") || brands.includes('Late July') || brands.includes('Utz') || brands.includes("Herr's"))) {
      return 'Potato Chips, Pretzels & Tortilla Chips';
    }
    const hasSeafood = (brands.includes('Fresh Seafood') || brands.includes('Hannaford') ||
      names.some(n => /\b(?:fish|seafood|salmon|shrimp|tilapia|swordfish|tuna|haddock|swai|whiting|flounder)\b|(?<!cape\s+)\bcod\b/i.test(n)) ||
      (names.some(n => /\bfillets?\b|\bfilets?\b/i.test(n)) && !names.some(n => /\b(?:pork|beef|chicken|turkey|steak|chop|loin|chips?|pretzels?|snacks?)\b/i.test(n)))) &&
      !names.some(n => /\b(?:chips?|pretzels?|snacks?|crackers?|cookies?|candy)\b/i.test(n)) &&
      !brands.includes('Cape Cod');
    if (hasSeafood) {
      return 'Fresh & Frozen Seafood Fillets';
    }

    // Check if all items share an identical product name once brand prefixes are removed
    const strippedNames = items.map(it => {
      let n = (it.name || '').trim();
      const b = (it.brand || '').trim();
      if (b && n.toLowerCase().startsWith(b.toLowerCase())) {
        n = n.slice(b.length).trim().replace(/^[-–—:,]\s*/, '');
      }
      return n;
    });

    if (strippedNames.length > 0 && strippedNames.every(sn => sn.length > 0 && sn.toLowerCase() === strippedNames[0].toLowerCase())) {
      if (brands.length === 1) {
        return `${brands[0]} ${strippedNames[0]}${pkg}`;
      }
      return `${strippedNames[0]}${pkg}`;
    }

    // Check if stripped names share a common suffix (e.g. "Salad Kits", "Water", "Soup")
    const commonSuffix = strippedNames.reduce((acc, curr) => {
      if (!acc) return curr;
      let matched = '';
      const words = acc.split(' ');
      for (let i = 0; i < words.length; i++) {
        const candidate = words.slice(i).join(' ');
        if (curr.toLowerCase().endsWith(candidate.toLowerCase())) {
          matched = candidate;
          break;
        }
      }
      return matched;
    }, '');

    if (commonSuffix && commonSuffix.length >= 4 && !/^(?:pack|items?|mix|selection)$/i.test(commonSuffix)) {
      if (brands.length === 1) {
        return `${brands[0]} ${commonSuffix}${pkg}`;
      }
      return `${commonSuffix}${pkg}`;
    }

    // Common grocery product types
    const keywords = [
      'Salad Blends or Kits', 'Salad Kits', 'Salad Blends', 'Salad Kit', 'Salad',
      'Soda', 'Potato Chips', 'Tortilla Chips', 'Chips', 'Cookies', 'Cereal',
      'Sausage', 'Bratwurst', 'Brats', 'Shampoo', 'Lotion', 'Bread', 'Dressing',
      'Broth', 'Crackers', 'Water', 'Tea', 'Juice', 'Vitamins', 'Candy', 'Dip',
      'Pasta', 'Rice', 'Ice Cream', 'Coffee', 'Cheese', 'Spices', 'Yogurt',
      'Snacks', 'Sauce', 'Chicken', 'Beef', 'Pork', 'Fish', 'Seafood', 'Bacon'
    ];

    let matchedKeyword = null;
    for (const kw of keywords) {
      const stem = kw.toLowerCase().replace(/s$/, '');
      if (names.every(n => n.toLowerCase().includes(kw.toLowerCase()) || n.toLowerCase().includes(stem))) {
        matchedKeyword = kw;
        break;
      }
    }

    if (matchedKeyword) {
      if (brands.length === 1) {
        const b = brands[0];
        if (items.length >= 2 && items.length <= 4) {
          const kwRegex = new RegExp(`\\s+${matchedKeyword}$`, 'i');
          const subParts = names.map(n => {
            let s = n;
            if (s.toLowerCase().startsWith(b.toLowerCase())) {
              s = s.slice(b.length).trim().replace(/^[-–—:]\s*/, '');
            }
            return s;
          });
          if (subParts.every(sp => kwRegex.test(sp))) {
            const modifiers = subParts.map(sp => sp.replace(kwRegex, '').trim()).filter(Boolean);
            if (modifiers.length === items.length && new Set(modifiers).size === items.length) {
              const joinedMods = modifiers.length === 2
                ? `${modifiers[0]} or ${modifiers[1]}`
                : `${modifiers.slice(0, -1).join(', ')} or ${modifiers[modifiers.length - 1]}`;
              return `${b} ${joinedMods} ${matchedKeyword}${pkg}`;
            }
          }
        }
        return `${brands[0]} ${matchedKeyword}${pkg}`;
      } else if (brands.length > 0) {
        return `${matchedKeyword}${pkg}`;
      } else {
        return `${matchedKeyword} Selection${pkg}`;
      }
    }

    if (brands.length === 1) {
      const b = brands[0];
      if (items.length >= 2 && items.length <= 4 && names.every(n => n.toLowerCase().startsWith(b.toLowerCase()))) {
        const subParts = names.map(n => n.slice(b.length).trim().replace(/^[-–—:]\s*/, ''));
        if (subParts.every(sp => sp.length > 0)) {
          if (subParts.length === 2) {
            return `${b} ${subParts[0]} or ${subParts[1]}`;
          }
          return `${b} ${subParts.slice(0, -1).join(', ')} or ${subParts[subParts.length - 1]}`;
        }
      }
      return `${b} Assorted Varieties${pkg} (${items.length} Items)`;
    } else if (brands.length > 0 && brands.length <= 3) {
      return `${brands.join(', ')} Selection${pkg} (${items.length} Items)`;
    } else if (brands.length > 3) {
      return `${brands.slice(0, 2).join(', ')} & more${pkg} (${items.length} Items)`;
    }

    const rep = items[0];
    const cat = (rep.category && rep.category !== 'Other') ? rep.category : (rep.department || getGroceryDepartment(rep) || 'Featured');
    const isMixMatch = items.some(it => (it.promo_type || '').includes('mix') || (it.promo_detail || '').toLowerCase().includes('mix'));
    const fallbackLabel = isMixMatch ? 'Mix & Match' : 'Selection';
    return `${cat} ${fallbackLabel}${pkg} (${items.length} Items)`;
  }

  function buildGroupObject(groupId, items) {
    const isMulti = items.length > 1;
    const brands = Array.from(new Set(items.map(it => it.brand).filter(Boolean))).sort();
    const prices = items.map(it => it.price).filter(p => p != null && !isNaN(p));
    const minPrice = prices.length ? Math.min(...prices) : null;
    const maxPrice = prices.length ? Math.max(...prices) : null;

    // Determine most common unit type in the group
    const unitTypeCounts = {};
    items.forEach(it => {
      if (it.unit_type) unitTypeCounts[it.unit_type] = (unitTypeCounts[it.unit_type] || 0) + 1;
    });
    const sortedUnitTypes = Object.keys(unitTypeCounts).sort((a, b) => unitTypeCounts[b] - unitTypeCounts[a]);
    const primaryUnitType = sortedUnitTypes[0] || null;

    // Only compute unit price range across items sharing the primary unit type
    const matchingUnitItems = primaryUnitType ? items.filter(it => it.unit_type === primaryUnitType && it.unit_price != null && !isNaN(it.unit_price)) : [];
    const minUnitPrice = matchingUnitItems.length ? Math.min(...matchingUnitItems.map(it => it.unit_price)) : null;
    const maxUnitPrice = matchingUnitItems.length ? Math.max(...matchingUnitItems.map(it => it.unit_price)) : null;

    const promoDetail = items.find(it => it.promo_detail)?.promo_detail || items[0].promo_detail || '';
    const promoType = items.find(it => it.promo_type && it.promo_type !== 'standard')?.promo_type || items[0].promo_type || 'standard';

    const hasNewAtl = items.some(it => isNewAtl(it));
    const hasMatchAtl = items.some(it => isMatchAtl(it));
    const hasAtl = hasNewAtl || hasMatchAtl || items.some(it => isAtlBadge(it.badge));
    const hasGreat = items.some(it => isGreatBadge(it.badge) || isAtlBadge(it.badge) || /beat/i.test(it.badge || ''));
    const hasCatBest = items.some(it => it.is_category_best);
    const hasPointsFreebie = items.some(it => isPointsFreebie(it));
    const hasPointsDeal = items.some(it => isPointsDeal(it));
    const hasLoved = items.some(it => getItemRating(it) === 'love');
    const hasDealOnly = items.some(it => getItemRating(it) === 'deal_only');
    const isQualifyingDealItem = (it) => isAtlBadge(it.badge) || isGreatBadge(it.badge) || it.is_category_best || isPointsFreebie(it) || (it.promo_type && it.promo_type !== 'standard');
    const hasGatedDealOnly = items.some(it => getItemRating(it) === 'deal_only' && isQualifyingDealItem(it));
    const hasGiveaway = items.some(it => getItemRating(it) === 'giveaway');
    const allHidden = items.length > 0 && items.every(it => getItemRating(it) === 'hide');
    const hasFreeGiveaway = items.some(it => getItemRating(it) === 'giveaway' && (it.price == null || it.price <= 0.25 || isPointsFreebie(it)));
    const isFrontPage = items.some(it => it.is_front_page);
    const page = items[0].page || 1;
    const category = items[0].category || 'Other';
    const department = items[0].department || getGroceryDepartment(items[0]);

    const title = synthesizeGroupTitle(items);
    const isMealDeal = groupId.startsWith('meal_deal_') || promoType === 'meal_deal' || title.toLowerCase().includes('meal deal');
    let anchorItem = null;
    if (isMealDeal && items.length > 0) {
      // Prioritize items with a positive purchase price (e.g. Ground Beef @ $5.99)
      const pricedItems = items.filter(it => (it.price || 0) > 0);
      if (pricedItems.length > 0) {
        anchorItem = pricedItems.reduce((prev, curr) => ((curr.price || 0) > (prev.price || 0) ? curr : prev), pricedItems[0]);
      } else {
        // If all items have 0 or null price, resolve the item mentioned in "buy this X"
        const fullPromo = items.map(it => it.raw_title || it.promo_detail || '').join(' ');
        const buyMatch = fullPromo.match(/buy this\s+([^,]+?)\s+get\s+(?:these|this)\s+free/i);
        if (buyMatch) {
          const buyTarget = buyMatch[1].trim().toLowerCase();
          const targetItem = items.find(it => it.name.toLowerCase().includes(buyTarget) || buyTarget.includes(it.name.toLowerCase()));
          if (targetItem) anchorItem = targetItem;
        }
      }
      if (!anchorItem) anchorItem = items[0];
    }

    let representativeDeal = anchorItem;
    if (!representativeDeal) {
      if (hasNewAtl) {
        representativeDeal = items.find(it => isNewAtl(it));
      } else if (hasMatchAtl) {
        representativeDeal = items.find(it => isMatchAtl(it));
      } else {
        representativeDeal = items[0];
      }
    }

    return {
      groupId,
      isMulti,
      isMealDeal,
      anchorItem,
      items,
      title,
      page,
      isFrontPage,
      category,
      department,
      brands,
      minPrice,
      maxPrice,
      minUnitPrice,
      maxUnitPrice,
      primaryUnitType,
      promoDetail,
      promoType,
      hasPointsFreebie,
      hasPointsDeal,
      hasNewAtl,
      hasMatchAtl,
      hasAtl,
      hasGreat,
      hasCatBest,
      hasLoved,
      hasDealOnly,
      hasGatedDealOnly,
      hasGiveaway,
      allHidden,
      hasFreeGiveaway,
      representativeDeal,
    };
  }

  function getAllGroups() {
    const groupsMap = new Map();
    allDeals.forEach(d => {
      const key = getGroupKey(d);
      if (!groupsMap.has(key)) {
        groupsMap.set(key, []);
      }
      const existingItems = groupsMap.get(key);
      // Deduplicate identical product instances inside the same group
      if (!existingItems.some(it => it.product_id === d.product_id && it.deal_id === d.deal_id)) {
        if (!existingItems.some(it => it.name === d.name && Math.abs((it.price || 0) - (d.price || 0)) < 0.01)) {
          existingItems.push(d);
        }
      }
    });

    // Merge any duplicate sub-ad groups that belong to a meal deal on the same page
    const mealDealKeyPrefix = 'meal_deal_';
    const mealDealGroups = [];
    groupsMap.forEach((items, key) => {
      if (key.startsWith(mealDealKeyPrefix)) {
        mealDealGroups.push({ key, items });
      }
    });

    if (mealDealGroups.length > 0) {
      const keysToDelete = [];
      groupsMap.forEach((items, key) => {
        if (key.startsWith(mealDealKeyPrefix)) return;
        for (const md of mealDealGroups) {
          const matchCount = items.filter(it =>
            md.items.some(mdItem => mdItem.name === it.name || (mdItem.product_id && mdItem.product_id === it.product_id))
          ).length;
          // If the items in this group are 70%+ identical to the meal deal bundle, merge into meal deal
          if (items.length > 0 && matchCount >= Math.min(3, items.length) && (matchCount / items.length) >= 0.7) {
            items.forEach(it => {
              if (!md.items.some(m => m.name === it.name && Math.abs((m.price || 0) - (it.price || 0)) < 0.01)) {
                md.items.push(it);
              }
            });
            keysToDelete.push(key);
            break;
          }
        }
      });
      keysToDelete.forEach(k => groupsMap.delete(k));
    }

    const groups = [];
    groupsMap.forEach((items, key) => {
      groups.push(buildGroupObject(key, items));
    });
    return groups;
  }

  // Initialize UI with fetched data
  function initData() {
    loadingState.style.display = 'none';
    allDeals.forEach(d => {
      d.department = getGroceryDepartment(d);
    });
    loadSavedShoppingList();
    loadSavedItemRatings();

    // Validity Date Display
    if (flyerMeta && flyerMeta.valid_from && flyerMeta.valid_to) {
      const fromObj = parseDateSafely(flyerMeta.valid_from);
      const toObj = parseDateSafely(flyerMeta.valid_to);
      if (fromObj && toObj) {
        const fromDate = fromObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const toDate = toObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        circularValidity.textContent = `${fromDate} – ${toDate}`;
      } else {
        circularValidity.textContent = 'Active Weekly Circular';
      }
    } else {
      circularValidity.textContent = 'Active Weekly Circular';
    }

    // Populate Stats Banner
    statTotalCount.textContent = allDeals.length;
    const atlCount = allDeals.filter(d => isAtlBadge(d.badge)).length;
    statAtlCount.textContent = atlCount;
    const frontCount = allDeals.filter(d => d.is_front_page).length;
    statFrontpageCount.textContent = frontCount;
    const catBestCount = allDeals.filter(d => d.is_category_best).length;
    statCatbestCount.textContent = catBestCount;

    // Build Categories
    buildCategoryPills();

    // Populate Rating Badges & Categorize Tab
    updateRatingBadgesCount();
    setupCategorizeTabEvents();

    // Render Initial View
    renderDeals();
  }

  // Build Categories Bar
  function buildCategoryPills() {
    const counts = {};
    allDeals.forEach(d => {
      const dept = d.department || getGroceryDepartment(d);
      counts[dept] = (counts[dept] || 0) + 1;
    });

    const sortedCategories = Object.keys(counts).sort((a, b) => {
      if (a === 'Other') return 1;
      if (b === 'Other') return -1;
      return counts[b] - counts[a];
    });

    categoryPillsContainer.innerHTML = '';

    // "All" Pill
    const allBtn = document.createElement('button');
    allBtn.className = `cat-pill ${activeCategory === 'ALL' ? 'active' : ''}`;
    allBtn.dataset.category = 'ALL';
    allBtn.textContent = `All Categories (${allDeals.length})`;
    allBtn.addEventListener('click', () => setCategory('ALL'));
    categoryPillsContainer.appendChild(allBtn);

    sortedCategories.forEach(cat => {
      const btn = document.createElement('button');
      btn.className = `cat-pill ${activeCategory === cat ? 'active' : ''}`;
      btn.dataset.category = cat;
      btn.textContent = `${cat} (${counts[cat]})`;
      btn.addEventListener('click', () => setCategory(cat));
      categoryPillsContainer.appendChild(btn);
    });
  }

  function setCategory(cat) {
    activeCategory = cat;
    document.querySelectorAll('.cat-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.category === cat);
    });
    renderDeals();
  }

  // Filtering & Sorting for Groups
  function getFilteredGroups() {
    const allGroups = getAllGroups();
    let filtered = [...allGroups];

    // Category / Department Filter
    if (activeCategory !== 'ALL') {
      filtered = filtered.filter(g =>
        g.items.some(d => (d.department || getGroceryDepartment(d)) === activeCategory)
      );
    }

    // Chip Filter
    if (activeFilter === 'atl') {
      filtered = filtered.filter(g => g.hasAtl);
    } else if (activeFilter === 'beat' || activeFilter === 'great') {
      filtered = filtered.filter(g => g.hasGreat);
    } else if (activeFilter === 'cycle') {
      filtered = filtered.filter(g =>
        g.items.some(d => /cycle|refresh/i.test(d.badge || ''))
      );
    } else if (activeFilter === 'firstseen') {
      filtered = filtered.filter(g =>
        g.items.some(d => /first/i.test(d.badge || ''))
      );
    } else if (activeFilter === 'hike') {
      filtered = filtered.filter(g =>
        g.items.some(d => /hike/i.test(d.badge || ''))
      );
    } else if (activeFilter === 'front') {
      filtered = filtered.filter(g => g.isFrontPage);
    } else if (activeFilter === 'catbest') {
      filtered = filtered.filter(g => g.hasCatBest);
    } else if (activeFilter === 'bogo') {
      filtered = filtered.filter(g =>
        g.items.some(d => (d.promo_type && d.promo_type !== 'standard') || (d.promo_detail && /bogo|buy/i.test(d.promo_detail)))
      );
    } else if (activeFilter === 'points') {
      filtered = filtered.filter(g =>
        g.items.some(d =>
          /points|freebie|reward/i.test(d.badge || '') ||
          (d.promo_type && d.promo_type.startsWith('points')) ||
          (d.promo_detail && /choice|points/i.test(d.promo_detail))
        )
      );
    } else if (activeFilter === 'favorites') {
      filtered = filtered.filter(g => g.hasLoved);
    } else if (activeFilter === 'deal_picks') {
      filtered = filtered.filter(g => g.hasDealOnly && g.hasGatedDealOnly);
    } else if (activeFilter === 'giveaways') {
      filtered = filtered.filter(g => g.hasGiveaway);
    } else if (activeFilter === 'hidden') {
      filtered = filtered.filter(g => g.items.some(it => getItemRating(it) === 'hide'));
    }

    // Default: unless searching or viewing hidden items, hide groups where ALL items are marked 'hide'
    if (activeFilter !== 'hidden' && !searchQuery.trim()) {
      filtered = filtered.filter(g => !g.allHidden);
    }

    // Search Filter (Smart word matching: all whitespace-separated keywords anywhere in any order)
    if (searchQuery.trim()) {
      const tokens = searchQuery.toLowerCase().trim().split(/\s+/).filter(Boolean);
      filtered = filtered.filter(g => {
        const groupHeader = `${g.title || ''} ${g.promoDetail || ''} ${(g.brands || []).join(' ')} ${g.department || ''} ${g.category || ''}`.toLowerCase();
        if (tokens.every(t => groupHeader.includes(t))) return true;

        const anyItemMatches = g.items.some(d => {
          const itemBlob = `${d.name || ''} ${d.brand || ''} ${d.department || ''} ${d.category || ''} ${d.promo_detail || ''}`.toLowerCase();
          return tokens.every(t => itemBlob.includes(t));
        });
        if (anyItemMatches) return true;

        const groupTotalBlob = `${groupHeader} ${g.items.map(d => `${d.name || ''} ${d.brand || ''} ${d.department || ''} ${d.category || ''} ${d.promo_detail || ''}`).join(' ')}`.toLowerCase();
        return tokens.every(t => groupTotalBlob.includes(t));
      });
    }

    // Sorting
    filtered.sort((a, b) => {
      if (activeSort === 'unit_price_asc') {
        const upA = a.minUnitPrice != null ? a.minUnitPrice : 999999;
        const upB = b.minUnitPrice != null ? b.minUnitPrice : 999999;
        return upA - upB;
      }
      if (activeSort === 'price_asc') {
        const pA = a.minPrice != null ? a.minPrice : 999999;
        const pB = b.minPrice != null ? b.minPrice : 999999;
        return pA - pB;
      }
      if (activeSort === 'price_desc') {
        const pA = a.maxPrice != null ? a.maxPrice : -1;
        const pB = b.maxPrice != null ? b.maxPrice : -1;
        return pB - pA;
      }
      if (activeSort === 'page_asc') {
        return (a.page || 1) - (b.page || 1);
      }
      if (activeSort === 'name_asc') {
        return (a.title || '').localeCompare(b.title || '');
      }

      // 'featured' default: ❤️ Favorites (+1000) > 🎁 Free Giveaways (+300) > 🎯 Qualifying Deal-Only (+250) > 5-Point Freebies (200) > ALL-TIME LOW (100) > High-Yield Points Deal (80) > Great Deal / Beat Avg (50) + Front page bonus (20)
      const lovedBonusA = a.hasLoved ? 1000 : (a.hasFreeGiveaway ? 300 : (a.hasGatedDealOnly ? 250 : 0));
      const lovedBonusB = b.hasLoved ? 1000 : (b.hasFreeGiveaway ? 300 : (b.hasGatedDealOnly ? 250 : 0));
      const scoreA = lovedBonusA + (a.hasPointsFreebie ? 200 : a.hasAtl ? 100 : a.hasPointsDeal ? 80 : a.hasGreat ? 50 : 0) + (a.isFrontPage ? 20 : 0);
      const scoreB = lovedBonusB + (b.hasPointsFreebie ? 200 : b.hasAtl ? 100 : b.hasPointsDeal ? 80 : b.hasGreat ? 50 : 0) + (b.isFrontPage ? 20 : 0);
      if (scoreA !== scoreB) return scoreB - scoreA;
      return (a.page || 1) - (b.page || 1);
    });

    return filtered;
  }

  // Flat deals filter (if groupByAd is disabled)
  function getFilteredDealsFlat() {
    let filtered = [...allDeals];

    if (activeCategory !== 'ALL') {
      filtered = filtered.filter(d => (d.department || getGroceryDepartment(d)) === activeCategory);
    }

    if (activeFilter === 'atl') {
      filtered = filtered.filter(d => isAtlBadge(d.badge));
    } else if (activeFilter === 'beat' || activeFilter === 'great') {
      filtered = filtered.filter(d => isGreatBadge(d.badge) || isAtlBadge(d.badge) || /beat/i.test(d.badge || ''));
    } else if (activeFilter === 'cycle') {
      filtered = filtered.filter(d => /cycle|refresh/i.test(d.badge || ''));
    } else if (activeFilter === 'firstseen') {
      filtered = filtered.filter(d => /first/i.test(d.badge || ''));
    } else if (activeFilter === 'hike') {
      filtered = filtered.filter(d => /hike/i.test(d.badge || ''));
    } else if (activeFilter === 'front') {
      filtered = filtered.filter(d => d.is_front_page);
    } else if (activeFilter === 'catbest') {
      filtered = filtered.filter(d => d.is_category_best);
    } else if (activeFilter === 'bogo') {
      filtered = filtered.filter(d => (d.promo_type && d.promo_type !== 'standard') || (d.promo_detail && /bogo|buy/i.test(d.promo_detail)));
    } else if (activeFilter === 'points') {
      filtered = filtered.filter(d =>
        /points|freebie|reward/i.test(d.badge || '') ||
        (d.promo_type && d.promo_type.startsWith('points')) ||
        (d.promo_detail && /choice|points/i.test(d.promo_detail))
      );
    } else if (activeFilter === 'favorites') {
      filtered = filtered.filter(d => getItemRating(d) === 'love');
    } else if (activeFilter === 'deal_picks') {
      filtered = filtered.filter(d => getItemRating(d) === 'deal_only' && (isAtlBadge(d.badge) || isGreatBadge(d.badge) || d.is_category_best || isPointsFreebie(d) || (d.promo_type && d.promo_type !== 'standard')));
    } else if (activeFilter === 'giveaways') {
      filtered = filtered.filter(d => getItemRating(d) === 'giveaway');
    } else if (activeFilter === 'hidden') {
      filtered = filtered.filter(d => getItemRating(d) === 'hide');
    }

    if (activeFilter !== 'hidden' && !searchQuery.trim()) {
      filtered = filtered.filter(d => getItemRating(d) !== 'hide');
    }

    if (searchQuery.trim()) {
      const tokens = searchQuery.toLowerCase().trim().split(/\s+/).filter(Boolean);
      filtered = filtered.filter(d => {
        const itemBlob = `${d.name || ''} ${d.brand || ''} ${d.department || ''} ${d.category || ''} ${d.promo_detail || ''}`.toLowerCase();
        return tokens.every(t => itemBlob.includes(t));
      });
    }

    filtered.sort((a, b) => {
      if (activeSort === 'unit_price_asc') {
        return (a.unit_price != null ? a.unit_price : 999999) - (b.unit_price != null ? b.unit_price : 999999);
      }
      if (activeSort === 'price_asc') {
        return (a.price != null ? a.price : 999999) - (b.price != null ? b.price : 999999);
      }
      if (activeSort === 'price_desc') {
        return (b.price != null ? b.price : -1) - (a.price != null ? a.price : -1);
      }
      if (activeSort === 'page_asc') {
        return (a.page || 1) - (b.page || 1);
      }
      if (activeSort === 'name_asc') {
        return (a.name || '').localeCompare(b.name || '');
      }
      const isQualifyingA = isAtlBadge(a.badge) || isGreatBadge(a.badge) || a.is_category_best || isPointsFreebie(a) || (a.promo_type && a.promo_type !== 'standard');
      const isQualifyingB = isAtlBadge(b.badge) || isGreatBadge(b.badge) || b.is_category_best || isPointsFreebie(b) || (b.promo_type && b.promo_type !== 'standard');
      const lovedBonusA = (getItemRating(a) === 'love') ? 1000 : ((getItemRating(a) === 'giveaway' && (a.price == null || a.price <= 0.25 || isPointsFreebie(a))) ? 300 : ((getItemRating(a) === 'deal_only' && isQualifyingA) ? 250 : 0));
      const lovedBonusB = (getItemRating(b) === 'love') ? 1000 : ((getItemRating(b) === 'giveaway' && (b.price == null || b.price <= 0.25 || isPointsFreebie(b))) ? 300 : ((getItemRating(b) === 'deal_only' && isQualifyingB) ? 250 : 0));
      const scoreA = lovedBonusA + (isPointsFreebie(a) ? 200 : isNewAtl(a) ? 120 : isMatchAtl(a) ? 100 : isAtlBadge(a.badge) ? 100 : isPointsDeal(a) ? 80 : isGreatBadge(a.badge) ? 50 : 0) + (a.is_front_page ? 20 : 0);
      const scoreB = lovedBonusB + (isPointsFreebie(b) ? 200 : isNewAtl(b) ? 120 : isMatchAtl(b) ? 100 : isAtlBadge(b.badge) ? 100 : isPointsDeal(b) ? 80 : isGreatBadge(b.badge) ? 50 : 0) + (b.is_front_page ? 20 : 0);
      if (scoreA !== scoreB) return scoreB - scoreA;
      return (a.page || 1) - (b.page || 1);
    });

    return filtered;
  }

  // =========================================================================
  // RENDERING ENGINE
  // =========================================================================

  function renderDeals() {
    if (groupByAd) {
      const groups = getFilteredGroups();
      const totalItemCount = groups.reduce((acc, g) => acc + g.items.length, 0);

      resultsCountText.textContent = `Showing ${groups.length} ${groups.length === 1 ? 'circular ad' : 'circular ads'} (${totalItemCount} ${totalItemCount === 1 ? 'item' : 'items'})`;
      const hasFilters = activeCategory !== 'ALL' || activeFilter !== null || searchQuery.trim() !== '';
      resetFiltersBtn.style.display = hasFilters ? 'inline' : 'none';

      if (groups.length === 0) {
        dealsGrid.style.display = 'none';
        dealsTableContainer.style.display = 'none';
        emptyState.style.display = 'block';
        return;
      }

      emptyState.style.display = 'none';

      if (viewMode === 'grid') {
        dealsGrid.style.display = 'grid';
        dealsTableContainer.style.display = 'none';
        renderGroupedGridView(groups);
      } else {
        dealsGrid.style.display = 'none';
        dealsTableContainer.style.display = 'block';
        renderGroupedTableView(groups);
      }
    } else {
      const deals = getFilteredDealsFlat();
      resultsCountText.textContent = `Showing ${deals.length} ${deals.length === 1 ? 'deal' : 'deals'}`;
      const hasFilters = activeCategory !== 'ALL' || activeFilter !== null || searchQuery.trim() !== '';
      resetFiltersBtn.style.display = hasFilters ? 'inline' : 'none';

      if (deals.length === 0) {
        dealsGrid.style.display = 'none';
        dealsTableContainer.style.display = 'none';
        emptyState.style.display = 'block';
        return;
      }

      emptyState.style.display = 'none';

      if (viewMode === 'grid') {
        dealsGrid.style.display = 'grid';
        dealsTableContainer.style.display = 'none';
        renderFlatGridView(deals);
      } else {
        dealsGrid.style.display = 'none';
        dealsTableContainer.style.display = 'block';
        renderFlatTableView(deals);
      }
    }

    updateExpandAllButtonState();
  }

  // Render Grouped Grid View
  function renderGroupedGridView(groups) {
    dealsGrid.innerHTML = groups.map(g => {
      if (g.isMulti) {
        return renderMultiItemGroupCard(g);
      } else {
        return renderSingleItemCard(g.items[0]);
      }
    }).join('');
  }

  function renderMultiItemGroupCard(g) {
    const isExpanded = expandedGroupIds.has(g.groupId);
    const isAllInList = g.items.every(it => shoppingList.some(s => s.id === it.deal_id));
    const someInList = g.items.some(it => shoppingList.some(s => s.id === it.deal_id));
    const rep = g.representativeDeal;
    let badgeHtml = getBadgeHtml(rep);
    if (g.hasLoved && !badgeHtml.includes('user-loved')) {
      badgeHtml = `<span class="deal-badge user-loved">❤️ FAVORITE INCLUDED</span> ${badgeHtml}`;
    } else if (g.hasGiveaway && !badgeHtml.includes('user-giveaway')) {
      badgeHtml = `<span class="deal-badge user-giveaway">🎁 GIVEAWAY</span> ${badgeHtml}`;
    } else if (g.allHidden && !badgeHtml.includes('user-hidden')) {
      badgeHtml = `<span class="deal-badge user-hidden">🚫 ALL HIDDEN</span> ${badgeHtml}`;
    }

    // Price range display
    let priceDisplay = '—';
    let unitPriceDisplay = '';
    const isGroupFreebie = g.hasPointsFreebie || isPointsFreebie(rep) || g.items.every(it => isPointsFreebie(it));
    const repPtsInfo = getPointsExtrapolatedInfo(rep) || (g.items[0] ? getPointsExtrapolatedInfo(g.items[0]) : null);

    if (g.isMealDeal && g.anchorItem && g.anchorItem.price != null) {
      priceDisplay = formatMoney(g.anchorItem.price);
      if (g.anchorItem.unit_price != null) {
        unitPriceDisplay = formatUnitPrice(g.anchorItem.unit_price, g.anchorItem.unit_type);
      }
    } else if (isGroupFreebie) {
      priceDisplay = '<span class="free-price">FREE</span>';
      if (repPtsInfo && repPtsInfo.yieldTag) {
        unitPriceDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(repPtsInfo.yieldTag)}</span>`;
      }
    } else if (repPtsInfo && repPtsInfo.pts && (g.minPrice == null || g.minPrice === 0 || g.items.every(it => isPointsRedemption(it) || isPointsDeal(it)))) {
      priceDisplay = `<span class="points-price">${repPtsInfo.pts} pts</span>`;
      if (repPtsInfo.yieldTag) {
        unitPriceDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(repPtsInfo.yieldTag)}</span>`;
      }
    } else if (g.minPrice != null && g.maxPrice != null) {
      if (Math.abs(g.minPrice - g.maxPrice) < 0.01) {
        priceDisplay = formatMoney(g.minPrice);
      } else {
        priceDisplay = `${formatMoney(g.minPrice)} – ${formatMoney(g.maxPrice)}`;
      }
      if (g.minUnitPrice != null && g.maxUnitPrice != null) {
        if (Math.abs(g.minUnitPrice - g.maxUnitPrice) < 0.005) {
          unitPriceDisplay = formatUnitPrice(g.minUnitPrice, g.primaryUnitType);
        } else {
          unitPriceDisplay = `$${g.minUnitPrice.toFixed(2)} – $${g.maxUnitPrice.toFixed(2)}/${g.primaryUnitType || 'unit'}`;
        }
      }
    }

    // Promo details note
    let promoDetailHtml = '';
    if (g.isMealDeal && g.anchorItem) {
      const anchorClean = escapeHtml(g.anchorItem.name.split(' - ')[0]);
      const priceTag = (g.anchorItem.price != null && g.anchorItem.price > 0) ? ` (${formatMoney(g.anchorItem.price)}${g.anchorItem.unit_price ? `/${g.anchorItem.unit_type || 'lb'}` : ''})` : '';
      promoDetailHtml = `<div class="meal-deal-qualifier-note">✨ Buy <strong>${anchorClean}</strong>${priceTag}, get bundled items <strong>FREE</strong></div>`;
    } else if (g.promoDetail) {
      promoDetailHtml = `<div class="promo-detail-note">🏷️ ${escapeHtml(g.promoDetail)}</div>`;
    }

    let historyHtml = '';
    if (rep) {
      if (rep.historical_min && rep.price && rep.historical_min > rep.price) {
        historyHtml = `<div class="history-summary">Best price recorded (Past low was <strong>${formatMoney(rep.historical_min)}</strong>)</div>`;
      } else if (rep.historical_min && rep.historical_avg && rep.historical_min < rep.price) {
        historyHtml = `<div class="history-summary">Avg: <strong>${formatMoney(rep.historical_avg)}</strong> • Min: <strong>${formatMoney(rep.historical_min)}</strong></div>`;
      } else if (isAtlBadge(rep.badge) && rep.historical_avg) {
        historyHtml = `<div class="history-summary">Best price recorded (Avg: <strong>${formatMoney(rep.historical_avg)}</strong>)</div>`;
      }
    }

    // Brand display string
    const brandStr = g.brands.length > 0 ? g.brands.slice(0, 4).join(' • ') + (g.brands.length > 4 ? ' • ...' : '') : '';

    // Variety preview chips (when collapsed)
    let previewChipsHtml = '';
    if (!isExpanded) {
      const topItems = g.items.slice(0, 4);
      const remaining = g.items.length - topItems.length;
      previewChipsHtml = `
        <div class="group-varieties-preview" title="Items included in this ad promotion">
          ${topItems.map(it => {
            const r = getItemRating(it);
            const prefix = r === 'love' ? '❤️ ' : (r === 'deal_only' ? '🎯 ' : (r === 'giveaway' ? '🎁 ' : ''));
            return `<span class="variety-chip">${prefix}${escapeHtml(it.name.split(' - ')[0])}</span>`;
          }).join(' ')}
          ${remaining > 0 ? `<span class="variety-chip more">+${remaining} more varieties</span>` : ''}
        </div>
      `;
    }

    // Expanded child items list
    let expandedSectionHtml = '';
    if (isExpanded) {
      expandedSectionHtml = `
        <div class="group-expanded-container">
          <div class="group-expanded-title">
            <span>Varieties & Items (${g.items.length}):</span>
            <span style="font-size:0.7rem; color:var(--primary-700); cursor:pointer;" onclick="window.__toggleGroupExpand('${g.groupId}')">▲ Collapse</span>
          </div>
          <div class="group-items-list">
            ${g.items.map(item => {
              const itemInList = shoppingList.some(s => s.id === item.deal_id);
              const isItemFreebie = isPointsFreebie(item);
              const isItemDeal = isPointsDeal(item);
              const isItemRedeem = isPointsRedemption(item);
              const itemPtsInfo = (isItemFreebie || isItemDeal || isItemRedeem) ? getPointsExtrapolatedInfo(item) : null;
              const itemUnit = itemPtsInfo && itemPtsInfo.pts ? `🪙 ${itemPtsInfo.pts} pts` : formatUnitPrice(item.unit_price, item.unit_type);
              let itemBadge = '';
              if (isNewAtl(item)) {
                itemBadge = '<span class="deal-badge atl new-atl" style="font-size:0.65rem; padding:1px 4px;">NEW ATL</span>';
              } else if (isMatchAtl(item)) {
                itemBadge = '<span class="deal-badge match-atl" style="font-size:0.65rem; padding:1px 4px;">MATCH ATL</span>';
              } else if (isAtlBadge(item.badge)) {
                itemBadge = '<span class="deal-badge atl" style="font-size:0.65rem; padding:1px 4px;">ATL</span>';
              }
              const isMain = g.isMealDeal && g.anchorItem && (item.deal_id === g.anchorItem.deal_id || item.name === g.anchorItem.name);
              let itemPriceHtml = `<span class="group-item-price">${formatMoney(item.price)}</span>`;
              let itemRoleBadge = '';
              if (isItemFreebie) {
                itemRoleBadge = '<span class="deal-badge points-freebie" style="font-size:0.65rem; padding:1px 4px; margin-right:4px;">🪙 FREE w/ Points</span>';
                itemPriceHtml = `<span class="group-item-price free-price" style="color:#7e22ce; font-weight:800;">FREE</span>`;
              } else if (isItemDeal) {
                itemRoleBadge = '<span class="deal-badge points-deal" style="font-size:0.65rem; padding:1px 4px; margin-right:4px;">🪙 High-Yield</span>';
                itemPriceHtml = `<span class="group-item-price points-price">${itemPtsInfo && itemPtsInfo.pts ? `${itemPtsInfo.pts} pts` : formatMoney(item.price)}</span>`;
              } else if (isItemRedeem) {
                itemRoleBadge = '<span class="deal-badge points-redemption" style="font-size:0.65rem; padding:1px 4px; margin-right:4px;">🪙 Redeem</span>';
                itemPriceHtml = `<span class="group-item-price points-price">${itemPtsInfo && itemPtsInfo.pts ? `${itemPtsInfo.pts} pts` : formatMoney(item.price)}</span>`;
              } else if (g.isMealDeal) {
                if (isMain) {
                  itemRoleBadge = '<span class="deal-badge" style="font-size:0.65rem; background:#dbeafe; color:#1e40af; margin-right:4px;">Main Item</span>';
                  itemPriceHtml = `<span class="group-item-price" style="font-weight:700;">${formatMoney(item.price)}</span>`;
                } else {
                  itemRoleBadge = '<span class="deal-badge" style="font-size:0.65rem; background:#dcfce7; color:#166534; margin-right:4px;">FREE with purchase</span>';
                  itemPriceHtml = `<span class="group-item-price" style="color:#059669; font-weight:700;">$0.00 <span style="text-decoration:line-through; color:var(--slate-400); font-weight:400; font-size:0.75rem;">${formatMoney(item.price)}</span></span>`;
                }
              }

              const rating = getItemRating(item);
              let ratingTagHtml = '';
              if (rating === 'love') {
                ratingTagHtml = '<span class="item-rating-tag rating-love">❤️ Favorite</span>';
              } else if (rating === 'deal_only') {
                ratingTagHtml = '<span class="item-rating-tag rating-deal-only">🎯 Deal Only</span>';
              } else if (rating === 'giveaway') {
                ratingTagHtml = '<span class="item-rating-tag rating-giveaway">🎁 Giveaway</span>';
              } else if (rating === 'hide') {
                ratingTagHtml = '<span class="item-rating-tag rating-hide">🚫 Hidden</span>';
              }

              return `
                <div class="group-item-row" data-deal-id="${item.deal_id}" data-product-key="${getProductKey(item)}">
                  <div class="group-item-info">
                    <div class="group-item-name">${escapeHtml(item.name)}</div>
                    <div class="group-item-sub">
                      ${itemRoleBadge}
                      ${item.brand ? `<span>${escapeHtml(item.brand)}</span>` : ''}
                      ${itemUnit ? `<span>• ${itemUnit}</span>` : ''}
                      ${itemBadge}
                      ${ratingTagHtml}
                    </div>
                  </div>
                  <div class="group-item-actions">
                    <div class="item-rating-group" title="Rate your preference for this specific item">
                      <button class="btn-rate-icon ${rating === 'love' ? 'active-love' : ''}" data-rate="love" onclick="window.__setItemRating(${item.deal_id}, 'love')" title="❤️ Love / Favorite (bubbles to top)">❤️</button>
                      <button class="btn-rate-icon ${rating === 'deal_only' ? 'active-deal-only' : ''}" data-rate="deal_only" onclick="window.__setItemRating(${item.deal_id}, 'deal_only')" title="🎯 Deal Only (bubbles when ATL or great discount)">🎯</button>
                      <button class="btn-rate-icon ${rating === 'giveaway' ? 'active-giveaway' : ''}" data-rate="giveaway" onclick="window.__setItemRating(${item.deal_id}, 'giveaway')" title="🎁 Giveaway (prioritize if free)">🎁</button>
                      <button class="btn-rate-icon ${rating === 'hide' ? 'active-hide' : ''}" data-rate="hide" onclick="window.__setItemRating(${item.deal_id}, 'hide')" title="🚫 Hide / Never show">🚫</button>
                    </div>
                    ${itemPriceHtml}
                    <button class="btn-item-add ${itemInList ? 'in-list' : ''}" onclick="window.__toggleShoppingItem(${item.deal_id})">
                      ${itemInList ? '✓ In List' : '+ List'}
                    </button>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }

    const cardAtlClass = g.hasNewAtl ? 'is-atl' : (g.hasMatchAtl ? 'is-match-atl' : (g.hasAtl ? 'is-atl' : ''));
    return `
      <div class="deal-card is-group ${cardAtlClass}" data-group-id="${g.groupId}">
        <div>
          <div class="card-top">
            <div class="badge-row">
              ${badgeHtml}
              <span class="deal-badge group-count">📦 ${g.items.length} ${g.items.length === 1 ? 'Item' : 'Varieties'}</span>
            </div>
            <span class="page-indicator">Pg ${g.page || 1}</span>
          </div>

          ${brandStr ? `<div class="product-brand">${escapeHtml(brandStr)}</div>` : ''}
          <h3 class="product-name">${escapeHtml(g.title)}</h3>

          <div class="price-container">
            <span class="current-price">${priceDisplay}</span>
            ${unitPriceDisplay ? `<span class="unit-price-tag">${unitPriceDisplay}</span>` : ''}
          </div>

          ${promoDetailHtml}
          ${historyHtml}
          ${previewChipsHtml}
        </div>

        <div class="card-action-row">
          <button class="btn-expand-group ${isExpanded ? 'expanded' : ''}" onclick="window.__toggleGroupExpand('${g.groupId}')">
            ${isExpanded ? '▲ Hide Individual Items' : `▼ View All ${g.items.length} Items`}
          </button>
          <button class="btn-add-list ${isAllInList ? 'in-list' : ''}" onclick="window.__toggleGroupAll('${g.groupId}')">
            ${isAllInList ? `✓ All ${g.items.length} In List` : someInList ? `+ Add All (${g.items.length})` : `+ Add All (${g.items.length})`}
          </button>
        </div>

        ${expandedSectionHtml}
      </div>
    `;
  }

  function renderSingleItemCard(d) {
    const isInList = shoppingList.some(item => item.id === d.deal_id);
    const isAtl = isAtlBadge(d.badge);
    const isFreebie = isPointsFreebie(d);
    const isDeal = isPointsDeal(d);
    const isRedeem = isPointsRedemption(d);
    const ptsInfo = (isFreebie || isDeal || isRedeem) ? getPointsExtrapolatedInfo(d) : null;
    const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
    const badgeHtml = getBadgeHtml(d);
    const dRating = getItemRating(d);
    const isRateOpen = singleRateExpandedDealIds.has(d.deal_id);
    const rateBtnText = dRating === 'love' ? '❤️ Favorite' : (dRating === 'giveaway' ? '🎁 Giveaway' : (dRating === 'hide' ? '🚫 Hidden' : '⭐ Rate'));
    const rateBtnClass = dRating === 'love' ? 'active-loved' : (dRating === 'giveaway' ? 'active-giveaway' : (dRating === 'hide' ? 'active-hidden' : ''));

    let priceDisplayHtml = `<span class="current-price">${formatMoney(d.price)}</span>`;
    let unitDisplayHtml = unitStr ? `<span class="unit-price-tag">${unitStr}</span>` : '';

    if (isFreebie) {
      priceDisplayHtml = `<span class="current-price free-price">FREE</span>`;
      if (ptsInfo && ptsInfo.yieldTag) {
        unitDisplayHtml = `<span class="unit-price-tag points-yield-tag">${escapeHtml(ptsInfo.yieldTag)}</span>`;
      }
    } else if (ptsInfo && ptsInfo.pts && (isDeal || isRedeem || d.price == null || d.price === 0)) {
      priceDisplayHtml = `<span class="current-price points-price">${ptsInfo.pts} pts</span>`;
      if (ptsInfo.yieldTag) {
        unitDisplayHtml = `<span class="unit-price-tag points-yield-tag">${escapeHtml(ptsInfo.yieldTag)}</span>`;
      }
    }

    let promoDetailHtml = '';
    if (d.promo_detail) {
      promoDetailHtml = `<div class="promo-detail-note">🏷️ ${escapeHtml(d.promo_detail)}</div>`;
    }

    let historyHtml = '';
    if (d.historical_min && d.historical_avg && d.historical_min < d.price) {
      historyHtml = `<div class="history-summary">Avg: <strong>${formatMoney(d.historical_avg)}</strong> • Min: <strong>${formatMoney(d.historical_min)}</strong></div>`;
    } else if (isAtl && d.historical_avg) {
      historyHtml = `<div class="history-summary">Best price recorded (Avg: <strong>${formatMoney(d.historical_avg)}</strong>)</div>`;
    }

    const cardAtlClass = isNewAtl(d) ? 'is-atl' : (isMatchAtl(d) ? 'is-match-atl' : (isAtl ? 'is-atl' : ''));

    return `
      <div class="deal-card ${cardAtlClass}" data-id="${d.deal_id}" data-product-key="${getProductKey(d)}">
        <div>
          <div class="card-top">
            <div class="badge-row">
              ${badgeHtml}
            </div>
            <span class="page-indicator">Pg ${d.page || 1}</span>
          </div>

          ${d.brand ? `<div class="product-brand">${escapeHtml(d.brand)}</div>` : ''}
          <h3 class="product-name">${escapeHtml(d.name)}</h3>

          <div class="price-container">
            ${priceDisplayHtml}
            ${unitDisplayHtml}
          </div>

          ${promoDetailHtml}
          ${historyHtml}
        </div>

        <div class="card-action-row">
          <button class="btn-rate-toggle ${rateBtnClass}" onclick="window.__toggleSingleRate(${d.deal_id})" title="Rate item preference">
            ${rateBtnText}
          </button>
          <button class="btn-add-list ${isInList ? 'in-list' : ''}" onclick="window.__toggleShoppingItem(${d.deal_id})">
            ${isInList ? '✓ In List' : '+ Add to List'}
          </button>
        </div>

        ${isRateOpen ? `
          <div class="single-card-rating-drawer">
            <span class="drawer-label">Preference:</span>
            <div class="item-rating-group">
              <button class="btn-rate-icon ${dRating === 'love' ? 'active-love' : ''}" data-rate="love" onclick="window.__setItemRating(${d.deal_id}, 'love')" title="❤️ Love / Favorite (bubbles to top)">❤️ Love</button>
              <button class="btn-rate-icon ${dRating === 'deal_only' ? 'active-deal-only' : ''}" data-rate="deal_only" onclick="window.__setItemRating(${d.deal_id}, 'deal_only')" title="🎯 Deal Only (bubbles when ATL or great discount)">🎯 Deal Only</button>
              <button class="btn-rate-icon ${dRating === 'giveaway' ? 'active-giveaway' : ''}" data-rate="giveaway" onclick="window.__setItemRating(${d.deal_id}, 'giveaway')" title="🎁 Giveaway (prioritize if free)">🎁 Giveaway</button>
              <button class="btn-rate-icon ${dRating === 'hide' ? 'active-hide' : ''}" data-rate="hide" onclick="window.__setItemRating(${d.deal_id}, 'hide')" title="🚫 Hide">🚫 Hide</button>
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  // Render Grouped Table View
  function renderGroupedTableView(groups) {
    dealsTableBody.innerHTML = groups.map(g => {
      if (g.isMulti) {
        const isExpanded = expandedGroupIds.has(g.groupId);
        const isAllInList = g.items.every(it => shoppingList.some(s => s.id === it.deal_id));
        const isGroupFreebie = g.hasPointsFreebie || isPointsFreebie(g.representativeDeal) || g.items.every(it => isPointsFreebie(it));
        const repPts = getPointsExtrapolatedInfo(g.representativeDeal) || (g.items[0] ? getPointsExtrapolatedInfo(g.items[0]) : null);
        const badgeHtml = getBadgeHtml(g.representativeDeal);
        let priceDisplay = formatMoney(g.minPrice);
        let unitDisplay = formatUnitPrice(g.minUnitPrice, g.primaryUnitType);

        if (g.isMealDeal && g.anchorItem && g.anchorItem.price != null) {
          priceDisplay = formatMoney(g.anchorItem.price);
        } else if (isGroupFreebie) {
          priceDisplay = `<span class="free-price" style="font-size:1.1rem;">FREE</span>`;
          if (repPts && repPts.yieldTag) {
            unitDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(repPts.yieldTag)}</span>`;
          }
        } else if (repPts && repPts.pts && (g.minPrice == null || g.minPrice === 0 || g.items.every(it => isPointsRedemption(it) || isPointsDeal(it)))) {
          priceDisplay = `<span class="points-price" style="font-size:1.1rem;">${repPts.pts} pts</span>`;
          if (repPts.yieldTag) {
            unitDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(repPts.yieldTag)}</span>`;
          }
        } else if (g.minPrice != null && g.maxPrice != null && Math.abs(g.minPrice - g.maxPrice) >= 0.01) {
          priceDisplay = `${formatMoney(g.minPrice)} – ${formatMoney(g.maxPrice)}`;
        }

        if (g.isMealDeal && g.anchorItem && g.anchorItem.unit_price != null) {
          unitDisplay = formatUnitPrice(g.anchorItem.unit_price, g.anchorItem.unit_type);
        } else if (!isGroupFreebie && g.minUnitPrice != null && g.maxUnitPrice != null && Math.abs(g.minUnitPrice - g.maxUnitPrice) >= 0.005) {
          unitDisplay = `$${g.minUnitPrice.toFixed(2)} – $${g.maxUnitPrice.toFixed(2)}/${g.primaryUnitType || 'unit'}`;
        }

        const tablePriceTag = (g.anchorItem && g.anchorItem.price != null && g.anchorItem.price > 0) ? ` (${formatMoney(g.anchorItem.price)}${g.anchorItem.unit_price ? `/${g.anchorItem.unit_type || 'lb'}` : ''})` : '';
        const promoText = g.isMealDeal && g.anchorItem ? `✨ Buy ${escapeHtml(g.anchorItem.name.split(' - ')[0])}${tablePriceTag}, Get Bundled Items FREE` : g.promoDetail;

        const parentRow = `
          <tr class="table-group-header-row">
            <td><span class="page-indicator">Pg ${g.page || 1}</span></td>
            <td>
              <div style="display:flex; align-items:center; gap:8px;">
                <button class="btn-table-expand" onclick="window.__toggleGroupExpand('${g.groupId}')">
                  ${isExpanded ? '▲' : '▼'} ${g.items.length} items
                </button>
                <strong>${escapeHtml(g.title)}</strong>
              </div>
              ${g.brands.length ? `<div style="font-size:0.75rem; color:var(--slate-500); text-transform:uppercase; margin-left:32px;">${escapeHtml(g.brands.join(', '))}</div>` : ''}
            </td>
            <td><span class="cat-pill" style="font-size:0.75rem; padding:2px 6px;">${escapeHtml(g.department || g.category || 'Other')}</span></td>
            <td><strong style="font-size:1.1rem; color:var(--slate-900);">${priceDisplay}</strong></td>
            <td>${unitDisplay ? (unitDisplay.startsWith('<span') ? unitDisplay : `<span class="unit-price-tag">${unitDisplay}</span>`) : '—'}</td>
            <td>
              ${badgeHtml}
              ${promoText ? `<div style="font-size:0.75rem; color:var(--primary-700); font-weight:600; margin-top:2px;">🏷️ ${escapeHtml(promoText)}</div>` : ''}
            </td>
            <td>
              <button class="btn-add-list ${isAllInList ? 'in-list' : ''}" style="padding:6px 10px; font-size:0.75rem;" onclick="window.__toggleGroupAll('${g.groupId}')">
                ${isAllInList ? '✓ All In' : `+ All (${g.items.length})`}
              </button>
            </td>
          </tr>
        `;

        const childRows = g.items.map(item => {
          const itemInList = shoppingList.some(s => s.id === item.deal_id);
          const isItemFreebie = isPointsFreebie(item);
          const isItemDeal = isPointsDeal(item);
          const isItemRedeem = isPointsRedemption(item);
          const itemPtsInfo = (isItemFreebie || isItemDeal || isItemRedeem) ? getPointsExtrapolatedInfo(item) : null;
          const itemUnit = itemPtsInfo && itemPtsInfo.pts ? `🪙 ${itemPtsInfo.pts} pts` : formatUnitPrice(item.unit_price, item.unit_type);
          let itemBadge = '';
          if (isNewAtl(item)) {
            itemBadge = '<span class="deal-badge atl new-atl" style="font-size:0.65rem; padding:1px 4px;">NEW ATL</span>';
          } else if (isMatchAtl(item)) {
            itemBadge = '<span class="deal-badge match-atl" style="font-size:0.65rem; padding:1px 4px;">MATCH ATL</span>';
          } else if (isAtlBadge(item.badge)) {
            itemBadge = '<span class="deal-badge atl" style="font-size:0.65rem; padding:1px 4px;">ATL</span>';
          }
          const isMain = g.isMealDeal && g.anchorItem && (item.deal_id === g.anchorItem.deal_id || item.name === g.anchorItem.name);
          let priceCell = `<strong>${formatMoney(item.price)}</strong>`;
          let badgeCell = itemBadge;

          if (isItemFreebie) {
            badgeCell = `<span class="deal-badge points-freebie" style="font-size:0.65rem; padding:1px 4px;">🪙 FREE w/ Points</span> ${itemBadge}`;
            priceCell = `<strong class="free-price" style="color:#7e22ce;">FREE</strong>`;
          } else if (isItemDeal) {
            badgeCell = `<span class="deal-badge points-deal" style="font-size:0.65rem; padding:1px 4px;">🪙 High-Yield</span> ${itemBadge}`;
            priceCell = `<strong class="points-price">${itemPtsInfo && itemPtsInfo.pts ? `${itemPtsInfo.pts} pts` : formatMoney(item.price)}</strong>`;
          } else if (isItemRedeem) {
            badgeCell = `<span class="deal-badge points-redemption" style="font-size:0.65rem; padding:1px 4px;">🪙 Redeem</span> ${itemBadge}`;
            priceCell = `<strong class="points-price">${itemPtsInfo && itemPtsInfo.pts ? `${itemPtsInfo.pts} pts` : formatMoney(item.price)}</strong>`;
          } else if (g.isMealDeal) {
            if (isMain) {
              badgeCell = `<span class="deal-badge" style="font-size:0.65rem; background:#dbeafe; color:#1e40af;">Main Item</span> ${itemBadge}`;
            } else {
              badgeCell = `<span class="deal-badge" style="font-size:0.65rem; background:#dcfce7; color:#166534;">FREE with purchase</span> ${itemBadge}`;
              priceCell = `<strong style="color:#059669;">$0.00</strong> <span style="text-decoration:line-through; color:var(--slate-400); font-size:0.75rem;">${formatMoney(item.price)}</span>`;
            }
          }

          const rating = getItemRating(item);
          return `
            <tr class="table-child-row ${isExpanded ? '' : 'collapsed'}">
              <td></td>
              <td style="padding-left:36px;">
                <span>${escapeHtml(item.name)}</span>
                ${item.brand ? `<span style="font-size:0.7rem; color:var(--slate-400); margin-left:6px;">(${escapeHtml(item.brand)})</span>` : ''}
              </td>
              <td><span style="font-size:0.75rem; color:var(--slate-500);">${escapeHtml(item.category && item.category !== 'Other' ? item.category : (item.department || ''))}</span></td>
              <td>${priceCell}</td>
              <td>${itemUnit ? `<span class="unit-price-tag" style="font-size:0.75rem;">${itemUnit}</span>` : '—'}</td>
              <td>${badgeCell}</td>
              <td>
                <div style="display:inline-flex; align-items:center; gap:6px;">
                  <div class="item-rating-group" title="Rate this item preference">
                    <button class="btn-rate-icon ${rating === 'love' ? 'active-love' : ''}" onclick="window.__setItemRating(${item.deal_id}, 'love')" title="❤️ Love">❤️</button>
                    <button class="btn-rate-icon ${rating === 'deal_only' ? 'active-deal-only' : ''}" onclick="window.__setItemRating(${item.deal_id}, 'deal_only')" title="🎯 Deal Only">🎯</button>
                    <button class="btn-rate-icon ${rating === 'giveaway' ? 'active-giveaway' : ''}" onclick="window.__setItemRating(${item.deal_id}, 'giveaway')" title="🎁 Giveaway">🎁</button>
                    <button class="btn-rate-icon ${rating === 'hide' ? 'active-hide' : ''}" onclick="window.__setItemRating(${item.deal_id}, 'hide')" title="🚫 Hide">🚫</button>
                  </div>
                  <button class="btn-item-add ${itemInList ? 'in-list' : ''}" onclick="window.__toggleShoppingItem(${item.deal_id})">
                    ${itemInList ? '✓ In' : '+ Add'}
                  </button>
                </div>
              </td>
            </tr>
          `;
        }).join('');

        return parentRow + childRows;
      } else {
        const d = g.items[0];
        const isInList = shoppingList.some(item => item.id === d.deal_id);
        const isFreebie = isPointsFreebie(d);
        const isDeal = isPointsDeal(d);
        const isRedeem = isPointsRedemption(d);
        const ptsInfo = (isFreebie || isDeal || isRedeem) ? getPointsExtrapolatedInfo(d) : null;
        const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
        const badgeHtml = getBadgeHtml(d);
        let priceDisplay = `<strong style="font-size:1.1rem; color:var(--slate-900);">${formatMoney(d.price)}</strong>`;
        let unitDisplay = unitStr ? `<span class="unit-price-tag">${unitStr}</span>` : '—';

        if (isFreebie) {
          priceDisplay = `<strong class="free-price" style="font-size:1.1rem;">FREE</strong>`;
          if (ptsInfo && ptsInfo.yieldTag) {
            unitDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(ptsInfo.yieldTag)}</span>`;
          }
        } else if (ptsInfo && ptsInfo.pts && (isDeal || isRedeem || d.price == null || d.price === 0)) {
          priceDisplay = `<strong class="points-price" style="font-size:1.1rem;">${ptsInfo.pts} pts</strong>`;
          if (ptsInfo.yieldTag) {
            unitDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(ptsInfo.yieldTag)}</span>`;
          }
        }

        return `
          <tr>
            <td><span class="page-indicator">Pg ${d.page || 1}</span></td>
            <td>
              <strong>${escapeHtml(d.name)}</strong>
              ${d.brand ? `<div style="font-size:0.75rem; color:var(--slate-500); text-transform:uppercase;">${escapeHtml(d.brand)}</div>` : ''}
            </td>
            <td><span class="cat-pill" style="font-size:0.75rem; padding:2px 6px;">${escapeHtml(d.department || d.category || 'Other')}</span></td>
            <td>${priceDisplay}</td>
            <td>${unitDisplay}</td>
            <td>
              ${badgeHtml}
              <div style="font-size:0.75rem; color:var(--slate-500); margin-top:2px;">${escapeHtml(d.analysis || '')}</div>
            </td>
            <td>
              <button class="btn-add-list ${isInList ? 'in-list' : ''}" style="padding:6px 10px; font-size:0.75rem;" onclick="window.__toggleShoppingItem(${d.deal_id})">
                ${isInList ? '✓ In List' : '+ Add'}
              </button>
            </td>
          </tr>
        `;
      }
    }).join('');
  }

  // Flat rendering fallbacks
  function renderFlatGridView(deals) {
    dealsGrid.innerHTML = deals.map(d => renderSingleItemCard(d)).join('');
  }

  function renderFlatTableView(deals) {
    dealsTableBody.innerHTML = deals.map(d => {
      const isInList = shoppingList.some(item => item.id === d.deal_id);
      const isFreebie = isPointsFreebie(d);
      const isDeal = isPointsDeal(d);
      const isRedeem = isPointsRedemption(d);
      const ptsInfo = (isFreebie || isDeal || isRedeem) ? getPointsExtrapolatedInfo(d) : null;
      const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
      const badgeHtml = getBadgeHtml(d);
      let priceDisplay = `<strong style="font-size:1.1rem; color:var(--slate-900);">${formatMoney(d.price)}</strong>`;
      let unitDisplay = unitStr ? `<span class="unit-price-tag">${unitStr}</span>` : '—';

      if (isFreebie) {
        priceDisplay = `<strong class="free-price" style="font-size:1.1rem;">FREE</strong>`;
        if (ptsInfo && ptsInfo.yieldTag) {
          unitDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(ptsInfo.yieldTag)}</span>`;
        }
      } else if (ptsInfo && ptsInfo.pts && (isDeal || isRedeem || d.price == null || d.price === 0)) {
        priceDisplay = `<strong class="points-price" style="font-size:1.1rem;">${ptsInfo.pts} pts</strong>`;
        if (ptsInfo.yieldTag) {
          unitDisplay = `<span class="unit-price-tag points-yield-tag">${escapeHtml(ptsInfo.yieldTag)}</span>`;
        }
      }

      return `
        <tr>
          <td><span class="page-indicator">Pg ${d.page || 1}</span></td>
          <td>
            <strong>${escapeHtml(d.name)}</strong>
            ${d.brand ? `<div style="font-size:0.75rem; color:var(--slate-500); text-transform:uppercase;">${escapeHtml(d.brand)}</div>` : ''}
          </td>
          <td><span class="cat-pill" style="font-size:0.75rem; padding:2px 6px;">${escapeHtml(d.department || d.category || 'Other')}</span></td>
          <td>${priceDisplay}</td>
          <td>${unitDisplay}</td>
          <td>
            ${badgeHtml}
            <div style="font-size:0.75rem; color:var(--slate-500); margin-top:2px;">${escapeHtml(d.analysis || '')}</div>
          </td>
          <td>
            <button class="btn-add-list ${isInList ? 'in-list' : ''}" style="padding:6px 10px; font-size:0.75rem;" onclick="window.__toggleShoppingItem(${d.deal_id})">
              ${isInList ? '✓ In List' : '+ Add'}
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // =========================================================================
  // CATEGORIZATION WORKSPACE & TAB CONTROLLER
  // =========================================================================

  function buildCategorizeCategoryPills() {
    if (!catCategoryPills) return;
    const uniqueProducts = getUniqueProducts();
    const counts = {};
    uniqueProducts.forEach(p => {
      const dept = p.department || getGroceryDepartment(p);
      counts[dept] = (counts[dept] || 0) + 1;
    });

    const sortedCats = Object.keys(counts).sort((a, b) => {
      if (a === 'Other') return 1;
      if (b === 'Other') return -1;
      return counts[b] - counts[a];
    });

    catCategoryPills.innerHTML = '';
    const allBtn = document.createElement('button');
    allBtn.className = `cat-pill ${catActiveCategory === 'ALL' ? 'active' : ''}`;
    allBtn.dataset.catDept = 'ALL';
    allBtn.textContent = `All Categories (${uniqueProducts.length})`;
    allBtn.addEventListener('click', () => {
      catActiveCategory = 'ALL';
      catCategoryPills.querySelectorAll('.cat-pill').forEach(b => b.classList.toggle('active', b.dataset.catDept === 'ALL'));
      renderCategorizeView();
    });
    catCategoryPills.appendChild(allBtn);

    sortedCats.forEach(cat => {
      const btn = document.createElement('button');
      btn.className = `cat-pill ${catActiveCategory === cat ? 'active' : ''}`;
      btn.dataset.catDept = cat;
      btn.textContent = `${cat} (${counts[cat]})`;
      btn.addEventListener('click', () => {
        catActiveCategory = cat;
        catCategoryPills.querySelectorAll('.cat-pill').forEach(b => b.classList.toggle('active', b.dataset.catDept === cat));
        renderCategorizeView();
      });
      catCategoryPills.appendChild(btn);
    });
  }

  function renderCategorizeView() {
    if (!categorizeView || activeTab !== 'categorize') return;

    let products = getUniqueProducts();
    updateRatingBadgesCount();

    // 1. Filter by Search Query
    if (catSearchQuery.trim()) {
      const q = catSearchQuery.toLowerCase().trim();
      products = products.filter(p => {
        const n = (p.name || '').toLowerCase();
        const b = (p.brand || '').toLowerCase();
        const c = (p.category || '').toLowerCase();
        const d = (p.department || getGroceryDepartment(p)).toLowerCase();
        return n.includes(q) || b.includes(q) || c.includes(q) || d.includes(q);
      });
    }

    // 2. Filter by Rating Status
    if (catActiveStatus === 'unrated') {
      products = products.filter(p => !getItemRating(p));
    } else if (catActiveStatus === 'love') {
      products = products.filter(p => getItemRating(p) === 'love');
    } else if (catActiveStatus === 'deal_only') {
      products = products.filter(p => getItemRating(p) === 'deal_only');
    } else if (catActiveStatus === 'giveaway') {
      products = products.filter(p => getItemRating(p) === 'giveaway');
    } else if (catActiveStatus === 'hide') {
      products = products.filter(p => getItemRating(p) === 'hide');
    }

    // 3. Filter by Category
    if (catActiveCategory !== 'ALL') {
      products = products.filter(p => (p.department || getGroceryDepartment(p)) === catActiveCategory);
    }

    // 4. Sort
    products.sort((a, b) => {
      if (catActiveSort === 'price_asc') {
        return (a.price != null ? a.price : 999999) - (b.price != null ? b.price : 999999);
      }
      if (catActiveSort === 'category') {
        const aDept = a.department || getGroceryDepartment(a);
        const bDept = b.department || getGroceryDepartment(b);
        const catCmp = aDept.localeCompare(bDept);
        if (catCmp !== 0) return catCmp;
        return (a.name || '').localeCompare(b.name || '');
      }
      if (catActiveSort === 'unrated_first') {
        const aRated = getItemRating(a) ? 1 : 0;
        const bRated = getItemRating(b) ? 1 : 0;
        if (aRated !== bRated) return aRated - bRated;
        return (a.name || '').localeCompare(b.name || '');
      }
      if (catActiveSort === 'rated_first') {
        const aRated = getItemRating(a) ? 1 : 0;
        const bRated = getItemRating(b) ? 1 : 0;
        if (aRated !== bRated) return bRated - aRated;
        return (a.name || '').localeCompare(b.name || '');
      }
      // default: name_asc
      return (a.name || '').localeCompare(b.name || '');
    });

    if (catCountText) {
      catCountText.textContent = `Showing ${products.length} ${products.length === 1 ? 'product' : 'products'}`;
    }

    if (products.length === 0) {
      if (catItemsList) catItemsList.innerHTML = '';
      if (catEmptyState) catEmptyState.style.display = 'block';
      return;
    }

    if (catEmptyState) catEmptyState.style.display = 'none';

    if (catItemsList) {
      catItemsList.innerHTML = products.map(p => {
        const currentRating = getItemRating(p);
        const ratingClass = currentRating === 'love' ? 'is-loved' : (currentRating === 'deal_only' ? 'is-deal-only' : (currentRating === 'giveaway' ? 'is-giveaway' : (currentRating === 'hide' ? 'is-hidden' : '')));
        let ratingTagHtml = '<span style="color:var(--slate-400); font-size:0.7rem;">⚡ Unrated</span>';
        if (currentRating === 'love') {
          ratingTagHtml = '<span class="item-rating-tag rating-love">❤️ Favorite</span>';
        } else if (currentRating === 'deal_only') {
          ratingTagHtml = '<span class="item-rating-tag rating-deal-only">🎯 Deal Only</span>';
        } else if (currentRating === 'giveaway') {
          ratingTagHtml = '<span class="item-rating-tag rating-giveaway">🎁 Giveaway</span>';
        } else if (currentRating === 'hide') {
          ratingTagHtml = '<span class="item-rating-tag rating-hide">🚫 Hidden</span>';
        }

        const priceStr = p.price != null ? `<span class="cat-deal-price">${formatMoney(p.price)}${p.unit_price ? ` <span style="font-size:0.75rem; color:var(--slate-500); font-weight:400;">(${formatUnitPrice(p.unit_price, p.unit_type)})</span>` : ''}</span>` : '<span style="color:var(--slate-400); font-size:0.75rem;">Regular Price</span>';

        return `
          <div class="categorize-item-card ${ratingClass}" data-product-key="${p.key}">
            <div class="cat-card-top">
              <div style="flex:1; min-width:0;">
                <div class="cat-item-name">${escapeHtml(p.name)}</div>
                ${p.brand ? `<div class="cat-item-brand">${escapeHtml(p.brand)}</div>` : ''}
              </div>
              <span class="cat-pill" style="font-size:0.7rem; padding:2px 6px;">${escapeHtml(p.department || getGroceryDepartment(p))}</span>
            </div>

            <div class="cat-card-sub">
              ${priceStr}
              ${ratingTagHtml}
            </div>

            <div class="cat-card-actions">
              <div class="cat-btn-group">
                <button class="cat-rate-btn btn-love ${currentRating === 'love' ? 'active' : ''}" onclick="window.__setItemRating(${p.deal_id}, 'love', 'categorize')">❤️ Love</button>
                <button class="cat-rate-btn btn-deal-only ${currentRating === 'deal_only' ? 'active' : ''}" onclick="window.__setItemRating(${p.deal_id}, 'deal_only', 'categorize')">🎯 Deal Only</button>
                <button class="cat-rate-btn btn-giveaway ${currentRating === 'giveaway' ? 'active' : ''}" onclick="window.__setItemRating(${p.deal_id}, 'giveaway', 'categorize')">🎁 Giveaway</button>
                <button class="cat-rate-btn btn-hide ${currentRating === 'hide' ? 'active' : ''}" onclick="window.__setItemRating(${p.deal_id}, 'hide', 'categorize')">🚫 Hide</button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  function switchTab(targetTab) {
    if (activeTab === targetTab) return;
    activeTab = targetTab;

    if (navTabDeals) navTabDeals.classList.toggle('active', activeTab === 'deals');
    if (navTabCategorize) navTabCategorize.classList.toggle('active', activeTab === 'categorize');

    if (activeTab === 'deals') {
      if (categorizeView) categorizeView.style.display = 'none';
      if (dealsFeedView) dealsFeedView.style.display = 'block';
      flushPendingFeedRefresh();
    } else {
      if (dealsFeedView) dealsFeedView.style.display = 'none';
      if (categorizeView) categorizeView.style.display = 'block';
      buildCategorizeCategoryPills();
      renderCategorizeView();
    }
  }

  function setupCategorizeTabEvents() {
    if (navTabDeals) {
      navTabDeals.addEventListener('click', () => switchTab('deals'));
    }
    if (navTabCategorize) {
      navTabCategorize.addEventListener('click', () => switchTab('categorize'));
    }

    if (catSearchInput) {
      catSearchInput.addEventListener('input', (e) => {
        catSearchQuery = e.target.value;
        if (catSearchClear) catSearchClear.style.display = catSearchQuery ? 'flex' : 'none';
        renderCategorizeView();
      });
    }

    if (catSearchClear) {
      catSearchClear.addEventListener('click', () => {
        catSearchQuery = '';
        catSearchInput.value = '';
        catSearchClear.style.display = 'none';
        catSearchInput.focus();
        renderCategorizeView();
      });
    }

    if (catSortSelect) {
      catSortSelect.addEventListener('change', (e) => {
        catActiveSort = e.target.value;
        renderCategorizeView();
      });
    }

    document.querySelectorAll('[data-cat-status]').forEach(chip => {
      chip.addEventListener('click', () => {
        catActiveStatus = chip.dataset.catStatus;
        document.querySelectorAll('[data-cat-status]').forEach(c => c.classList.toggle('active', c.dataset.catStatus === catActiveStatus));
        renderCategorizeView();
      });
    });

    if (catClearAllBtn) {
      catClearAllBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear all your saved item preferences?')) {
          itemRatings = {};
          saveItemRatings();
          updateRatingBadgesCount();
          renderCategorizeView();
          pendingFeedRefresh = true;
          showToast('All item preferences cleared');
        }
      });
    }
  }

  // =========================================================================
  // INTERACTION HANDLERS & EXPANSION
  // =========================================================================

  window.__toggleGroupExpand = function (groupId) {
    if (expandedGroupIds.has(groupId)) {
      expandedGroupIds.delete(groupId);
      // Collapsing: user finished viewing this group, so flush any pending re-ordering!
      pendingFeedRefresh = false;
      renderDeals();
    } else {
      expandedGroupIds.add(groupId);
      renderDeals();
    }
  };

  window.__toggleSingleRate = function (dealId) {
    if (singleRateExpandedDealIds.has(dealId)) {
      singleRateExpandedDealIds.delete(dealId);
      // Closing drawer: flush any pending re-ordering!
      pendingFeedRefresh = false;
      renderDeals();
    } else {
      singleRateExpandedDealIds.add(dealId);
      renderDeals();
    }
  };

  window.__toggleGroupAll = function (groupId) {
    const allGroups = getAllGroups();
    const group = allGroups.find(g => g.groupId === groupId);
    if (!group) return;

    const allInList = group.items.every(it => shoppingList.some(s => s.id === it.deal_id));
    if (allInList) {
      // Remove all
      group.items.forEach(it => {
        const idx = shoppingList.findIndex(s => s.id === it.deal_id);
        if (idx >= 0) shoppingList.splice(idx, 1);
      });
      showToast(`Removed all ${group.items.length} items from shopping list`);
    } else {
      // Add all
      let addedCount = 0;
      group.items.forEach(it => {
        if (!shoppingList.some(s => s.id === it.deal_id)) {
          shoppingList.push({
            id: it.deal_id,
            name: it.name,
            price: it.price || 0,
            unit_price: it.unit_price,
            unit_type: it.unit_type,
            page: it.page || 1,
            checked: false,
          });
          addedCount++;
        }
      });
      showToast(`Added ${addedCount} varieties to shopping list!`);
    }

    saveShoppingList();
    renderDeals();
  };

  window.__toggleShoppingItem = function (dealId) {
    const deal = allDeals.find(d => d.deal_id === dealId);
    if (!deal) return;

    const existingIndex = shoppingList.findIndex(item => item.id === dealId);
    if (existingIndex >= 0) {
      shoppingList.splice(existingIndex, 1);
      showToast(`Removed "${deal.name}" from shopping list`);
    } else {
      shoppingList.push({
        id: deal.deal_id,
        name: deal.name,
        price: deal.price || 0,
        unit_price: deal.unit_price,
        unit_type: deal.unit_type,
        page: deal.page || 1,
        checked: false,
      });
      showToast(`Added "${deal.name}" to shopping list!`);
    }

    saveShoppingList();
    renderDeals();
  };

  window.__setItemRating = function (dealId, rating, source = 'feed') {
    const deal = allDeals.find(d => d.deal_id === dealId);
    if (!deal) return;
    setItemRating(deal, rating, source);
  };

  document.addEventListener('click', (e) => {
    if (!pendingFeedRefresh) return;
    if (e.target.closest('.group-expanded-container') || e.target.closest('.single-card-rating-drawer') || e.target.closest('.item-rating-group') || e.target.closest('.btn-rate-toggle') || e.target.closest('.btn-expand-group')) {
      return;
    }
    // Clicked outside an active rating interaction: flush re-order!
    flushPendingFeedRefresh();
  });

  function updateExpandAllButtonState() {
    if (!expandCollapseAllBtn) return;
    if (!groupByAd) {
      expandCollapseAllBtn.style.display = 'none';
      return;
    }
    expandCollapseAllBtn.style.display = 'inline-flex';

    const currentGroups = getFilteredGroups().filter(g => g.isMulti);
    const allExpanded = currentGroups.length > 0 && currentGroups.every(g => expandedGroupIds.has(g.groupId));

    if (allExpanded) {
      expandCollapseIcon.textContent = '▲';
      expandCollapseText.textContent = 'Collapse All';
    } else {
      expandCollapseIcon.textContent = '▼';
      expandCollapseText.textContent = 'Expand All';
    }
  }

  function toggleExpandCollapseAll() {
    const currentGroups = getFilteredGroups().filter(g => g.isMulti);
    const allExpanded = currentGroups.length > 0 && currentGroups.every(g => expandedGroupIds.has(g.groupId));

    if (allExpanded) {
      currentGroups.forEach(g => expandedGroupIds.delete(g.groupId));
    } else {
      currentGroups.forEach(g => expandedGroupIds.add(g.groupId));
    }
    renderDeals();
  }

  // Shopping List Drawer UI
  function updateShoppingListUI() {
    listCountBadge.textContent = shoppingList.length;
    drawerItemCount.textContent = `${shoppingList.length} ${shoppingList.length === 1 ? 'item' : 'items'}`;

    if (shoppingList.length === 0) {
      emptyListView.style.display = 'block';
      shoppingListItems.innerHTML = '';
      drawerTotalPrice.textContent = '$0.00';
      return;
    }

    emptyListView.style.display = 'none';

    let total = 0;
    shoppingListItems.innerHTML = shoppingList.map((item, index) => {
      total += (item.price || 0);
      return `
        <div class="list-item-card ${item.checked ? 'checked' : ''}">
          <div class="item-left">
            <input type="checkbox" class="item-checkbox" ${item.checked ? 'checked' : ''} onchange="window.__toggleItemChecked(${index})">
            <div>
              <div class="item-name-text">${escapeHtml(item.name)}</div>
              <div class="item-unit-text">Pg ${item.page || 1} ${item.unit_price ? `• ${formatUnitPrice(item.unit_price, item.unit_type)}` : ''}</div>
            </div>
          </div>
          <div class="item-right">
            <div class="item-price-text">${formatMoney(item.price)}</div>
            <button class="item-remove-btn" title="Remove Item" onclick="window.__removeShoppingItem(${index})">✕</button>
          </div>
        </div>
      `;
    }).join('');

    drawerTotalPrice.textContent = formatMoney(total);
  }

  window.__toggleItemChecked = function (index) {
    if (shoppingList[index]) {
      shoppingList[index].checked = !shoppingList[index].checked;
      saveShoppingList();
    }
  };

  window.__removeShoppingItem = function (index) {
    if (shoppingList[index]) {
      shoppingList.splice(index, 1);
      saveShoppingList();
      renderDeals();
    }
  };

  function openDrawer() {
    shoppingDrawer.classList.add('active');
    drawerBackdrop.classList.add('active');
  }

  function closeDrawer() {
    shoppingDrawer.classList.remove('active');
    drawerBackdrop.classList.remove('active');
  }

  function copyListToClipboard() {
    if (shoppingList.length === 0) {
      showToast('Shopping list is empty');
      return;
    }

    let text = `🛒 Giant Food Stores (Lewisburg PA) Shopping List\n`;
    text += `===========================================\n`;
    let total = 0;
    shoppingList.forEach(item => {
      total += (item.price || 0);
      text += `[${item.checked ? 'x' : ' '}] ${item.name} - ${formatMoney(item.price)} (Pg ${item.page})\n`;
    });
    text += `===========================================\n`;
    text += `Estimated Total: ${formatMoney(total)}\n`;

    navigator.clipboard.writeText(text).then(() => {
      showToast('📋 Shopping list copied to clipboard!');
    }).catch(() => {
      showToast('Could not copy to clipboard');
    });
  }

  function clearAllItems() {
    if (shoppingList.length === 0) return;
    if (confirm('Clear all items from your shopping list?')) {
      shoppingList = [];
      saveShoppingList();
      renderDeals();
      showToast('Shopping list cleared');
    }
  }

  function resetAllFilters() {
    activeCategory = 'ALL';
    activeFilter = null;
    searchQuery = '';
    searchInput.value = '';
    searchClearBtn.style.display = 'none';

    document.querySelectorAll('.cat-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.category === 'ALL');
    });
    filterChips.forEach(chip => chip.classList.remove('active'));

    renderDeals();
  }

  // =========================================================================
  // EVENT LISTENERS
  // =========================================================================

  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value;
    searchClearBtn.style.display = searchQuery ? 'flex' : 'none';
    renderDeals();
  });

  searchClearBtn.addEventListener('click', () => {
    searchQuery = '';
    searchInput.value = '';
    searchClearBtn.style.display = 'none';
    searchInput.focus();
    renderDeals();
  });

  sortSelect.addEventListener('change', (e) => {
    activeSort = e.target.value;
    renderDeals();
  });

  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const filterType = chip.dataset.filter;
      if (activeFilter === filterType) {
        activeFilter = null;
        chip.classList.remove('active');
      } else {
        filterChips.forEach(c => c.classList.remove('active'));
        activeFilter = filterType;
        chip.classList.add('active');
      }
      renderDeals();
    });
  });

  // Toggle Grouping By Ad Button
  if (toggleGroupingBtn) {
    toggleGroupingBtn.addEventListener('click', () => {
      groupByAd = !groupByAd;
      toggleGroupingBtn.classList.toggle('active', groupByAd);
      renderDeals();
      showToast(groupByAd ? 'Grouping by circular ad' : 'Showing all individual items');
    });
  }

  // Expand / Collapse All Button
  if (expandCollapseAllBtn) {
    expandCollapseAllBtn.addEventListener('click', toggleExpandCollapseAll);
  }

  // Stat Cards Quick Click Filters
  document.getElementById('stat-all-deals').addEventListener('click', resetAllFilters);
  document.getElementById('stat-atl-filter').addEventListener('click', () => {
    activeFilter = activeFilter === 'atl' ? null : 'atl';
    filterChips.forEach(c => c.classList.toggle('active', c.dataset.filter === 'atl' && activeFilter === 'atl'));
    renderDeals();
  });
  document.getElementById('stat-frontpage-filter').addEventListener('click', () => {
    activeFilter = activeFilter === 'front' ? null : 'front';
    filterChips.forEach(c => c.classList.toggle('active', c.dataset.filter === 'front' && activeFilter === 'front'));
    renderDeals();
  });
  document.getElementById('stat-catbest-filter').addEventListener('click', () => {
    activeFilter = activeFilter === 'catbest' ? null : 'catbest';
    filterChips.forEach(c => c.classList.toggle('active', c.dataset.filter === 'catbest' && activeFilter === 'catbest'));
    renderDeals();
  });

  // View Toggles
  viewGridBtn.addEventListener('click', () => {
    viewMode = 'grid';
    viewGridBtn.classList.add('active');
    viewTableBtn.classList.remove('active');
    renderDeals();
  });

  viewTableBtn.addEventListener('click', () => {
    viewMode = 'table';
    viewTableBtn.classList.add('active');
    viewGridBtn.classList.remove('active');
    renderDeals();
  });

  // Reset Buttons
  resetFiltersBtn.addEventListener('click', resetAllFilters);
  emptyResetBtn.addEventListener('click', resetAllFilters);

  // Shopping List Drawer Triggers
  shoppingListTrigger.addEventListener('click', openDrawer);
  closeDrawerBtn.addEventListener('click', closeDrawer);
  drawerBackdrop.addEventListener('click', closeDrawer);
  copyListBtn.addEventListener('click', copyListToClipboard);
  clearListBtn.addEventListener('click', clearAllItems);

  // Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      searchInput.focus();
    }
    if (e.key === 'Escape' && shoppingDrawer.classList.contains('active')) {
      closeDrawer();
    }
  });

  // Init
  loadSavedShoppingList();
  fetchDeals();
})();
