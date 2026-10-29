import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getCategories, getMenuItems } from '../services/api';
import { formatUSD } from '../utils/formatters';
import DishImage from '../components/DishImage';

export default function MenuPage() {
  const [categories, setCategories] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [availabilityFilter, setAvailabilityFilter] = useState('all'); // 'all', 'available', 'unavailable'
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params = {};
      if (selectedCategory !== 'all') {
        params.categoryId = selectedCategory;
      }
      if (availabilityFilter === 'available') {
        params.isAvailable = true;
      } else if (availabilityFilter === 'unavailable') {
        params.isAvailable = false;
      }

      const [categoriesData, itemsData] = await Promise.all([
        getCategories(),
        getMenuItems(params),
      ]);

      setCategories(Array.isArray(categoriesData) ? categoriesData : []);
      setMenuItems(Array.isArray(itemsData) ? itemsData : []);
    } catch (err) {
      console.error('Failed to load menu data:', err);
      setError(err.message || 'Failed to communicate with the restaurant backend.');
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, availabilityFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Client-side text search filtering
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return menuItems;
    const query = searchQuery.toLowerCase().trim();
    return menuItems.filter((item) => {
      const nameMatch = item.name && item.name.toLowerCase().includes(query);
      const descMatch = item.description && item.description.toLowerCase().includes(query);
      const catMatch = item.category_name && item.category_name.toLowerCase().includes(query);
      return nameMatch || descMatch || catMatch;
    });
  }, [menuItems, searchQuery]);

  // Calculated operational counts
  const totalItemsCount = menuItems.length;
  const availableCount = menuItems.filter((item) => item.is_available).length;
  const outOfStockCount = totalItemsCount - availableCount;

  return (
    <div className="page-content">
      {/* Menu Overview KPI Metrics */}
      <section className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Dishes</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l4 2" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : totalItemsCount}</div>
          <div className="metric-subtext">Active on catalog</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Categories</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 6h16M4 12h16M4 18h7" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : categories.length}</div>
          <div className="metric-subtext">Configured sections</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Available for Order</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : availableCount}</div>
          <div className="metric-subtext">In-stock and sellable</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Out of Stock</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : outOfStockCount}</div>
          <div className="metric-subtext">Unavailable in kitchen</div>
        </div>
      </section>

      {/* Toolbar: Search, Availability Filter & Category Pills */}
      <section className="filters-section">
        <div className="filters-top-row">
          <div className="search-bar">
            <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Search dishes by name, ingredients, or category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery('')}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          <div className="availability-filter-group">
            <label htmlFor="availability-select" className="filter-label">Availability:</label>
            <select
              id="availability-select"
              className="select-control"
              value={availabilityFilter}
              onChange={(e) => setAvailabilityFilter(e.target.value)}
            >
              <option value="all">All Dishes</option>
              <option value="available">Available Only</option>
              <option value="unavailable">Out of Stock Only</option>
            </select>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="category-pills-bar">
          <button
            type="button"
            className={`category-pill ${selectedCategory === 'all' ? 'active' : ''}`}
            onClick={() => setSelectedCategory('all')}
          >
            All Categories
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              className={`category-pill ${selectedCategory === cat.id ? 'active' : ''}`}
              onClick={() => setSelectedCategory(cat.id)}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </section>

      {/* View States: Error, Loading, Empty, or Cards */}
      {error ? (
        <div className="state-card state-error">
          <div className="state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div className="state-body">
            <h3>Unable to Load Menu Items</h3>
            <p className="state-message">{error}</p>
            <button type="button" className="btn btn-primary" onClick={loadData}>
              Retry Connection
            </button>
          </div>
        </div>
      ) : loading ? (
        <div className="menu-grid">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="menu-card skeleton-card">
              <div className="skeleton-line skeleton-badge" />
              <div className="skeleton-line skeleton-title" />
              <div className="skeleton-line skeleton-desc" />
              <div className="skeleton-line skeleton-desc short" />
              <div className="skeleton-footer">
                <div className="skeleton-line skeleton-price" />
                <div className="skeleton-line skeleton-pill" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="state-card state-empty">
          <div className="state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 21h8" />
              <path d="M12 17v4" />
              <path d="M7 4h10l-1 9H8L7 4Z" />
            </svg>
          </div>
          <div className="state-body">
            <h3>No Menu Items Found</h3>
            <p className="state-message">
              {searchQuery || selectedCategory !== 'all' || availabilityFilter !== 'all'
                ? 'No menu items match your active search and filter criteria.'
                : 'There are currently no dishes recorded in the database.'}
            </p>
            {(searchQuery || selectedCategory !== 'all' || availabilityFilter !== 'all') ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setSelectedCategory('all');
                  setAvailabilityFilter('all');
                  setSearchQuery('');
                }}
              >
                Clear All Filters
              </button>
            ) : (
              <button type="button" className="btn btn-secondary" onClick={loadData}>
                Refresh Catalog
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="menu-grid">
          {filteredItems.map((item) => {
            const categoryLabel =
              item.category_name ||
              categories.find((c) => c.id === item.category_id)?.name ||
              `Category #${item.category_id}`;

            return (
              <article key={item.id} className="menu-card">
                <header className="card-top">
                  <span className="category-tag">{categoryLabel}</span>
                  <span
                    className={`status-pill ${
                      item.is_available ? 'status-pill-available' : 'status-pill-unavailable'
                    }`}
                  >
                    <span className="pill-dot" />
                    {item.is_available ? 'Available' : 'Out of Stock'}
                  </span>
                </header>

                <div className="menu-card-image-wrap">
                  <DishImage
                    item={{ ...item, category_name: categoryLabel }}
                    className="menu-card-dish-img"
                    aspectRatio="16/10"
                  />
                </div>

                <div className="card-main">
                  <h3 className="item-title">{item.name}</h3>
                  <p className="item-desc">
                    {item.description ? item.description : <span className="no-desc">No description provided</span>}
                  </p>
                </div>

                <footer className="card-bottom">
                  <div className="item-price">{formatUSD(item.price)}</div>
                  {item.prep_time_minutes !== null && item.prep_time_minutes !== undefined && (
                    <div className="item-prep" title="Kitchen preparation time">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                      <span>{item.prep_time_minutes} min</span>
                    </div>
                  )}
                </footer>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
