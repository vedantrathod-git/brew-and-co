import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { getCategories, getMenuItems, getTables, getOrders, createOrder } from '../services/api';
import { formatUSD } from '../utils/formatters';
import DishImage from '../components/DishImage';

export default function OrdersPage() {
  // Data sources
  const [categories, setCategories] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [tables, setTables] = useState([]);
  const [recentOrders, setRecentOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Menu filters
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // POS Cart State
  // items: Array<{ id: string, menuItemId: number, name: string, price: number|string, quantity: number, specialInstructions: string }>
  const [cart, setCart] = useState([]);
  const [orderType, setOrderType] = useState('dine_in'); // 'dine_in' | 'takeaway'
  const [selectedTableId, setSelectedTableId] = useState('');

  // Submission & Transaction State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [createdOrderSummary, setCreatedOrderSummary] = useState(null);

  // Tab to view recent orders
  const [activeSubTab, setActiveSubTab] = useState('pos'); // 'pos' | 'recent'

  // Load initial menu, tables, and recent orders
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [cats, items, tbls, ords] = await Promise.all([
        getCategories(),
        getMenuItems(),
        getTables(),
        getOrders(),
      ]);

      setCategories(Array.isArray(cats) ? cats : []);
      setMenuItems(Array.isArray(items) ? items : []);
      setTables(Array.isArray(tbls) ? tbls : []);
      setRecentOrders(Array.isArray(ords) ? ords : []);
    } catch (err) {
      console.error('Failed to load POS data:', err);
      setError(err.message || 'Unable to connect to POS services.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Client-side search and category filtering for the menu picker
  const filteredMenuItems = useMemo(() => {
    return menuItems.filter((item) => {
      if (selectedCategory !== 'all' && item.category_id !== Number(selectedCategory)) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const matchesName = item.name && item.name.toLowerCase().includes(query);
        const matchesDesc = item.description && item.description.toLowerCase().includes(query);
        const matchesCategory = item.category_name && item.category_name.toLowerCase().includes(query);
        return matchesName || matchesDesc || matchesCategory;
      }
      return true;
    });
  }, [menuItems, selectedCategory, searchQuery]);

  // Available tables suitable for dine-in
  const availableTables = useMemo(() => {
    return tables.filter((t) => t.status === 'available');
  }, [tables]);

  // Cart operations
  const addToCart = (menuItem) => {
    if (!menuItem.is_available) return;

    setCart((prevCart) => {
      // Find existing entry with the same menu_item_id and no custom notes
      const existingIndex = prevCart.findIndex(
        (c) => c.menuItemId === menuItem.id && !c.specialInstructions
      );

      if (existingIndex > -1) {
        const updated = [...prevCart];
        updated[existingIndex] = {
          ...updated[existingIndex],
          quantity: updated[existingIndex].quantity + 1,
        };
        return updated;
      }

      // Add fresh cart entry
      const newEntry = {
        cartId: `${menuItem.id}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        menuItemId: menuItem.id,
        name: menuItem.name,
        price: menuItem.price,
        quantity: 1,
        specialInstructions: '',
      };
      return [...prevCart, newEntry];
    });

    // Dismiss any stale submit status message
    setSubmitError(null);
  };

  const updateQuantity = (cartId, delta) => {
    setCart((prevCart) => {
      return prevCart
        .map((item) => {
          if (item.cartId === cartId) {
            const newQty = item.quantity + delta;
            return newQty > 0 ? { ...item, quantity: newQty } : null;
          }
          return item;
        })
        .filter(Boolean);
    });
  };

  const removeFromCart = (cartId) => {
    setCart((prevCart) => prevCart.filter((item) => item.cartId !== cartId));
  };

  const updateInstructions = (cartId, instructions) => {
    // Backend model schema restricts to 255 characters
    const sanitized = instructions.slice(0, 255);
    setCart((prevCart) =>
      prevCart.map((item) => (item.cartId === cartId ? { ...item, specialInstructions: sanitized } : item))
    );
  };

  const clearCart = () => {
    if (cart.length > 0) {
      setCart([]);
      setSubmitError(null);
    }
  };

  // Estimated client-side subtotal for staff reference (authoritative calculated by backend)
  const estimatedSubtotal = useMemo(() => {
    return cart.reduce((sum, item) => {
      const price = Number(item.price) || 0;
      return sum + price * item.quantity;
    }, 0);
  }, [cart]);

  // Handle Order Submission
  const handleSubmitOrder = async (e) => {
    e.preventDefault();
    if (cart.length === 0 || isSubmitting) return;

    // Dine-in table validation
    let tableId = null;
    if (orderType === 'dine_in') {
      if (!selectedTableId) {
        setSubmitError('Please select an available dining table for this dine-in order.');
        return;
      }
      tableId = Number(selectedTableId);
    }

    // Build payload matching OrderCreate Pydantic schema
    const payload = {
      table_id: tableId,
      items: cart.map((item) => ({
        menu_item_id: item.menuItemId,
        quantity: item.quantity,
        special_instructions: item.specialInstructions.trim() ? item.specialInstructions.trim() : null,
      })),
      discount: 0.0,
    };

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const createdOrder = await createOrder(payload);

      // Successfully created: record summary, clear cart, refresh floor tables and recent orders
      setCreatedOrderSummary(createdOrder);
      setCart([]);
      setSelectedTableId('');

      // Refresh table status and orders list in background
      const [updatedTables, updatedOrders] = await Promise.all([getTables(), getOrders()]);
      setTables(Array.isArray(updatedTables) ? updatedTables : []);
      setRecentOrders(Array.isArray(updatedOrders) ? updatedOrders : []);
    } catch (err) {
      console.error('Order creation failed:', err);
      // Retain the cart so staff can retry or reassign without losing input
      setSubmitError(err.message || 'Failed to submit order to the kitchen. Please check server status.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-content pos-page-layout">
      {/* POS Sub-Header Navigation Tabs */}
      <div className="pos-subnav-bar">
        <div className="pos-tab-group">
          <button
            type="button"
            className={`pos-nav-tab ${activeSubTab === 'pos' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('pos')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
              <path d="M3 6h18" />
              <path d="M16 10a4 4 0 0 1-8 0" />
            </svg>
            <span>POS Register</span>
            {cart.length > 0 && <span className="tab-counter-badge">{cart.reduce((s, i) => s + i.quantity, 0)}</span>}
          </button>

          <button
            type="button"
            className={`pos-nav-tab ${activeSubTab === 'recent' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('recent')}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 8v4l3 3" />
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span>Recent Orders ({recentOrders.length})</span>
          </button>
        </div>

        <div className="pos-quick-meta">
          <span className="meta-pill">
            <span className="meta-label">Available Tables:</span>
            <strong>{availableTables.length} of {tables.length}</strong>
          </span>
        </div>
      </div>

      {activeSubTab === 'pos' ? (
        <div className="pos-terminal-split">
          {/* ====================================================================
             LEFT PANE: Menu Catalog & Item Selection
             ==================================================================== */}
          <section className="pos-catalog-pane">
            {/* Search & Category Pills */}
            <div className="pos-catalog-toolbar">
              <div className="search-bar">
                <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Quick search dish by name or category..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button type="button" className="search-clear-btn" onClick={() => setSearchQuery('')}>
                    ✕
                  </button>
                )}
              </div>

              <div className="category-pills-bar">
                <button
                  type="button"
                  className={`category-pill ${selectedCategory === 'all' ? 'active' : ''}`}
                  onClick={() => setSelectedCategory('all')}
                >
                  All Items
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    className={`category-pill ${selectedCategory === String(cat.id) ? 'active' : ''}`}
                    onClick={() => setSelectedCategory(String(cat.id))}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Menu Items Grid */}
            {loading ? (
              <div className="pos-items-grid">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <div key={n} className="pos-item-card skeleton-card">
                    <div className="skeleton-line skeleton-badge" />
                    <div className="skeleton-line skeleton-title" />
                    <div className="skeleton-line skeleton-desc short" />
                    <div className="skeleton-footer">
                      <div className="skeleton-line skeleton-price" />
                    </div>
                  </div>
                ))}
              </div>
            ) : error ? (
              <div className="state-card state-error">
                <div className="state-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                </div>
                <div className="state-body">
                  <h3>Unable to Load Menu</h3>
                  <p className="state-message">{error}</p>
                  <button type="button" className="btn btn-primary" onClick={loadData}>
                    Retry
                  </button>
                </div>
              </div>
            ) : filteredMenuItems.length === 0 ? (
              <div className="state-card state-empty">
                <div className="state-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                </div>
                <div className="state-body">
                  <h3>No Dishes Found</h3>
                  <p className="state-message">No menu items match your search.</p>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      setSelectedCategory('all');
                      setSearchQuery('');
                    }}
                  >
                    Clear Filter
                  </button>
                </div>
              </div>
            ) : (
              <div className="pos-items-grid">
                {filteredMenuItems.map((item) => {
                  const isAvailable = item.is_available;
                  const cartCount = cart
                    .filter((c) => c.menuItemId === item.id)
                    .reduce((sum, c) => sum + c.quantity, 0);

                  return (
                    <div
                      key={item.id}
                      className={`pos-item-card ${!isAvailable ? 'pos-item-disabled' : ''}`}
                      onClick={() => isAvailable && addToCart(item)}
                      role="button"
                      tabIndex={isAvailable ? 0 : -1}
                      onKeyDown={(e) => {
                        if (isAvailable && (e.key === 'Enter' || e.key === ' ')) {
                          e.preventDefault();
                          addToCart(item);
                        }
                      }}
                    >
                      <div className="pos-card-header">
                        <span className="category-tag">
                          {item.category_name || `Cat #${item.category_id}`}
                        </span>
                        {!isAvailable ? (
                          <span className="status-pill status-pill-unavailable">
                            <span className="pill-dot" />
                            Out of Stock
                          </span>
                        ) : cartCount > 0 ? (
                          <span className="pos-item-badge">{cartCount} in ticket</span>
                        ) : null}
                      </div>

                      <div className="pos-card-image-wrap">
                        <DishImage
                          item={item}
                          className="pos-card-dish-img"
                          aspectRatio="16/10"
                        />
                      </div>

                      <div className="pos-card-body">
                        <h4 className="pos-item-name">{item.name}</h4>
                        {item.description && (
                          <p className="pos-item-desc">{item.description}</p>
                        )}
                      </div>

                      <div className="pos-card-footer">
                        <span className="pos-item-price">{formatUSD(item.price)}</span>
                        {isAvailable ? (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm pos-add-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              addToCart(item);
                            }}
                            title="Add dish to ticket"
                          >
                            + Add
                          </button>
                        ) : (
                          <span className="pos-sold-out-label">Unavailable</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* ====================================================================
             RIGHT PANE: Current Ticket & Cart Summary
             ==================================================================== */}
          <aside className="pos-cart-pane">
            <div className="pos-ticket-card">
              {/* Ticket Header */}
              <div className="pos-ticket-header">
                <div>
                  <h3 className="pos-ticket-title">Current Ticket</h3>
                  <p className="pos-ticket-subtitle">
                    {cart.reduce((s, i) => s + i.quantity, 0)} items selected
                  </p>
                </div>
                {cart.length > 0 && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={clearCart}
                    title="Clear current cart"
                  >
                    Clear Ticket
                  </button>
                )}
              </div>

              {/* Order Creation Success Banner */}
              {createdOrderSummary && (
                <div className="pos-success-banner">
                  <div className="success-header">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                      <polyline points="22 4 12 14.01 9 11.01" />
                    </svg>
                    <h4>Order Sent to Kitchen</h4>
                  </div>
                  <div className="success-body">
                    <p>
                      <strong>Order Number:</strong>{' '}
                      <code>{createdOrderSummary.order_number}</code>
                    </p>
                    <p>
                      <strong>Type:</strong>{' '}
                      {createdOrderSummary.table_number
                        ? `Table ${createdOrderSummary.table_number}`
                        : 'Takeaway'}
                    </p>
                    <p>
                      <strong>Authoritative Total:</strong>{' '}
                      {formatUSD(createdOrderSummary.total)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm success-dismiss-btn"
                    onClick={() => setCreatedOrderSummary(null)}
                  >
                    Start Next Ticket
                  </button>
                </div>
              )}

              {/* Submit Error Message */}
              {submitError && (
                <div className="pos-error-banner">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <div>
                    <strong>Order Submission Error:</strong>
                    <p>{submitError}</p>
                  </div>
                </div>
              )}

              {/* Order Options: Dine-in vs Takeaway & Table Picker */}
              <div className="pos-order-options">
                <div className="order-type-toggle">
                  <button
                    type="button"
                    className={`order-type-btn ${orderType === 'dine_in' ? 'active' : ''}`}
                    onClick={() => setOrderType('dine_in')}
                  >
                    Dine-in
                  </button>
                  <button
                    type="button"
                    className={`order-type-btn ${orderType === 'takeaway' ? 'active' : ''}`}
                    onClick={() => {
                      setOrderType('takeaway');
                      setSelectedTableId('');
                    }}
                  >
                    Takeaway
                  </button>
                </div>

                {orderType === 'dine_in' && (
                  <div className="table-selector-group">
                    <label htmlFor="table-select" className="filter-label">
                      Assigned Table:
                    </label>
                    <select
                      id="table-select"
                      className="select-control table-dropdown"
                      value={selectedTableId}
                      onChange={(e) => {
                        setSelectedTableId(e.target.value);
                        setSubmitError(null);
                      }}
                    >
                      <option value="">— Select an available table —</option>
                      {tables.map((tbl) => {
                        const isAvail = tbl.status === 'available';
                        return (
                          <option
                            key={tbl.id}
                            value={tbl.id}
                            disabled={!isAvail}
                          >
                            Table {tbl.table_number} ({tbl.capacity} seats) — {tbl.status.toUpperCase()}
                          </option>
                        );
                      })}
                    </select>

                    {availableTables.length === 0 && (
                      <p className="no-tables-warning">
                        ⚠️ No tables are currently available. Switch to Takeaway or complete an active table order.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Cart Line Items */}
              <div className="pos-ticket-items">
                {cart.length === 0 ? (
                  <div className="pos-empty-cart">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                      <path d="M3 6h18" />
                      <path d="M16 10a4 4 0 0 1-8 0" />
                    </svg>
                    <p className="empty-title">Ticket is empty</p>
                    <p className="empty-sub">Select dishes from the menu to build the order.</p>
                  </div>
                ) : (
                  cart.map((item) => (
                    <div key={item.cartId} className="pos-line-item">
                      <div className="line-item-top">
                        <div className="line-item-title-wrap">
                          <span className="line-item-name">{item.name}</span>
                          <span className="line-item-unit-price">
                            {formatUSD(item.price)} each
                          </span>
                        </div>
                        <span className="line-item-total">
                          {formatUSD(Number(item.price) * item.quantity)}
                        </span>
                      </div>

                      {/* Quantity & Remove Row */}
                      <div className="line-item-controls">
                        <div className="qty-control-group">
                          <button
                            type="button"
                            className="qty-btn"
                            onClick={() => updateQuantity(item.cartId, -1)}
                            title="Decrease quantity"
                          >
                            –
                          </button>
                          <span className="qty-value">{item.quantity}</span>
                          <button
                            type="button"
                            className="qty-btn"
                            onClick={() => updateQuantity(item.cartId, 1)}
                            title="Increase quantity"
                          >
                            +
                          </button>
                        </div>

                        <button
                          type="button"
                          className="line-item-remove-btn"
                          onClick={() => removeFromCart(item.cartId)}
                          title="Remove dish"
                        >
                          ✕ Remove
                        </button>
                      </div>

                      {/* Special Instructions Field */}
                      <div className="line-item-notes">
                        <input
                          type="text"
                          className="special-instructions-input"
                          placeholder="Special instructions (e.g. no spice, extra cheese)..."
                          value={item.specialInstructions}
                          maxLength={255}
                          onChange={(e) => updateInstructions(item.cartId, e.target.value)}
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Authoritative Totals & Submit Section */}
              <div className="pos-ticket-footer">
                <div className="summary-row">
                  <span>Estimated Subtotal:</span>
                  <span className="summary-val">{formatUSD(estimatedSubtotal)}</span>
                </div>
                <div className="summary-row summary-subtext-row">
                  <span className="subtext-label">Tax (0% default):</span>
                  <span className="summary-val">{formatUSD(0)}</span>
                </div>
                <div className="summary-divider" />
                <div className="summary-row total-row">
                  <span>Estimated Total:</span>
                  <span className="summary-total-val">{formatUSD(estimatedSubtotal)}</span>
                </div>
                <p className="server-notice">
                  * Authoritative subtotal, tax, and order number are verified by the backend upon submission.
                </p>

                <button
                  type="button"
                  className="btn btn-primary pos-submit-btn"
                  disabled={
                    cart.length === 0 ||
                    isSubmitting ||
                    (orderType === 'dine_in' && !selectedTableId)
                  }
                  onClick={handleSubmitOrder}
                >
                  {isSubmitting ? (
                    <>
                      <span className="btn-spinner" />
                      <span>Sending to Kitchen...</span>
                    </>
                  ) : (
                    `Place Order (${formatUSD(estimatedSubtotal)})`
                  )}
                </button>
              </div>
            </div>
          </aside>
        </div>
      ) : (
        /* ====================================================================
           RECENT ORDERS VIEW
           ==================================================================== */
        <section className="pos-recent-orders-section">
          <div className="recent-orders-header">
            <h3>Recent Active & Completed Orders</h3>
            <button type="button" className="btn btn-secondary btn-sm" onClick={loadData}>
              Refresh Orders
            </button>
          </div>

          {recentOrders.length === 0 ? (
            <div className="state-card state-empty">
              <div className="state-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                </svg>
              </div>
              <div className="state-body">
                <h3>No Recent Orders</h3>
                <p className="state-message">No orders have been submitted to the POS system yet.</p>
              </div>
            </div>
          ) : (
            <div className="recent-orders-grid">
              {recentOrders.map((ord) => {
                const statusClasses = {
                  pending: 'status-pill-occupied',
                  in_progress: 'status-pill-occupied',
                  served: 'status-pill-reserved',
                  completed: 'status-pill-available',
                  cancelled: 'status-pill-unavailable',
                }[ord.status] || 'status-pill-unavailable';

                return (
                  <article key={ord.id} className="recent-order-card">
                    <header className="recent-card-top">
                      <span className="order-num-code">{ord.order_number}</span>
                      <span className={`status-pill ${statusClasses}`}>
                        <span className="pill-dot" />
                        {ord.status.toUpperCase()}
                      </span>
                    </header>

                    <div className="recent-card-body">
                      <div className="recent-type-row">
                        <span className="recent-label">Service Type:</span>
                        <strong className="recent-table-name">
                          {ord.table_number ? `Table ${ord.table_number}` : 'Takeaway'}
                        </strong>
                      </div>

                      <div className="recent-items-list">
                        <span className="recent-label">Ordered Items ({ord.items ? ord.items.length : 0}):</span>
                        <ul className="recent-items-bullet">
                          {(ord.items || []).slice(0, 3).map((item, idx) => (
                            <li key={idx}>
                              {item.quantity}× {item.menu_item_name || `Item #${item.menu_item_id}`}
                              {item.special_instructions ? ` ("${item.special_instructions}")` : ''}
                            </li>
                          ))}
                          {(ord.items || []).length > 3 && (
                            <li className="more-items-text">
                              + {(ord.items || []).length - 3} more items
                            </li>
                          )}
                        </ul>
                      </div>
                    </div>

                    <footer className="recent-card-bottom">
                      <div className="recent-total-val">{formatUSD(ord.total)}</div>
                      <span className="recent-date">
                        {new Date(ord.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </footer>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
