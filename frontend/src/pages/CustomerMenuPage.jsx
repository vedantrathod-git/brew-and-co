import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ProductCard from '../components/ProductCard';
import ProductDetailModal from '../components/ProductDetailModal';
import { getPublicMenu } from '../services/api';
import { filterCuratedMenu } from '../utils/curatedCatalog';

export default function CustomerMenuPage({ initialCategoryId }) {
  const [categories, setCategories] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [selectedCategoryId, setSelectedCategoryId] = useState(
    initialCategoryId ? Number(initialCategoryId) : 'all'
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProduct, setSelectedProduct] = useState(null);

  const loadMenu = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rawData = await getPublicMenu();
      const data = filterCuratedMenu(rawData);
      setCategories(Array.isArray(data.categories) ? data.categories : []);
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch (err) {
      console.error('Failed to load customer menu:', err);
      setError('Unable to load our menu catalog right now. Please verify your connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMenu();
  }, [loadMenu]);

  // Synchronize category if prop changes (e.g. from navigation)
  useEffect(() => {
    if (initialCategoryId) {
      setSelectedCategoryId(Number(initialCategoryId));
    }
  }, [initialCategoryId]);

  // Filtered Items (Client-side fast search & category match)
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Category filter
      if (selectedCategoryId !== 'all' && item.category_id !== Number(selectedCategoryId)) {
        return false;
      }
      // Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchName = item.name && item.name.toLowerCase().includes(q);
        const matchDesc = item.description && item.description.toLowerCase().includes(q);
        const matchCat = item.category_name && item.category_name.toLowerCase().includes(q);
        return matchName || matchDesc || matchCat;
      }
      return true;
    });
  }, [items, selectedCategoryId, searchQuery]);

  const activeCategoryName = useMemo(() => {
    if (selectedCategoryId === 'all') return 'All Selections';
    const cat = categories.find((c) => c.id === Number(selectedCategoryId));
    return cat ? cat.name : 'All Selections';
  }, [categories, selectedCategoryId]);

  return (
    <div className="customer-menu-container">
      {/* Menu Page Header */}
      <header className="customer-menu-header">
        <span className="section-eyebrow">Fresh &bull; Single-Estate &bull; Baked Daily</span>
        <h1 className="customer-menu-title">The Brew &amp; Co. Menu</h1>
        <p className="customer-menu-subtitle">
          Discover our curated collection of 37 artisanal selections across specialty coffees,
          teas, morning viennoiserie, hearth toasties, farm brunch, and French patisserie.
        </p>
      </header>

      {/* Interactive Controls Bar: Category Pills + Search */}
      <div className="customer-controls-bar">
        {/* Search Input */}
        <div className="customer-search-box">
          <svg className="customer-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="search"
            className="customer-search-input"
            placeholder="Search by name, ingredients, or notes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search menu items"
          />
          {searchQuery && (
            <button
              type="button"
              className="customer-search-clear"
              onClick={() => setSearchQuery('')}
              aria-label="Clear search"
            >
              &times;
            </button>
          )}
        </div>

        {/* Category Navigation Pills */}
        <nav className="customer-category-pills" aria-label="Menu Category Filter">
          <button
            type="button"
            className={`category-pill ${selectedCategoryId === 'all' ? 'active' : ''}`}
            onClick={() => setSelectedCategoryId('all')}
          >
            All Selections ({items.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              className={`category-pill ${selectedCategoryId === cat.id ? 'active' : ''}`}
              onClick={() => setSelectedCategoryId(cat.id)}
            >
              {cat.name} ({cat.item_count})
            </button>
          ))}
        </nav>
      </div>

      {/* Results Meta Info */}
      <div className="customer-results-meta">
        <h2 className="current-view-title">{activeCategoryName}</h2>
        <span className="current-results-count">
          Showing {filteredItems.length} {filteredItems.length === 1 ? 'item' : 'items'}
        </span>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="menu-loading-box">
          <div className="state-spinner" />
          <p className="loading-text">Preparing fresh café selections...</p>
        </div>
      ) : error ? (
        <div className="menu-error-box">
          <p className="error-text">{error}</p>
          <button type="button" className="retry-btn" onClick={loadMenu}>
            Retry Connection
          </button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="menu-empty-results">
          <div className="empty-results-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </div>
          <h3 className="empty-results-title">No selections match your search</h3>
          <p className="empty-results-subtext">
            {searchQuery
              ? `We couldn't find anything matching "${searchQuery}". Try searching for "croissant", "espresso", or "burrata".`
              : 'No items are available in this department currently.'}
          </p>
          <button
            type="button"
            className="clear-filters-btn"
            onClick={() => {
              setSearchQuery('');
              setSelectedCategoryId('all');
            }}
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="customer-products-grid">
          {filteredItems.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onSelect={setSelectedProduct}
            />
          ))}
        </div>
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}
    </div>
  );
}
