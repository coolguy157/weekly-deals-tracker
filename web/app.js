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
  let shoppingList = []; // { id, name, price, unit_price, checked, page }

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

  // Load Saved Shopping List from LocalStorage
  function loadSavedShoppingList() {
    try {
      const saved = localStorage.getItem('giant_lewisburg_shopping_list');
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
      localStorage.setItem('giant_lewisburg_shopping_list', JSON.stringify(shoppingList));
    } catch (e) {
      console.warn('Could not save shopping list', e);
    }
    updateShoppingListUI();
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
    return /atl|all[-_]time/i.test(badge || '');
  }
  function isGreatBadge(badge) {
    return /great|beat/i.test(badge || '');
  }
  function isPointsFreebie(d) {
    if (!d) return false;
    const badge = typeof d === 'string' ? d : (d.badge || '');
    const pType = typeof d === 'object' ? (d.promo_type || '') : '';
    const pDetail = typeof d === 'object' ? (d.promo_detail || '') : '';
    return /points_freebie|freebie/i.test(badge) || pType === 'points_redemption' || /freebie|free with \d+ choice points/i.test(pDetail);
  }

  function getBadgeHtml(d) {
    const rawBadge = (d.badge || '').toUpperCase();
    const badges = [];

    if (/ATL|ALL[-_]TIME/i.test(rawBadge)) {
      badges.push('<span class="deal-badge atl">🔥 ALL-TIME LOW</span>');
    } else if (/POINTS_FREEBIE|FREEBIE/i.test(rawBadge)) {
      badges.push('<span class="deal-badge points-freebie">🪙 FREE W/ POINTS</span>');
    } else if (/POINTS_REWARD|REWARD/i.test(rawBadge)) {
      badges.push('<span class="deal-badge points-reward">🪙 POINTS REWARD</span>');
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

  function synthesizeGroupTitle(items) {
    if (items.length === 1) {
      return items[0].name || 'Deal Item';
    }

    // Check if this is a Meal Deal bundle
    const promo = (items[0].promo_detail || '').toLowerCase();
    if (items.some(it => it.promo_type === 'meal_deal') || promo.includes('meal deal') || promo.includes('get these free')) {
      return 'Weekly Meal Deal';
    }

    const brands = Array.from(new Set(items.map(it => it.brand).filter(Boolean))).sort();
    const names = items.map(it => it.name || '');

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
    if (brands.includes('Fresh Seafood') || brands.includes('Hannaford') || names.some(n => /fillet|swai|cod|whiting/i.test(n))) {
      return 'Fresh & Frozen Seafood Fillets';
    }

    // Common grocery product types
    const keywords = [
      'Soda', 'Potato Chips', 'Tortilla Chips', 'Chips', 'Cookies', 'Cereal',
      'Sausage', 'Bratwurst', 'Brats', 'Shampoo', 'Lotion', 'Bread', 'Dressing',
      'Broth', 'Crackers', 'Water', 'Tea', 'Juice', 'Vitamins', 'Candy', 'Dip',
      'Pasta', 'Rice', 'Ice Cream', 'Coffee', 'Cheese', 'Spices', 'Yogurt',
      'Snacks', 'Sauce', 'Chicken', 'Beef', 'Pork', 'Fish', 'Seafood', 'Bacon'
    ];

    let matchedKeyword = null;
    for (const kw of keywords) {
      if (names.every(n => n.toLowerCase().includes(kw.toLowerCase()))) {
        matchedKeyword = kw;
        break;
      }
    }

    // Common pack packaging
    let pkg = '';
    const packSizes = ['12 pk', '6 pk', '8 pk', '15 ct', 'Family Size', 'Party Size', '1 Liter', '2 Liter'];
    for (const p of packSizes) {
      if (names.every(n => n.toLowerCase().includes(p.toLowerCase()))) {
        pkg = ` (${p})`;
        break;
      }
    }

    if (matchedKeyword) {
      if (brands.length === 1) {
        return `${brands[0]} ${matchedKeyword}${pkg}`;
      } else if (brands.length > 0 && brands.length <= 3) {
        return `${brands.join(', ')} • ${matchedKeyword}${pkg}`;
      } else if (brands.length > 3) {
        return `${brands.slice(0, 2).join(', ')} & more • ${matchedKeyword}${pkg}`;
      } else {
        return `${matchedKeyword} Selection${pkg}`;
      }
    }

    if (brands.length === 1) {
      return `${brands[0]} Assorted Varieties${pkg} (${items.length} Items)`;
    } else if (brands.length > 0 && brands.length <= 3) {
      return `${brands.join(', ')} Selection${pkg} (${items.length} Items)`;
    } else if (brands.length > 3) {
      return `${brands.slice(0, 2).join(', ')} & more${pkg} (${items.length} Items)`;
    }

    const cat = items[0].category || 'Featured';
    return `${cat} Mix & Match${pkg} (${items.length} Items)`;
  }

  function buildGroupObject(groupId, items) {
    const isMulti = items.length > 1;
    const brands = Array.from(new Set(items.map(it => it.brand).filter(Boolean))).sort();
    const prices = items.map(it => it.price).filter(p => p != null && !isNaN(p));
    const minPrice = prices.length ? Math.min(...prices) : null;
    const maxPrice = prices.length ? Math.max(...prices) : null;

    const unitPrices = items.map(it => it.unit_price).filter(p => p != null && !isNaN(p));
    const minUnitPrice = unitPrices.length ? Math.min(...unitPrices) : null;
    const maxUnitPrice = unitPrices.length ? Math.max(...unitPrices) : null;

    const unitTypes = Array.from(new Set(items.map(it => it.unit_type).filter(Boolean)));
    const primaryUnitType = unitTypes[0] || null;

    const promoDetail = items.find(it => it.promo_detail)?.promo_detail || items[0].promo_detail || '';
    const promoType = items.find(it => it.promo_type && it.promo_type !== 'standard')?.promo_type || items[0].promo_type || 'standard';

    const hasAtl = items.some(it => isAtlBadge(it.badge));
    const hasGreat = items.some(it => isGreatBadge(it.badge) || isAtlBadge(it.badge) || /beat/i.test(it.badge || ''));
    const hasCatBest = items.some(it => it.is_category_best);
    const hasPointsFreebie = items.some(it => isPointsFreebie(it));
    const isFrontPage = items.some(it => it.is_front_page);
    const page = items[0].page || 1;
    const category = items[0].category || 'Other';

    const title = synthesizeGroupTitle(items);
    const isMealDeal = groupId.startsWith('meal_deal_') || promoType === 'meal_deal' || title.toLowerCase().includes('meal deal');
    let anchorItem = null;
    if (isMealDeal && items.length > 0) {
      anchorItem = items.reduce((prev, curr) => ((curr.price || 0) > (prev.price || 0) ? curr : prev), items[0]);
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
      brands,
      minPrice,
      maxPrice,
      minUnitPrice,
      maxUnitPrice,
      primaryUnitType,
      promoDetail,
      promoType,
      hasPointsFreebie,
      hasAtl,
      hasGreat,
      hasCatBest,
      representativeDeal: anchorItem || items[0],
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

    // Render Initial View
    renderDeals();
  }

  // Build Categories Bar
  function buildCategoryPills() {
    const counts = {};
    allDeals.forEach(d => {
      const cat = d.category || 'Other';
      counts[cat] = (counts[cat] || 0) + 1;
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

    // Category Filter
    if (activeCategory !== 'ALL') {
      filtered = filtered.filter(g =>
        g.items.some(d => (d.category || 'Other') === activeCategory)
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
    }

    // Search Filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(g => {
        const titleMatch = (g.title || '').toLowerCase().includes(q);
        const promoMatch = (g.promoDetail || '').toLowerCase().includes(q);
        const brandMatch = g.brands.some(b => b.toLowerCase().includes(q));
        const itemMatch = g.items.some(d => {
          const n = (d.name || '').toLowerCase();
          const b = (d.brand || '').toLowerCase();
          const c = (d.category || '').toLowerCase();
          return n.includes(q) || b.includes(q) || c.includes(q);
        });
        return titleMatch || promoMatch || brandMatch || itemMatch;
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

      // 'featured' default: 5-Point / Points Freebies (200) > ALL-TIME LOW (100) > Great Deal / Beat Avg (50) + Front page bonus (20)
      const scoreA = (a.hasPointsFreebie ? 200 : a.hasAtl ? 100 : a.hasGreat ? 50 : 0) + (a.isFrontPage ? 20 : 0);
      const scoreB = (b.hasPointsFreebie ? 200 : b.hasAtl ? 100 : b.hasGreat ? 50 : 0) + (b.isFrontPage ? 20 : 0);
      if (scoreA !== scoreB) return scoreB - scoreA;
      return (a.page || 1) - (b.page || 1);
    });

    return filtered;
  }

  // Flat deals filter (if groupByAd is disabled)
  function getFilteredDealsFlat() {
    let filtered = [...allDeals];

    if (activeCategory !== 'ALL') {
      filtered = filtered.filter(d => (d.category || 'Other') === activeCategory);
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
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(d => {
        const name = (d.name || '').toLowerCase();
        const brand = (d.brand || '').toLowerCase();
        const cat = (d.category || '').toLowerCase();
        const promo = (d.promo_detail || '').toLowerCase();
        return name.includes(q) || brand.includes(q) || cat.includes(q) || promo.includes(q);
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
      const scoreA = (isPointsFreebie(a) ? 200 : isAtlBadge(a.badge) ? 100 : isGreatBadge(a.badge) ? 50 : 0) + (a.is_front_page ? 20 : 0);
      const scoreB = (isPointsFreebie(b) ? 200 : isAtlBadge(b.badge) ? 100 : isGreatBadge(b.badge) ? 50 : 0) + (b.is_front_page ? 20 : 0);
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
    const badgeHtml = getBadgeHtml(rep);

    // Price range display
    let priceDisplay = '—';
    let unitPriceDisplay = '';
    if (g.isMealDeal && g.anchorItem && g.anchorItem.price != null) {
      priceDisplay = formatMoney(g.anchorItem.price);
      if (g.anchorItem.unit_price != null) {
        unitPriceDisplay = formatUnitPrice(g.anchorItem.unit_price, g.anchorItem.unit_type);
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
      promoDetailHtml = `<div class="meal-deal-qualifier-note">✨ Buy <strong>${anchorClean}</strong> (${formatMoney(g.anchorItem.price)}), get bundled items <strong>FREE</strong></div>`;
    } else if (g.promoDetail) {
      promoDetailHtml = `<div class="promo-detail-note">🏷️ ${escapeHtml(g.promoDetail)}</div>`;
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
          ${topItems.map(it => `<span class="variety-chip">${escapeHtml(it.name.split(' - ')[0])}</span>`).join('')}
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
              const itemUnit = formatUnitPrice(item.unit_price, item.unit_type);
              const itemBadge = isAtlBadge(item.badge) ? '<span class="deal-badge atl" style="font-size:0.65rem; padding:1px 4px;">ATL</span>' : '';
              const isMain = g.isMealDeal && g.anchorItem && (item.deal_id === g.anchorItem.deal_id || item.name === g.anchorItem.name);
              let itemPriceHtml = `<span class="group-item-price">${formatMoney(item.price)}</span>`;
              let itemRoleBadge = '';
              if (g.isMealDeal) {
                if (isMain) {
                  itemRoleBadge = '<span class="deal-badge" style="font-size:0.65rem; background:#dbeafe; color:#1e40af; margin-right:4px;">Main Item</span>';
                  itemPriceHtml = `<span class="group-item-price" style="font-weight:700;">${formatMoney(item.price)}</span>`;
                } else {
                  itemRoleBadge = '<span class="deal-badge" style="font-size:0.65rem; background:#dcfce7; color:#166534; margin-right:4px;">FREE with purchase</span>';
                  itemPriceHtml = `<span class="group-item-price" style="color:#059669; font-weight:700;">$0.00 <span style="text-decoration:line-through; color:var(--slate-400); font-weight:400; font-size:0.75rem;">${formatMoney(item.price)}</span></span>`;
                }
              }

              return `
                <div class="group-item-row" data-deal-id="${item.deal_id}">
                  <div class="group-item-info">
                    <div class="group-item-name">${escapeHtml(item.name)}</div>
                    <div class="group-item-sub">
                      ${itemRoleBadge}
                      ${item.brand ? `<span>${escapeHtml(item.brand)}</span>` : ''}
                      ${itemUnit ? `<span>• ${itemUnit}</span>` : ''}
                      ${itemBadge}
                    </div>
                  </div>
                  <div class="group-item-actions">
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

    return `
      <div class="deal-card is-group ${g.hasAtl ? 'is-atl' : ''}" data-group-id="${g.groupId}">
        <div>
          <div class="card-top">
            <div class="badge-row">
              ${badgeHtml}
              <span class="deal-badge group-count">📦 ${g.items.length} Varieties</span>
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
    const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
    const badgeHtml = getBadgeHtml(d);

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

    return `
      <div class="deal-card ${isAtl ? 'is-atl' : ''}" data-id="${d.deal_id}">
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
            <span class="current-price">${formatMoney(d.price)}</span>
            ${unitStr ? `<span class="unit-price-tag">${unitStr}</span>` : ''}
          </div>

          ${promoDetailHtml}
          ${historyHtml}
        </div>

        <div class="card-action-row">
          <button class="btn-add-list ${isInList ? 'in-list' : ''}" onclick="window.__toggleShoppingItem(${d.deal_id})">
            ${isInList ? '✓ In List' : '+ Add to List'}
          </button>
        </div>
      </div>
    `;
  }

  // Render Grouped Table View
  function renderGroupedTableView(groups) {
    dealsTableBody.innerHTML = groups.map(g => {
      if (g.isMulti) {
        const isExpanded = expandedGroupIds.has(g.groupId);
        const isAllInList = g.items.every(it => shoppingList.some(s => s.id === it.deal_id));
        const badgeHtml = getBadgeHtml(g.representativeDeal);
        let priceDisplay = formatMoney(g.minPrice);
        if (g.isMealDeal && g.anchorItem && g.anchorItem.price != null) {
          priceDisplay = formatMoney(g.anchorItem.price);
        } else if (g.minPrice != null && g.maxPrice != null && Math.abs(g.minPrice - g.maxPrice) >= 0.01) {
          priceDisplay = `${formatMoney(g.minPrice)} – ${formatMoney(g.maxPrice)}`;
        }
        let unitDisplay = formatUnitPrice(g.minUnitPrice, g.primaryUnitType);
        if (g.isMealDeal && g.anchorItem && g.anchorItem.unit_price != null) {
          unitDisplay = formatUnitPrice(g.anchorItem.unit_price, g.anchorItem.unit_type);
        } else if (g.minUnitPrice != null && g.maxUnitPrice != null && Math.abs(g.minUnitPrice - g.maxUnitPrice) >= 0.005) {
          unitDisplay = `$${g.minUnitPrice.toFixed(2)} – $${g.maxUnitPrice.toFixed(2)}/${g.primaryUnitType || 'unit'}`;
        }

        const promoText = g.isMealDeal && g.anchorItem ? `✨ Buy ${escapeHtml(g.anchorItem.name.split(' - ')[0])}, Get Bundled Items FREE` : g.promoDetail;

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
            <td><span class="cat-pill" style="font-size:0.75rem; padding:2px 6px;">${g.category || 'Other'}</span></td>
            <td><strong style="font-size:1.1rem; color:var(--slate-900);">${priceDisplay}</strong></td>
            <td>${unitDisplay ? `<span class="unit-price-tag">${unitDisplay}</span>` : '—'}</td>
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
          const itemUnit = formatUnitPrice(item.unit_price, item.unit_type);
          const itemBadge = isAtlBadge(item.badge) ? '<span class="deal-badge atl" style="font-size:0.65rem; padding:1px 4px;">ATL</span>' : '';
          const isMain = g.isMealDeal && g.anchorItem && (item.deal_id === g.anchorItem.deal_id || item.name === g.anchorItem.name);
          let priceCell = `<strong>${formatMoney(item.price)}</strong>`;
          let badgeCell = itemBadge;
          if (g.isMealDeal) {
            if (isMain) {
              badgeCell = `<span class="deal-badge" style="font-size:0.65rem; background:#dbeafe; color:#1e40af;">Main Item</span> ${itemBadge}`;
            } else {
              badgeCell = `<span class="deal-badge" style="font-size:0.65rem; background:#dcfce7; color:#166534;">FREE with purchase</span> ${itemBadge}`;
              priceCell = `<strong style="color:#059669;">$0.00</strong> <span style="text-decoration:line-through; color:var(--slate-400); font-size:0.75rem;">${formatMoney(item.price)}</span>`;
            }
          }

          return `
            <tr class="table-child-row ${isExpanded ? '' : 'collapsed'}">
              <td></td>
              <td style="padding-left:36px;">
                <span>${escapeHtml(item.name)}</span>
                ${item.brand ? `<span style="font-size:0.7rem; color:var(--slate-400); margin-left:6px;">(${escapeHtml(item.brand)})</span>` : ''}
              </td>
              <td><span style="font-size:0.75rem; color:var(--slate-500);">${item.category || ''}</span></td>
              <td>${priceCell}</td>
              <td>${itemUnit ? `<span class="unit-price-tag" style="font-size:0.75rem;">${itemUnit}</span>` : '—'}</td>
              <td>${badgeCell}</td>
              <td>
                <button class="btn-item-add ${itemInList ? 'in-list' : ''}" onclick="window.__toggleShoppingItem(${item.deal_id})">
                  ${itemInList ? '✓ In' : '+ Add'}
                </button>
              </td>
            </tr>
          `;
        }).join('');

        return parentRow + childRows;
      } else {
        const d = g.items[0];
        const isInList = shoppingList.some(item => item.id === d.deal_id);
        const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
        const badgeHtml = getBadgeHtml(d);

        return `
          <tr>
            <td><span class="page-indicator">Pg ${d.page || 1}</span></td>
            <td>
              <strong>${escapeHtml(d.name)}</strong>
              ${d.brand ? `<div style="font-size:0.75rem; color:var(--slate-500); text-transform:uppercase;">${escapeHtml(d.brand)}</div>` : ''}
            </td>
            <td><span class="cat-pill" style="font-size:0.75rem; padding:2px 6px;">${d.category || 'Other'}</span></td>
            <td><strong style="font-size:1.1rem; color:var(--slate-900);">${formatMoney(d.price)}</strong></td>
            <td>${unitStr ? `<span class="unit-price-tag">${unitStr}</span>` : '—'}</td>
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
      const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
      const badgeHtml = getBadgeHtml(d);

      return `
        <tr>
          <td><span class="page-indicator">Pg ${d.page || 1}</span></td>
          <td>
            <strong>${escapeHtml(d.name)}</strong>
            ${d.brand ? `<div style="font-size:0.75rem; color:var(--slate-500); text-transform:uppercase;">${escapeHtml(d.brand)}</div>` : ''}
          </td>
          <td><span class="cat-pill" style="font-size:0.75rem; padding:2px 6px;">${d.category || 'Other'}</span></td>
          <td><strong style="font-size:1.1rem; color:var(--slate-900);">${formatMoney(d.price)}</strong></td>
          <td>${unitStr ? `<span class="unit-price-tag">${unitStr}</span>` : '—'}</td>
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
  // INTERACTION HANDLERS & EXPANSION
  // =========================================================================

  window.__toggleGroupExpand = function (groupId) {
    if (expandedGroupIds.has(groupId)) {
      expandedGroupIds.delete(groupId);
    } else {
      expandedGroupIds.add(groupId);
    }
    renderDeals();
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
