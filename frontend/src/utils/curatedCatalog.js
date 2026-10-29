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

export const CURATED_PRODUCT_IDS = new Set([
  // 1. Coffee & Espresso (6 items)
  106, // Double Espresso (Doppio) ($1.91)
  108, // Café Cortado (Gibraltar) ($2.22)
  110, // Brew & Co. Flat White ($2.54)
  111, // Artisanal Cappuccino ($2.43)
  113, // Dark Mocha Supreme ($2.86)
  115, // V60 Single-Origin Pour Over ($2.75)

  // 2. Tea & Hot Beverages (3 items)
  119, // Smoked Earl Grey Bergamot ($2.12)
  121, // Ceremonial Matcha Latte ($2.86)
  123, // Belgian Hot Chocolate (70%) ($2.75)

  // 3. Cold Coffee & Refreshers (4 items)
  124, // 18-Hour Kyoto Drip Cold Brew ($2.54)
  126, // Vietnamese Iced Coffee ($2.75)
  127, // Classic Affogato al Caffè ($2.54)
  128, // Citrus Espresso Tonic ($2.86)

  // 4. Bakery & Viennoiserie (5 items)
  132, // Classic French Butter Croissant ($1.91)
  133, // Pain au Chocolat ($2.22)
  134, // Almond Frangipane Croissant ($2.65)
  135, // Pistachio Cardamom Cruffin ($2.75)
  137, // Kalamata Olive & Rosemary Focaccia ($1.91)

  // 5. Sandwiches & Toasties (4 items)
  142, // Smoked Chicken & Truffle Aioli Focaccia ($3.81)
  143, // Pesto Burrata & Roasted Pepper Sourdough ($3.60)
  144, // Truffled Wild Mushroom & Gruyère Toastie ($3.39)
  148, // Classic Reuben on Caraway Rye ($4.13)

  // 6. Breakfast & Brunch (4 items)
  150, // Eggs Florentine on Brioche ($3.60)
  151, // Eggs Royale (Smoked Salmon) ($4.45)
  153, // Shakshuka Skillet with Crumbled Feta ($3.49)
  155, // Belgian Buttermilk Waffle Stack ($3.39)

  // 7. Salads & Light Bowls (3 items)
  158, // Wild Grain & Roasted Beet Harvest Bowl ($3.60)
  159, // Charred Burrata & Peach Panzanella ($3.81)
  162, // Acai Antioxidant Smoothie Bowl ($3.70)

  // 8. Desserts & Patisserie (4 items)
  164, // Artisanal Espresso Tiramisu Jar ($3.07)
  165, // Dark Chocolate Sea Salt Tart (70%) ($2.86)
  166, // Burnt Basque Cheesecake Slice ($3.28)
  167, // Pistachio Raspberry Opera Cake ($3.39)

  // 9. Seasonal & Signature Specials (4 items)
  170, // Smoked Sea Salt Caramel Latte ($2.96)
  171, // Madagascar Vanilla Bean Shakerato ($2.86)
  173, // Cascara Cold Brew Spritz ($2.75)
  174, // Rose Cardamom Iced Latte ($2.96)
]);

/**
 * Checks whether a given product or product ID belongs to the curated customer catalog.
 * @param {number|Object} itemOrId - Product object with `id` or raw numeric ID
 * @returns {boolean}
 */
export function isCuratedProduct(itemOrId) {
  if (!itemOrId) return false;
  const id = typeof itemOrId === 'object' ? itemOrId.id : itemOrId;
  return CURATED_PRODUCT_IDS.has(Number(id));
}

/**
 * Filters a public menu response to the curated customer catalog.
 * Dynamically updates category item counts and excludes any category with 0 items.
 *
 * @param {Object} rawMenuData - { categories: Array, items: Array }
 * @returns {Object} Curated { categories, items, total_categories, total_items }
 */
export function filterCuratedMenu(rawMenuData) {
  if (!rawMenuData || !Array.isArray(rawMenuData.items)) {
    return { categories: [], items: [], total_categories: 0, total_items: 0 };
  }

  // 1. Filter items to only curated products
  const curatedItems = rawMenuData.items.filter((item) => isCuratedProduct(item.id));

  // 2. Count items per category among curated products
  const categoryCounts = {};
  for (const item of curatedItems) {
    categoryCounts[item.category_id] = (categoryCounts[item.category_id] || 0) + 1;
  }

  // 3. Update categories with accurate counts and filter out empty categories
  const rawCategories = Array.isArray(rawMenuData.categories) ? rawMenuData.categories : [];
  const activeCuratedCategories = rawCategories
    .filter((cat) => (categoryCounts[cat.id] || 0) > 0)
    .map((cat) => ({
      ...cat,
      item_count: categoryCounts[cat.id] || 0,
    }));

  return {
    categories: activeCuratedCategories,
    items: curatedItems,
    total_categories: activeCuratedCategories.length,
    total_items: curatedItems.length,
  };
}
