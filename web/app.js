/**
 * Giant Weekly Deals - Lewisburg PA Tracker
 * Client-side Controller & Dynamic Filter Engine
 */

(function () {
  'use strict';

  // State
  let allDeals = [];
  let flyerMeta = null;
  let activeCategory = 'ALL';
  let activeFilter = null; // 'atl', 'great', 'front', 'catbest', 'bogo'
  let searchQuery = '';
  let activeSort = 'featured';
  let viewMode = 'grid'; // 'grid' | 'table'
  let shoppingList = []; // { id, name, price, unit_price, checked }

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
      // First try local deals.json with cache-busting
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
      console.warn('Failed to load deals.json, attempting fallback or mock', err);
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

  // Filtering & Sorting
  function getFilteredDeals() {
    let filtered = [...allDeals];

    // Category Filter
    if (activeCategory !== 'ALL') {
      filtered = filtered.filter(d => (d.category || 'Other') === activeCategory);
    }

    // Chip Filter
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
      filtered = filtered.filter(d => /points|freebie|reward/i.test(d.badge || '') || (d.promo_type && d.promo_type.startsWith('points')) || (d.promo_detail && /choice|points/i.test(d.promo_detail)));
    }

    // Search Filter
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

    // Sorting
    filtered.sort((a, b) => {
      if (activeSort === 'unit_price_asc') {
        const upA = a.unit_price != null ? a.unit_price : 999999;
        const upB = b.unit_price != null ? b.unit_price : 999999;
        return upA - upB;
      }
      if (activeSort === 'price_asc') {
        const pA = a.price != null ? a.price : 999999;
        const pB = b.price != null ? b.price : 999999;
        return pA - pB;
      }
      if (activeSort === 'price_desc') {
        const pA = a.price != null ? a.price : -1;
        const pB = b.price != null ? b.price : -1;
        return pB - pA;
      }
      if (activeSort === 'page_asc') {
        return (a.page || 1) - (b.page || 1);
      }
      if (activeSort === 'name_asc') {
        return (a.name || '').localeCompare(b.name || '');
      }
      // 'featured' default: ATL first, then Great Deals, then front page, then page asc
      const scoreA = (a.badge === 'ALL-TIME LOW' ? 100 : a.badge === 'GREAT DEAL' ? 50 : 0) + (a.is_front_page ? 20 : 0);
      const scoreB = (b.badge === 'ALL-TIME LOW' ? 100 : b.badge === 'GREAT DEAL' ? 50 : 0) + (b.is_front_page ? 20 : 0);
      if (scoreA !== scoreB) return scoreB - scoreA;
      return (a.page || 1) - (b.page || 1);
    });

    return filtered;
  }

  // Format Helper
  function formatMoney(val) {
    if (val == null || isNaN(val)) return '—';
    return `$${Number(val).toFixed(2)}`;
  }

  function formatUnitPrice(val, unitType) {
    if (val == null || isNaN(val)) return '';
    const unit = unitType ? `/${unitType}` : '/unit';
    return `$${Number(val).toFixed(2)}${unit}`;
  }

  // Render Deal Cards (Grid View)
  function renderDeals() {
    const deals = getFilteredDeals();

    // Results info text
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
      renderGridView(deals);
    } else {
      dealsGrid.style.display = 'none';
      dealsTableContainer.style.display = 'block';
      renderTableView(deals);
    }
  }

  function renderGridView(deals) {
    dealsGrid.innerHTML = deals.map(d => {
      const isInList = shoppingList.some(item => item.id === d.deal_id);
      const isAtl = isAtlBadge(d.badge);
      const unitStr = formatUnitPrice(d.unit_price, d.unit_type);
      const badgeHtml = getBadgeHtml(d);

      let promoDetailHtml = '';
      if (d.promo_detail) {
        promoDetailHtml = `<div class="promo-detail-note">🏷️ ${d.promo_detail}</div>`;
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
    }).join('');
  }

  function renderTableView(deals) {
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
          <td>
            <button class="btn-add-list ${isInList ? 'in-list' : ''}" style="padding:6px 10px; font-size:0.75rem;" onclick="window.__toggleShoppingItem(${d.deal_id})">
              ${isInList ? '✓ In List' : '+ Add'}
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Shopping List Management
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
        checked: false
      });
      showToast(`Added "${deal.name}" to shopping list!`);
    }

    saveShoppingList();
    renderDeals();
  };

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

  // Drawer Open / Close
  function openDrawer() {
    shoppingDrawer.classList.add('active');
    drawerBackdrop.classList.add('active');
  }

  function closeDrawer() {
    shoppingDrawer.classList.remove('active');
    drawerBackdrop.classList.remove('active');
  }

  // Copy List to Clipboard
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

  // Escape HTML helper
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Reset Filters
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

  // Event Listeners
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
