/**
 * Dish Image Mapping & Fallback Management
 * Brew & Co. — Unique Product Photography Catalog
 *
 * All image URLs are verified, high-resolution photography from the Unsplash CDN
 * with fixed query parameters (auto=format, fit=crop, w=800, q=80) for fast caching.
 *
 * Guarantees:
 * - Every single curated customer product (IDs 106 to 174) has a distinct, 100% unique photograph.
 * - Accurate culinary alt text for accessibility.
 * - Legacy items (IDs 25 to 34) retain their historical mappings for staff POS.
 */

export const DEFAULT_FALLBACK_IMAGE =
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80';

// Stable, high-quality images mapped directly to seeded database dish IDs & slugs
export const DISH_IMAGE_CATALOG = {
  // ──────────────────────────────────────────────────────────────────────────
  // CURATED 37 ARTISANAL BREW & CO. PRODUCTS (100% UNIQUE PHOTOGRAPHS)
  // ──────────────────────────────────────────────────────────────────────────

  // 1. Coffee & Espresso (6 items)
  106: {
    id: 106,
    name: 'Double Espresso (Doppio)',
    slug: 'double-espresso-doppio',
    url: 'https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?auto=format&fit=crop&w=800&q=80',
    alt: 'Rich double espresso with thick golden crema in ceramic cup',
  },
  108: {
    id: 108,
    name: 'Café Cortado (Gibraltar)',
    slug: 'cafe-cortado-gibraltar',
    url: 'https://images.unsplash.com/photo-1534778101976-62847782c213?auto=format&fit=crop&w=800&q=80',
    alt: 'Cortado coffee with textured milk in a faceted glass tumbler',
  },
  110: {
    id: 110,
    name: 'Brew & Co. Flat White',
    slug: 'brew-co-flat-white',
    url: 'https://images.unsplash.com/photo-1577968897966-3d4325b36b61?auto=format&fit=crop&w=800&q=80',
    alt: 'Velvety flat white with intricate latte art in a ceramic cup',
  },
  111: {
    id: 111,
    name: 'Artisanal Cappuccino',
    slug: 'artisanal-cappuccino',
    url: 'https://images.unsplash.com/photo-1571814521680-da02a7da9c97?auto=format&fit=crop&w=800&q=80',
    alt: 'Traditional artisanal cappuccino with velvety aerated foam and cocoa dusting in a ceramic cup',
  },
  113: {
    id: 113,
    name: 'Dark Mocha Supreme',
    slug: 'dark-mocha-supreme',
    url: 'https://images.unsplash.com/photo-1541167760496-1628856ab772?auto=format&fit=crop&w=800&q=80',
    alt: 'Dark chocolate mocha folded with espresso and steamed milk',
  },
  115: {
    id: 115,
    name: 'V60 Single-Origin Pour Over',
    slug: 'v60-single-origin-pour-over',
    url: 'https://images.unsplash.com/photo-1768674150936-1d2044ba32d6?auto=format&fit=crop&w=800&q=80',
    alt: 'Ceramic V60 dripper cone on glass server carafe with artisanal pour-over kettle',
  },

  // 2. Tea & Hot Beverages (3 items)
  119: {
    id: 119,
    name: 'Smoked Earl Grey Bergamot',
    slug: 'smoked-earl-grey-bergamot',
    url: 'https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80',
    alt: 'Aromatic Earl Grey black tea served hot in a clear glass teacup',
  },
  121: {
    id: 121,
    name: 'Ceremonial Matcha Latte',
    slug: 'ceremonial-matcha-latte',
    url: 'https://images.unsplash.com/photo-1536256263959-770b48d82b0a?auto=format&fit=crop&w=800&q=80',
    alt: 'Ceremonial grade green matcha latte with delicate foam art',
  },
  123: {
    id: 123,
    name: 'Belgian Hot Chocolate (70%)',
    slug: 'belgian-hot-chocolate-70',
    url: 'https://images.unsplash.com/photo-1542990253-0d0f5be5f0ed?auto=format&fit=crop&w=800&q=80',
    alt: 'Decadent Belgian molten dark chocolate drink topped with marshmallows',
  },

  // 3. Cold Coffee & Refreshers (4 items)
  124: {
    id: 124,
    name: '18-Hour Kyoto Drip Cold Brew',
    slug: '18-hour-kyoto-drip-cold-brew',
    url: 'https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?auto=format&fit=crop&w=800&q=80',
    alt: 'Slow-steeped 18-hour Kyoto drip cold brew poured over clear ice',
  },
  126: {
    id: 126,
    name: 'Vietnamese Iced Coffee',
    slug: 'vietnamese-iced-coffee',
    url: 'https://images.unsplash.com/photo-1664515725552-d47d97e7da3a?auto=format&fit=crop&w=800&q=80',
    alt: 'Authentic layered Vietnamese iced coffee with sweetened condensed milk and ice',
  },
  127: {
    id: 127,
    name: 'Classic Affogato al Caffè',
    slug: 'classic-affogato-al-caffe',
    url: 'https://images.unsplash.com/photo-1612197127729-c623fa1d0360?auto=format&fit=crop&w=800&q=80',
    alt: 'Scoop of artisan vanilla bean gelato drenched in freshly pulled hot espresso',
  },
  128: {
    id: 128,
    name: 'Citrus Espresso Tonic',
    slug: 'citrus-espresso-tonic',
    url: 'https://images.unsplash.com/photo-1773798795857-15c230fd2e43?auto=format&fit=crop&w=800&q=80',
    alt: 'Sparkling citrus espresso tonic with effervescent bubbles, espresso float, and citrus slice',
  },

  // 4. Bakery & Viennoiserie (5 items)
  132: {
    id: 132,
    name: 'Classic French Butter Croissant',
    slug: 'classic-french-butter-croissant',
    url: 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=800&q=80',
    alt: 'Golden flaky French butter croissant with laminated honeycomb layers',
  },
  133: {
    id: 133,
    name: 'Pain au Chocolat',
    slug: 'pain-au-chocolat',
    url: 'https://images.unsplash.com/photo-1681218424681-b4f8228ecea9?auto=format&fit=crop&w=800&q=80',
    alt: 'Flaky golden pain au chocolat viennoiserie pastry with rich dark chocolate batons',
  },
  134: {
    id: 134,
    name: 'Almond Frangipane Croissant',
    slug: 'almond-frangipane-croissant',
    url: 'https://images.unsplash.com/photo-1769437626773-4b2c1ac0cf6c?auto=format&fit=crop&w=800&q=80',
    alt: 'Twice-baked croissant topped with toasted sliced almonds and powdered sugar',
  },
  135: {
    id: 135,
    name: 'Pistachio Cardamom Cruffin',
    slug: 'pistachio-cardamom-cruffin',
    url: 'https://images.unsplash.com/photo-1769259180150-4a4528fcb222?auto=format&fit=crop&w=800&q=80',
    alt: 'Laminated cardamom knot cruffin pastry filled with rich pistachio cream',
  },
  137: {
    id: 137,
    name: 'Kalamata Olive & Rosemary Focaccia',
    slug: 'kalamata-olive-rosemary-focaccia',
    url: 'https://images.unsplash.com/photo-1767065886239-24a0b8975b24?auto=format&fit=crop&w=800&q=80',
    alt: 'Artisan fermented sourdough focaccia dimpled with kalamata olives, cherry tomatoes, and rosemary',
  },

  // 5. Sandwiches & Toasties (4 items)
  142: {
    id: 142,
    name: 'Smoked Chicken & Truffle Aioli Focaccia',
    slug: 'smoked-chicken-truffle-aioli-focaccia',
    url: 'https://images.unsplash.com/photo-1700937244987-92488ab2ada5?auto=format&fit=crop&w=800&q=80',
    alt: 'Gourmet roasted chicken and truffle aioli on artisan crusty bread with crisp herbs',
  },
  143: {
    id: 143,
    name: 'Pesto Burrata & Roasted Pepper Sourdough',
    slug: 'pesto-burrata-roasted-pepper-sourdough',
    url: 'https://images.unsplash.com/photo-1664192579087-80def67137a3?auto=format&fit=crop&w=800&q=80',
    alt: 'Creamy fresh burrata cheese on toasted sourdough with basil pesto and roasted peppers',
  },
  144: {
    id: 144,
    name: 'Truffled Wild Mushroom & Gruyère Toastie',
    slug: 'truffled-wild-mushroom-gruyere-toastie',
    url: 'https://images.unsplash.com/photo-1737513916865-63c7fd3b67a7?auto=format&fit=crop&w=800&q=80',
    alt: 'Crispy golden toastie with sautéed wild mushrooms and bubbling melted Gruyère cheese',
  },
  148: {
    id: 148,
    name: 'Classic Reuben on Caraway Rye',
    slug: 'classic-reuben-on-caraway-rye',
    url: 'https://images.unsplash.com/photo-1614746526977-fac370353ae8?auto=format&fit=crop&w=800&q=80',
    alt: 'Griddled classic Reuben with thick pastrami, melted Swiss, and sauerkraut on rye',
  },

  // 6. Breakfast & Brunch (4 items)
  150: {
    id: 150,
    name: 'Eggs Florentine on Brioche',
    slug: 'eggs-florentine-on-brioche',
    url: 'https://images.unsplash.com/photo-1785697249208-749c906b69b0?auto=format&fit=crop&w=800&q=80',
    alt: 'Soft poached eggs over wilted spinach on toasted brioche with golden hollandaise',
  },
  151: {
    id: 151,
    name: 'Eggs Royale (Smoked Salmon)',
    slug: 'eggs-royale-smoked-salmon',
    url: 'https://images.unsplash.com/photo-1608039829572-78524f79c4c7?auto=format&fit=crop&w=800&q=80',
    alt: 'Poached eggs and oak-smoked salmon with dill hollandaise on English muffin',
  },
  153: {
    id: 153,
    name: 'Shakshuka Skillet with Crumbled Feta',
    slug: 'shakshuka-skillet-with-crumbled-feta',
    url: 'https://images.unsplash.com/photo-1590412200988-a436970781fa?auto=format&fit=crop&w=800&q=80',
    alt: 'North African spiced tomato and pepper shakshuka with runny eggs and feta',
  },
  155: {
    id: 155,
    name: 'Belgian Buttermilk Waffle Stack',
    slug: 'belgian-buttermilk-waffle-stack',
    url: 'https://images.unsplash.com/photo-1562376552-0d160a2f238d?auto=format&fit=crop&w=800&q=80',
    alt: 'Golden Belgian buttermilk waffles stacked with caramelized bananas and pecans',
  },

  // 7. Salads & Light Bowls (3 items)
  158: {
    id: 158,
    name: 'Wild Grain & Roasted Beet Harvest Bowl',
    slug: 'wild-grain-roasted-beet-harvest-bowl',
    url: 'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80',
    alt: 'Quinoa, roasted ruby beets, baby kale, and goat cheese in an artisan harvest bowl',
  },
  159: {
    id: 159,
    name: 'Charred Burrata & Peach Panzanella',
    slug: 'charred-burrata-peach-panzanella',
    url: 'https://images.unsplash.com/photo-1649400454485-b8ad827f929d?auto=format&fit=crop&w=800&q=80',
    alt: 'Creamy fresh Italian burrata with heirloom tomatoes, charred peaches, and rustic bread',
  },
  162: {
    id: 162,
    name: 'Acai Antioxidant Smoothie Bowl',
    slug: 'acai-antioxidant-smoothie-bowl',
    url: 'https://images.unsplash.com/photo-1627308594190-a057cd4bfac8?auto=format&fit=crop&w=800&q=80',
    alt: 'Organic frozen acai smoothie bowl topped with fresh berries, banana, and chia seeds',
  },

  // 8. Desserts & Patisserie (4 items)
  164: {
    id: 164,
    name: 'Artisanal Espresso Tiramisu Jar',
    slug: 'artisanal-espresso-tiramisu-jar',
    url: 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=800&q=80',
    alt: 'Handcrafted espresso tiramisu layered with mascarpone sabayon and Dutch cocoa',
  },
  165: {
    id: 165,
    name: 'Dark Chocolate Sea Salt Tart (70%)',
    slug: 'dark-chocolate-sea-salt-tart-70',
    url: 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=800&q=80',
    alt: 'Crisp chocolate sablé tart with Valrhona ganache and Maldon sea salt flakes',
  },
  166: {
    id: 166,
    name: 'Burnt Basque Cheesecake Slice',
    slug: 'burnt-basque-cheesecake-slice',
    url: 'https://images.unsplash.com/photo-1623659194932-2029be969235?auto=format&fit=crop&w=800&q=80',
    alt: 'Caramelized Basque burnt cheesecake slice with a rustic dark crust and creamy molten center',
  },
  167: {
    id: 167,
    name: 'Pistachio Raspberry Opera Cake',
    slug: 'pistachio-raspberry-opera-cake',
    url: 'https://images.unsplash.com/photo-1565958011703-44f9829ba187?auto=format&fit=crop&w=800&q=80',
    alt: 'Multi-layered opera cake with almond joconde, pistachio buttercream, and raspberry ganache',
  },
  169: {
    id: 169,
    name: 'French Macaron Trio',
    slug: 'french-macaron-trio',
    url: 'https://images.unsplash.com/photo-1569864358642-9d1684040f43?auto=format&fit=crop&w=800&q=80',
    alt: 'Trio of delicate French macarons with chocolate, vanilla, and salted caramel fillings',
  },

  // 9. Seasonal & Signature Specials (4 items)
  170: {
    id: 170,
    name: 'Smoked Sea Salt Caramel Latte',
    slug: 'smoked-sea-salt-caramel-latte',
    url: 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?auto=format&fit=crop&w=800&q=80',
    alt: 'Specialty latte with smoked sea salt caramel drizzle and velvety steamed milk',
  },
  171: {
    id: 171,
    name: 'Madagascar Vanilla Bean Shakerato',
    slug: 'madagascar-vanilla-bean-shakerato',
    url: 'https://images.unsplash.com/photo-1549746434-6331eadece3c?auto=format&fit=crop&w=800&q=80',
    alt: 'Vigorously hand-shaken double espresso with Madagascar vanilla bean in a chilled coupe glass',
  },
  173: {
    id: 173,
    name: 'Cascara Cold Brew Spritz',
    slug: 'cascara-cold-brew-spritz',
    url: 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=800&q=80',
    alt: 'Sparkling cascara coffee cherry tea spritz with blood orange and fresh mint',
  },
  174: {
    id: 174,
    name: 'Rose Cardamom Iced Latte',
    slug: 'rose-cardamom-iced-latte',
    url: 'https://images.unsplash.com/photo-1786888483050-3b117affda90?auto=format&fit=crop&w=800&q=80',
    alt: 'Chilled double espresso over Damask rose water cordial, oat milk, and cardamom over ice',
  },

  // ──────────────────────────────────────────────────────────────────────────
  // HISTORICAL LEGACY ITEMS (IDs 25–34, Preserved for Staff POS & Receipts)
  // ──────────────────────────────────────────────────────────────────────────
  25: {
    id: 25,
    name: 'Truffle Arancini',
    slug: 'truffle-arancini',
    url: 'https://images.unsplash.com/photo-1541529086526-db283c563270?auto=format&fit=crop&w=800&q=80',
    alt: 'Golden crispy Italian truffle arancini balls served on a rustic plate',
  },
  26: {
    id: 26,
    name: 'Bruschetta Pomodoro',
    slug: 'bruschetta-pomodoro',
    url: 'https://images.unsplash.com/photo-1572695157366-5e585ab2b69f?auto=format&fit=crop&w=800&q=80',
    alt: 'Toasted artisan bruschetta topped with ripe diced tomatoes and fresh basil',
  },
  27: {
    id: 27,
    name: 'Margherita Classica',
    slug: 'margherita-classica',
    url: 'https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?auto=format&fit=crop&w=800&q=80',
    alt: 'Wood-fired Margherita pizza with bubbling mozzarella and fresh basil leaves',
  },
  28: {
    id: 28,
    name: 'Spicy Diavola',
    slug: 'spicy-diavola',
    url: 'https://images.unsplash.com/photo-1628840042765-356cda07504e?auto=format&fit=crop&w=800&q=80',
    alt: 'Wood-fired spicy diavola pepperoni pizza with charred crust and red pepper flakes',
  },
  29: {
    id: 29,
    name: 'Tartufo Bianco Pizza',
    slug: 'tartufo-bianco-pizza',
    url: 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&q=80',
    alt: 'Artisan white truffle mushroom pizza with roasted garlic and ricotta',
  },
  30: {
    id: 30,
    name: 'Fettuccine Truffle Alfredo',
    slug: 'fettuccine-truffle-alfredo',
    url: 'https://images.unsplash.com/photo-1645112411341-6c4fd023714a?auto=format&fit=crop&w=800&q=80',
    alt: 'Creamy fettuccine alfredo pasta with black truffle shavings and fresh parmesan',
  },
  31: {
    id: 31,
    name: 'Grilled Salmon Fillet',
    slug: 'grilled-salmon-fillet',
    url: 'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=800&q=80',
    alt: 'Pan-seared Atlantic salmon fillet with crispy skin, lemon butter, and herbs',
  },
  32: {
    id: 32,
    name: 'Cold Brew Espresso',
    slug: 'cold-brew-espresso',
    url: 'https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?auto=format&fit=crop&w=800&q=80',
    alt: 'Slow-steeped craft cold brew coffee poured over clear ice in a tall glass',
  },
  33: {
    id: 33,
    name: 'Blood Orange Spritz',
    slug: 'blood-orange-spritz',
    url: 'https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=800&q=80',
    alt: 'Sparkling ruby blood orange spritz cocktail garnished with dehydrated citrus',
  },
  34: {
    id: 34,
    name: 'Classic Tiramisu',
    slug: 'classic-tiramisu',
    url: 'https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=800&q=80',
    alt: 'Traditional Italian tiramisu layered with espresso ladyfingers and cocoa dusting',
  },
};

// Also index by slug for resilient string-based lookups
export const DISH_SLUG_MAP = {};
for (const entry of Object.values(DISH_IMAGE_CATALOG)) {
  if (entry.slug) {
    DISH_SLUG_MAP[entry.slug] = entry;
  }
}

// Neutral, culinary category fallbacks (used ONLY when an item has no direct photograph)
export const CATEGORY_FALLBACKS = {
  'coffee & espresso': 'https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?auto=format&fit=crop&w=800&q=80',
  'tea & hot beverages': 'https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=800&q=80',
  'cold coffee & refreshers': 'https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?auto=format&fit=crop&w=800&q=80',
  'bakery & viennoiserie': 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=800&q=80',
  'sandwiches & toasties': 'https://images.unsplash.com/photo-1737513916865-63c7fd3b67a7?auto=format&fit=crop&w=800&q=80',
  'breakfast & brunch': 'https://images.unsplash.com/photo-1785697249208-749c906b69b0?auto=format&fit=crop&w=800&q=80',
  'salads & light bowls': 'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80',
  'desserts & patisserie': 'https://images.unsplash.com/photo-1623659194932-2029be969235?auto=format&fit=crop&w=800&q=80',
  'seasonal & signature specials': 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?auto=format&fit=crop&w=800&q=80',
};

/**
 * Normalizes a dish name into a canonical slug key.
 * e.g. "Double Espresso (Doppio)" -> "double-espresso-doppio"
 */
export function normalizeDishSlug(name) {
  if (!name || typeof name !== 'string') return '';
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

/**
 * Resolves the full image metadata { url, alt } for a given menu item.
 * Evaluates: Direct ID match -> Slug match -> Category fallback -> Global default.
 *
 * @param {Object} item - Menu item object with { id, name, category_name }
 * @returns {{ url: string, alt: string }}
 */
export function getDishImageMeta(item) {
  if (!item) {
    return {
      url: DEFAULT_FALLBACK_IMAGE,
      alt: 'Artisanal culinary specialty from Brew & Co.',
    };
  }

  // 1. Check direct ID match in catalog
  if (item.id && DISH_IMAGE_CATALOG[item.id]) {
    const entry = DISH_IMAGE_CATALOG[item.id];
    return {
      url: entry.url,
      alt: entry.alt || `${item.name} dish presentation`,
    };
  }

  // 2. Check slug match in catalog
  const slug = normalizeDishSlug(item.name);
  if (slug && DISH_SLUG_MAP[slug]) {
    const entry = DISH_SLUG_MAP[slug];
    return {
      url: entry.url,
      alt: entry.alt || `${item.name} dish presentation`,
    };
  }

  // 3. Check category fallback
  if (item.category_name) {
    const catLower = item.category_name.toLowerCase().trim();
    if (CATEGORY_FALLBACKS[catLower]) {
      return {
        url: CATEGORY_FALLBACKS[catLower],
        alt: `${item.name} - ${item.category_name} specialty`,
      };
    }
  }

  // 4. Global fallback
  return {
    url: DEFAULT_FALLBACK_IMAGE,
    alt: item.name ? `${item.name} dish presentation` : 'Brew & Co. culinary dish presentation',
  };
}

/**
 * Resolves the image URL string for a given menu item.
 * @param {Object} item - Menu item object
 * @returns {string} Fully qualified image URL
 */
export function getDishImageUrl(item) {
  return getDishImageMeta(item).url;
}
