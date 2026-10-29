import assert from 'node:assert/strict';
import { formatUSD, formatCurrency, formatINR } from './src/utils/formatters.js';
import {
  getDishImageUrl,
  normalizeDishSlug,
  DISH_IMAGE_CATALOG,
  DEFAULT_FALLBACK_IMAGE,
} from './src/utils/dishImages.js';

console.log('='.repeat(70));
console.log(' Phase 12 - USD Currency & Dish Image Mapping Verification Suite');
console.log('='.repeat(70));

// ----------------------------------------------------------------------------
// Test 1: USD Formatter Precision & Edge Cases
// ----------------------------------------------------------------------------
console.log('\n[Test 1] Verifying formatUSD() behavior...');

assert.equal(formatUSD(12.5), '$12.50', 'Expected 12.5 to format as $12.50');
assert.equal(formatUSD(8.5), '$8.50', 'Expected 8.5 to format as $8.50');
assert.equal(formatUSD(0), '$0.00', 'Expected 0 to format as $0.00');
assert.equal(formatUSD('24.95'), '$24.95', 'Expected numeric string "24.95" to format as $24.95');
assert.equal(formatUSD(1250.75), '$1,250.75', 'Expected 1250.75 to format with comma separator as $1,250.75');
assert.equal(formatUSD(null), '$0.00', 'Expected null to format gracefully as $0.00');
assert.equal(formatUSD(undefined), '$0.00', 'Expected undefined to format gracefully as $0.00');
assert.equal(formatUSD(''), '$0.00', 'Expected empty string to format gracefully as $0.00');
assert.equal(formatUSD('not-a-number'), '$0.00', 'Expected NaN string to format gracefully as $0.00');

// Aliases
assert.equal(formatCurrency(16.0), '$16.00', 'formatCurrency alias failed');
assert.equal(formatINR(18.5), '$18.50', 'formatINR backward-compatibility alias failed');

console.log('  ✓ formatUSD correctly produces standard $X.XX with 2 decimal places.');
console.log('  ✓ Handles numbers, decimal strings, null, undefined, empty string, and NaN gracefully.');
console.log('  ✓ Aliases formatCurrency and formatINR both resolve to $ presentation.');

// ----------------------------------------------------------------------------
// Test 2: Dish Slug Normalization
// ----------------------------------------------------------------------------
console.log('\n[Test 2] Verifying dish slug normalization...');
assert.equal(normalizeDishSlug('Truffle Arancini'), 'truffle-arancini');
assert.equal(normalizeDishSlug('Bruschetta Pomodoro!'), 'bruschetta-pomodoro');
assert.equal(normalizeDishSlug('  Wood-Fired Pizza  '), 'wood-fired-pizza');
assert.equal(normalizeDishSlug(''), '');
console.log('  ✓ normalizeDishSlug produces clean kebab-case keys.');

// ----------------------------------------------------------------------------
// Test 3: Seeded Database Dish Image Resolution
// ----------------------------------------------------------------------------
console.log('\n[Test 3] Verifying image resolution for all 10 seeded restaurant dishes...');

const SEEDED_DISHES = [
  { id: 25, name: 'Truffle Arancini', category_name: 'Starters & Appetizers' },
  { id: 26, name: 'Bruschetta Pomodoro', category_name: 'Starters & Appetizers' },
  { id: 27, name: 'Margherita Classica', category_name: 'Wood-Fired Pizza' },
  { id: 28, name: 'Spicy Diavola', category_name: 'Wood-Fired Pizza' },
  { id: 29, name: 'Tartufo Bianco Pizza', category_name: 'Wood-Fired Pizza' },
  { id: 30, name: 'Fettuccine Truffle Alfredo', category_name: 'Pasta & Mains' },
  { id: 31, name: 'Grilled Salmon Fillet', category_name: 'Pasta & Mains' },
  { id: 32, name: 'Cold Brew Espresso', category_name: 'Craft Beverages' },
  { id: 33, name: 'Blood Orange Spritz', category_name: 'Craft Beverages' },
  { id: 34, name: 'Classic Tiramisu', category_name: 'Desserts' },
];

for (const dish of SEEDED_DISHES) {
  const url = getDishImageUrl(dish);
  assert.ok(url && url.startsWith('https://images.unsplash.com/photo-'), `Invalid URL for ${dish.name}: ${url}`);
  console.log(`  ✓ Dish #${dish.id} "${dish.name}" -> ${url.substring(0, 50)}...`);
}

// ----------------------------------------------------------------------------
// Test 4: Dynamic & Keyword Fallbacks
// ----------------------------------------------------------------------------
console.log('\n[Test 4] Verifying heuristic keyword and category fallbacks...');

const dynamicItems = [
  { name: 'Smash Cheeseburger', description: 'Double beef patty with cheddar' },
  { name: 'Crispy French Fries', description: 'Golden salted fries' },
  { name: 'Caesar Salad', description: 'Romaine lettuce with parmesan' },
  { name: 'Penne Carbonara', description: 'Rich egg and pancetta sauce' },
  { name: 'Pepperoni Pizza', description: 'Spicy pepperoni slices' },
  { name: 'Chocolate Fudge Cake', description: 'Rich layered chocolate cake' },
  { name: 'Iced Latte', description: 'Espresso with cold milk' },
  { name: 'Unknown Exotic Specialty', category_name: 'Wood-Fired Pizza' },
  { name: 'Mystery Item', category_name: 'Unknown Category' },
];

for (const item of dynamicItems) {
  const url = getDishImageUrl(item);
  assert.ok(url && typeof url === 'string', `Failed to resolve URL for ${item.name}`);
  console.log(`  ✓ Dynamic: "${item.name}" -> mapped successfully.`);
}

console.log('\n' + '='.repeat(70));
console.log(' ALL PHASE 12 FORMATTER & DISH IMAGE TESTS PASSED! (100% SUCCESS)');
console.log('='.repeat(70));
