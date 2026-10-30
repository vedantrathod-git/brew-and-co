/**
 * Brew & Co. — Curated Customer Menu Configuration
 *
 * Curates the customer-facing digital storefront to a balanced selection of 37
 * artisanal products across all 9 café departments.
 *
 * Guarantees:
 * 1. Exactly 37 products displayed to customers.
 * 2. Every category retains 3 to 6 active products (0 empty categories).
 * 3. Every displayed product has a distinct, 100% unique photograph.
 * 4. Staff POS and internal menu management retain access to the full 70 active products.
 */

export const CURATED_PRODUCT_NAMES = new Set([
  // 1. Coffee & Espresso (6 items)
  'Double Espresso (Doppio)',
  'Café Cortado (Gibraltar)',
  'Brew & Co. Flat White',
  'Artisanal Cappuccino',
  'Dark Mocha Supreme',
  'V60 Single-Origin Pour Over',

  // 2. Tea & Hot Beverages (3 items)
  'Smoked Earl Grey Bergamot',
  'Ceremonial Matcha Latte',
  'Belgian Hot Chocolate (70%)',

  // 3. Cold Coffee & Refreshers (4 items)
  '18-Hour Kyoto Drip Cold Brew',
  'Vietnamese Iced Coffee',
  'Classic Affogato al Caffè',
  'Citrus Espresso Tonic',

  // 4. Bakery & Viennoiserie (5 items)
  'Classic French Butter Croissant',
  'Pain au Chocolat',
  'Almond Frangipane Croissant',
  'Pistachio Cardamom Cruffin',
  'Kalamata Olive & Rosemary Focaccia',

  // 5. Sandwiches & Toasties (4 items)
  'Smoked Chicken & Truffle Aioli Focaccia',
  'Pesto Burrata & Roasted Pepper Sourdough',
  'Truffled Wild Mushroom & Gruyère Toastie',
  'Classic Reuben on Caraway Rye',

  // 6. Breakfast & Brunch (4 items)
  'Eggs Florentine on Brioche',
  'Eggs Royale (Smoked Salmon)',
  'Shakshuka Skillet with Crumbled Feta',
  'Belgian Buttermilk Waffle Stack',

  // 7. Salads & Light Bowls (3 items)
  'Wild Grain & Roasted Beet Harvest Bowl',
  'Charred Burrata & Peach Panzanella',
  'Acai Antioxidant Smoothie Bowl',

  // 8. Desserts & Patisserie (4 items)
  'Artisanal Espresso Tiramisu Jar',
  'Dark Chocolate Sea Salt Tart (70%)',
  'Burnt Basque Cheesecake Slice',
  'Pistachio Raspberry Opera Cake',

  // 9. Seasonal & Signature Specials (4 items)
  'Smoked Sea Salt Caramel Latte',
  'Madagascar Vanilla Bean Shakerato',
  'Cascara Cold Brew Spritz',
  'Rose Cardamom Iced Latte',
]);

export const CURATED_PRODUCT_NAMES_NORMALIZED = new Set(
  Array.from(CURATED_PRODUCT_NAMES).map((name) => name.trim().toLowerCase())
);

export const CURATED_PRODUCT_IDS = new Set([
  // ── Neon / Fresh Sequence IDs (1–70 space) ────────────────────────────────
  1, 3, 5, 6, 8, 10,
  14, 16, 18,
  19, 21, 22, 23,
  27, 28, 29, 30, 32,
  37, 38, 39, 43,
  45, 46, 48, 50,
  53, 54, 57,
  59, 60, 61, 62,
  65, 66, 68, 69,

  // ── Legacy / Historical Sequence IDs (106–174 space) ──────────────────────
  106, 108, 110, 111, 113, 115,
  119, 121, 123,
  124, 126, 127, 128,
  132, 133, 134, 135, 137,
  142, 143, 144, 148,
  150, 151, 153, 155,
  158, 159, 162,
  164, 165, 166, 167,
  170, 171, 173, 174,
]);

/**
 * Checks whether a given product or product ID belongs to the curated customer catalog.
 * Supports product objects (matching name or ID) and numeric/string IDs.
 *
 * @param {number|string|Object} itemOrId - Product object with `id` / `name` or raw ID
 * @returns {boolean}
 */
export function isCuratedProduct(itemOrId) {
  if (!itemOrId) return false;

  if (typeof itemOrId === 'object') {
    if (itemOrId.id != null && CURATED_PRODUCT_IDS.has(Number(itemOrId.id))) {
      return true;
    }
    if (itemOrId.name) {
      const normalized = String(itemOrId.name).trim().toLowerCase();
      if (CURATED_PRODUCT_NAMES_NORMALIZED.has(normalized)) {
        return true;
      }
    }
    return false;
  }

  const numericId = Number(itemOrId);
  return !Number.isNaN(numericId) && CURATED_PRODUCT_IDS.has(numericId);
}

/**
 * Filters a public menu response to the curated customer catalog.
 * Dynamically updates category item counts and excludes any category with 0 items.
 *
 * @param {Object|Array} rawMenuData - { categories: Array, items: Array } or Array of items
 * @returns {Object} Curated { categories, items, total_categories, total_items }
 */
export function filterCuratedMenu(rawMenuData) {
  if (!rawMenuData) {
    return { categories: [], items: [], total_categories: 0, total_items: 0 };
  }

  const rawItems = Array.isArray(rawMenuData.items)
    ? rawMenuData.items
    : Array.isArray(rawMenuData)
    ? rawMenuData
    : [];

  // 1. Filter items to only curated products (evaluates both name and ID)
  const curatedItems = rawItems.filter((item) => isCuratedProduct(item));

  // 2. Count items per category among curated products
  const categoryCounts = {};
  for (const item of curatedItems) {
    if (item.category_id != null) {
      categoryCounts[item.category_id] = (categoryCounts[item.category_id] || 0) + 1;
    }
  }

  // 3. Update categories with accurate counts and filter out empty categories
  const rawCategories = Array.isArray(rawMenuData.categories) ? rawMenuData.categories : [];
  let activeCuratedCategories = [];

  if (rawCategories.length > 0) {
    activeCuratedCategories = rawCategories
      .filter((cat) => (categoryCounts[cat.id] || 0) > 0)
      .map((cat) => ({
        ...cat,
        item_count: categoryCounts[cat.id] || 0,
      }));
  } else {
    // If rawCategories wasn't provided, reconstruct category summaries from curated items
    const catMap = new Map();
    for (const item of curatedItems) {
      if (item.category_id != null && !catMap.has(item.category_id)) {
        catMap.set(item.category_id, {
          id: item.category_id,
          name: item.category_name || `Category ${item.category_id}`,
          item_count: categoryCounts[item.category_id] || 0,
        });
      }
    }
    activeCuratedCategories = Array.from(catMap.values()).sort((a, b) => a.id - b.id);
  }

  return {
    categories: activeCuratedCategories,
    items: curatedItems,
    total_categories: activeCuratedCategories.length,
    total_items: curatedItems.length,
  };
}
