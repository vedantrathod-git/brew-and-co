import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getOrders, updateOrder, getOrder, settleOrderCashStaff } from '../services/api';
import { formatUSD, formatDateTime, formatTime } from '../utils/formatters';

// Semantic status configurations consistent with the POS and KDS design tokens
const STATUS_META = {
  pending: {
    label: 'Pending',
    pillClass: 'status-pill-occupied',
    badgeClass: 'badge-pending',
    indicator: 'Queued',
  },
  in_progress: {
    label: 'In Preparation',
    pillClass: 'status-pill-reserved',
    badgeClass: 'badge-in-progress',
    indicator: 'Cooking',
  },
  served: {
    label: 'Served',
    pillClass: 'status-pill-available',
    badgeClass: 'badge-served',
    indicator: 'Plated',
  },
  completed: {
    label: 'Completed',
    pillClass: 'status-pill-available',
    badgeClass: 'badge-completed',
    indicator: 'Completed',
  },
  cancelled: {
    label: 'Cancelled',
    pillClass: 'status-pill-unavailable',
    badgeClass: 'badge-cancelled',
    indicator: 'Voided',
  },
};

export default function OrderHistoryPage({ onNavigate }) {
  // Main Data States
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'active', 'pending', 'in_progress', 'served', 'completed', 'cancelled'
  const [typeFilter, setTypeFilter] = useState('all'); // 'all', 'dine_in', 'takeaway'
  const [sortOrder, setSortOrder] = useState('desc'); // 'desc' (newest first) or 'asc' (oldest first)

  // Drawer & Inspection State
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [confirmCancelModal, setConfirmCancelModal] = useState(false);

  // Ref to prevent duplicate overlapping network requests
  const isFetchingRef = useRef(false);

  // ── 1. Fetch Orders from Backend ──────────────────────────────────────────
  const fetchOrders = useCallback(async (isManual = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    if (isManual) {
      setIsRefreshing(true);
    }

    try {
      const data = await getOrders();
      setOrders(Array.isArray(data) ? data : []);
      setLastRefreshedAt(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to load orders:', err);
      // Only set blocking error if we don't already have data
      if (orders.length === 0) {
        setError(err.message || 'Unable to communicate with order service.');
      } else {
        setActionError(`Background refresh failed: ${err.message || 'Server error'}`);
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      isFetchingRef.current = false;
    }
  }, [orders.length]);

  useEffect(() => {
    fetchOrders(false);
  }, [fetchOrders]);

  // ── 2. Sync Selected Order Details ────────────────────────────────────────
  useEffect(() => {
    if (!selectedOrderId) {
      setSelectedOrder(null);
      return;
    }

    // First populate from local state cache immediately for instant UI
    const found = orders.find((o) => o.id === selectedOrderId);
    if (found) {
      setSelectedOrder(found);
    }

    // Then re-fetch fresh order from API to guarantee full nested integrity
    let isCancelled = false;
    setIsLoadingDetail(true);
    setActionError(null);
    setActionSuccess(null);

    getOrder(selectedOrderId)
      .then((freshOrder) => {
        if (!isCancelled && freshOrder) {
          setSelectedOrder(freshOrder);
          // Also update in list if attributes changed
          setOrders((prev) =>
            prev.map((o) => (o.id === freshOrder.id ? { ...o, ...freshOrder } : o))
          );
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.error(`Failed to fetch order #${selectedOrderId}:`, err);
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setIsLoadingDetail(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedOrderId, orders]);

  // Handle ESC key to close drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (confirmCancelModal) {
          setConfirmCancelModal(false);
        } else if (selectedOrderId) {
          setSelectedOrderId(null);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedOrderId, confirmCancelModal]);

  // ── 3. Derived Metrics (Strictly from Server Data) ─────────────────────────
  const metrics = useMemo(() => {
    const total = orders.length;
    const active = orders.filter((o) => ['pending', 'in_progress', 'served'].includes(o.status)).length;
    const completed = orders.filter((o) => o.status === 'completed').length;
    const cancelled = orders.filter((o) => o.status === 'cancelled').length;

    // Authoritative total sum from all non-cancelled orders
    const grossValue = orders
      .filter((o) => o.status !== 'cancelled')
      .reduce((sum, o) => sum + Number(o.total || 0), 0);

    return { total, active, completed, cancelled, grossValue };
  }, [orders]);

  // ── 4. Filtered & Sorted Orders ───────────────────────────────────────────
  const filteredOrders = useMemo(() => {
    let result = [...orders];

    // Search by Order Number or Table Number
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((o) => {
        const orderNumMatch = o.order_number && o.order_number.toLowerCase().includes(q);
        const tableMatch =
          o.table_number &&
          (o.table_number.toLowerCase().includes(q) ||
            `table ${o.table_number}`.toLowerCase().includes(q) ||
            `t${o.table_number}`.toLowerCase().includes(q));
        return orderNumMatch || tableMatch;
      });
    }

    // Status Filter
    if (statusFilter === 'active') {
      result = result.filter((o) => ['pending', 'in_progress', 'served'].includes(o.status));
    } else if (statusFilter !== 'all') {
      result = result.filter((o) => o.status === statusFilter);
    }

    // Order Type Filter
    if (typeFilter === 'dine_in') {
      result = result.filter((o) => o.table_id !== null && o.table_id !== undefined);
    } else if (typeFilter === 'takeaway') {
      result = result.filter((o) => o.table_id === null || o.table_id === undefined);
    }

    // Sort order
    result.sort((a, b) => {
      const timeA = new Date(a.created_at).getTime() || a.id;
      const timeB = new Date(b.created_at).getTime() || b.id;
      return sortOrder === 'desc' ? timeB - timeA : timeA - timeB;
    });

    return result;
  }, [orders, searchQuery, statusFilter, typeFilter, sortOrder]);

  // ── 5. Status Transition Handler (Adhering to State Machine) ───────────────
  const handleTransition = async (targetStatus) => {
    if (!selectedOrder) return;
    setIsUpdatingStatus(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      const updated = await updateOrder(selectedOrder.id, { status: targetStatus });
      setSelectedOrder(updated);

      // Update in main list
      setOrders((prev) =>
        prev.map((o) => (o.id === updated.id ? { ...o, ...updated } : o))
      );

      setActionSuccess(`Order #${updated.order_number} transitioned to "${STATUS_META[targetStatus]?.label || targetStatus}".`);
      setConfirmCancelModal(false);
    } catch (err) {
      console.error(`Failed to update status to ${targetStatus}:`, err);
      setActionError(
        err.message || 'Server rejected status transition. Please refresh and try again.'
      );
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleSettleCash = async () => {
    if (!selectedOrder || isUpdatingStatus) return;
    setIsUpdatingStatus(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      await settleOrderCashStaff(selectedOrder.id);
      setSelectedOrder((prev) => ({
        ...prev,
        payment_status: 'paid',
        payment_method: 'cash',
      }));
      setOrders((prev) =>
        prev.map((o) =>
          o.id === selectedOrder.id
            ? { ...o, payment_status: 'paid', payment_method: 'cash' }
            : o
        )
      );
      setActionSuccess(`Order #${selectedOrder.order_number} marked as Paid (Cash).`);
    } catch (err) {
      setActionError(err.message || 'Failed to settle cash payment.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  // Compute allowed transitions for selected order based on backend state machine
  const nextAllowedActions = useMemo(() => {
    if (!selectedOrder) return [];
    const isTakeaway = selectedOrder.table_id === null || selectedOrder.table_id === undefined;
    const cur = selectedOrder.status;

    if (cur === 'completed' || cur === 'cancelled') {
      return []; // Terminal state
    }

    const actions = [];
    if (!isTakeaway) {
      // Dine-in transitions
      if (cur === 'pending') {
        actions.push({ status: 'in_progress', label: 'Start Preparation', variant: 'primary' });
        actions.push({ status: 'cancelled', label: 'Cancel Order', variant: 'danger' });
      } else if (cur === 'in_progress') {
        actions.push({ status: 'served', label: 'Mark as Served', variant: 'primary' });
        actions.push({ status: 'cancelled', label: 'Cancel Order', variant: 'danger' });
      } else if (cur === 'served') {
        actions.push({ status: 'completed', label: 'Complete & Close Bill', variant: 'success' });
        actions.push({ status: 'cancelled', label: 'Cancel Order', variant: 'danger' });
      }
    } else {
      // Takeaway transitions
      if (cur === 'pending') {
        actions.push({ status: 'in_progress', label: 'Start Preparation', variant: 'secondary' });
        actions.push({ status: 'completed', label: 'Complete & Hand Over', variant: 'success' });
        actions.push({ status: 'cancelled', label: 'Cancel Order', variant: 'danger' });
      } else if (cur === 'in_progress' || cur === 'served') {
        actions.push({ status: 'completed', label: 'Complete & Hand Over', variant: 'success' });
        actions.push({ status: 'cancelled', label: 'Cancel Order', variant: 'danger' });
      }
    }

    return actions;
  }, [selectedOrder]);

  return (
    <div className="page-content order-history-page">
      {/* ── Top Bar / Header ────────────────────────────────────────────── */}
      <section className="history-top-bar">
        <div className="history-top-info">
          <h2 className="history-heading">Order Management & Audit</h2>
          <p className="history-subheading">
            Browse live and historical tickets, inspect guest line items, filter by fulfillment status, and track order lifecycles.
          </p>
        </div>

        <div className="history-top-actions">
          {lastRefreshedAt && (
            <span className="history-sync-meta">
              <span className="sync-pulse" />
              Synced at {formatTime(lastRefreshedAt)}
            </span>
          )}

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => fetchOrders(true)}
            disabled={isRefreshing || loading}
            title="Refresh order records from server"
          >
            <svg
              className={`btn-icon ${isRefreshing ? 'spin-icon' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
              <path d="M16 21h5v-5" />
            </svg>
            <span>{isRefreshing ? 'Syncing...' : 'Refresh'}</span>
          </button>
        </div>
      </section>

      {/* ── Operational Summary Cards ───────────────────────────────────── */}
      <section className="history-summary-grid">
        <div className="history-stat-card">
          <div className="stat-card-header">
            <span className="stat-label">Total Orders</span>
            <span className="stat-icon-wrap icon-slate">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </span>
          </div>
          <div className="stat-value">{metrics.total}</div>
          <div className="stat-subtext">Lifetime recorded tickets</div>
        </div>

        <div className="history-stat-card">
          <div className="stat-card-header">
            <span className="stat-label">Active Orders</span>
            <span className="stat-icon-wrap icon-amber">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </span>
          </div>
          <div className="stat-value text-amber">{metrics.active}</div>
          <div className="stat-subtext">Pending, in-prep, or served</div>
        </div>

        <div className="history-stat-card">
          <div className="stat-card-header">
            <span className="stat-label">Completed Orders</span>
            <span className="stat-icon-wrap icon-emerald">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </span>
          </div>
          <div className="stat-value text-emerald">{metrics.completed}</div>
          <div className="stat-subtext">Fulfilled & settled tickets</div>
        </div>

        <div className="history-stat-card">
          <div className="stat-card-header">
            <span className="stat-label">Gross Order Value</span>
            <span className="stat-icon-wrap icon-terracotta">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="1" x2="12" y2="23" />
                <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </span>
          </div>
          <div className="stat-value text-terracotta">{formatUSD(metrics.grossValue)}</div>
          <div className="stat-subtext">From all non-cancelled orders</div>
        </div>
      </section>

      {/* ── Toolbar & Filter Row ────────────────────────────────────────── */}
      <section className="history-toolbar-card">
        <div className="history-toolbar-row">
          {/* Search Box */}
          <div className="history-search-wrap">
            <svg
              className="search-input-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="form-input history-search-input"
              placeholder="Search by Order # or Table #..."
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

          {/* Type Filter */}
          <div className="history-select-wrap">
            <label htmlFor="type-filter" className="filter-label">Type:</label>
            <select
              id="type-filter"
              className="form-select history-type-select"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <option value="all">All Service Types</option>
              <option value="dine_in">Dine-In Only</option>
              <option value="takeaway">Takeaway Only</option>
            </select>
          </div>

          {/* Sort Order */}
          <div className="history-select-wrap">
            <label htmlFor="sort-filter" className="filter-label">Sort:</label>
            <select
              id="sort-filter"
              className="form-select history-sort-select"
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
            >
              <option value="desc">Newest First</option>
              <option value="asc">Oldest First</option>
            </select>
          </div>
        </div>

        {/* Status Filter Pills */}
        <div className="history-status-pills">
          <span className="pills-label">Status:</span>
          {[
            { id: 'all', label: 'All Orders', count: orders.length },
            { id: 'active', label: 'Active', count: metrics.active },
            { id: 'pending', label: 'Pending', count: orders.filter((o) => o.status === 'pending').length },
            { id: 'in_progress', label: 'In Prep', count: orders.filter((o) => o.status === 'in_progress').length },
            { id: 'served', label: 'Served', count: orders.filter((o) => o.status === 'served').length },
            { id: 'completed', label: 'Completed', count: metrics.completed },
            { id: 'cancelled', label: 'Cancelled', count: metrics.cancelled },
          ].map((pill) => {
            const isSelected = statusFilter === pill.id;
            return (
              <button
                key={pill.id}
                type="button"
                className={`filter-pill ${isSelected ? 'active' : ''}`}
                onClick={() => setStatusFilter(pill.id)}
              >
                <span>{pill.label}</span>
                <span className="filter-pill-count">{pill.count}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* ── Error Banner ────────────────────────────────────────────────── */}
      {error && (
        <div className="alert-banner alert-danger mb-4">
          <div className="alert-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{error}</span>
          </div>
          <button
            type="button"
            className="btn btn-outline-danger btn-xs"
            onClick={() => fetchOrders(true)}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Orders List / Table View ────────────────────────────────────── */}
      <section className="history-table-container">
        {loading && orders.length === 0 ? (
          <div className="history-state-box">
            <div className="state-spinner" />
            <h3>Loading Order Records...</h3>
            <p>Retrieving authoritative order data from PostgreSQL.</p>
          </div>
        ) : filteredOrders.length === 0 ? (
          <div className="history-state-box">
            <div className="state-icon-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
            </div>
            {orders.length === 0 ? (
              <>
                <h3>No Orders Recorded Yet</h3>
                <p>The database currently contains zero tickets. Place an order via the POS Terminal to start auditing tickets.</p>
                {onNavigate && (
                  <button
                    type="button"
                    className="btn btn-primary mt-3"
                    onClick={() => onNavigate('orders')}
                  >
                    Open POS Terminal
                  </button>
                )}
              </>
            ) : (
              <>
                <h3>No Matching Orders Found</h3>
                <p>No orders match the current filter criteria or search query "{searchQuery}".</p>
                <button
                  type="button"
                  className="btn btn-secondary mt-3"
                  onClick={() => {
                    setSearchQuery('');
                    setStatusFilter('all');
                    setTypeFilter('all');
                  }}
                >
                  Clear All Filters
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="history-table-wrap">
            <table className="history-orders-table">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Service Type</th>
                  <th>Items Preview</th>
                  <th>Placed At</th>
                  <th>Completed At</th>
                  <th className="text-right">Total</th>
                  <th className="text-center">Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredOrders.map((ord) => {
                  const meta = STATUS_META[ord.status] || {
                    label: ord.status,
                    pillClass: 'status-pill-subtle',
                  };
                  const isDineIn = ord.table_id !== null && ord.table_id !== undefined;
                  const isSelected = selectedOrderId === ord.id;
                  const itemCount = (ord.items || []).length;
                  const previewNames = (ord.items || [])
                    .slice(0, 2)
                    .map((i) => i.menu_item_name || 'Item')
                    .join(', ');
                  const remaining = itemCount > 2 ? ` +${itemCount - 2} more` : '';

                  return (
                    <tr
                      key={ord.id}
                      className={`history-order-row ${isSelected ? 'row-selected' : ''}`}
                      onClick={() => setSelectedOrderId(ord.id)}
                    >
                      {/* Order Number */}
                      <td className="cell-order-number">
                        <div className="order-num-box">
                          <svg className="order-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect width="18" height="18" x="3" y="3" rx="2" />
                            <path d="M7 7h10" />
                            <path d="M7 12h10" />
                            <path d="M7 17h6" />
                          </svg>
                          <span className="order-num-text">{ord.order_number}</span>
                        </div>
                      </td>

                      {/* Service Type */}
                      <td className="cell-service-type">
                        {isDineIn ? (
                          <span className="type-badge dine-in">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M4 18v3" />
                              <path d="M20 18v3" />
                              <path d="M2 14h20" />
                              <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
                            </svg>
                            Table {ord.table_number || ord.table_id}
                          </span>
                        ) : (
                          <span className="type-badge takeaway">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                              <path d="M3 6h18" />
                              <path d="M16 10a4 4 0 0 1-8 0" />
                            </svg>
                            Takeaway
                          </span>
                        )}
                      </td>

                      {/* Items Preview */}
                      <td className="cell-items-preview">
                        <div className="items-meta-line">
                          <span className="items-count-badge">
                            {itemCount} {itemCount === 1 ? 'item' : 'items'}
                          </span>
                          <span className="items-summary" title={previewNames + remaining}>
                            {previewNames}
                            {remaining}
                          </span>
                        </div>
                      </td>

                      {/* Placed At */}
                      <td className="cell-timestamp">
                        <div className="time-primary">{formatTime(ord.created_at)}</div>
                        <div className="date-secondary">{formatDateTime(ord.created_at).split(',')[0]}</div>
                      </td>

                      {/* Completed At */}
                      <td className="cell-timestamp">
                        {ord.completed_at ? (
                          <>
                            <div className="time-primary">{formatTime(ord.completed_at)}</div>
                            <div className="date-secondary">{formatDateTime(ord.completed_at).split(',')[0]}</div>
                          </>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* Total */}
                      <td className="cell-total text-right">
                        <span className="total-amount-strong">{formatUSD(ord.total)}</span>
                      </td>

                      {/* Status */}
                      <td className="cell-status text-center">
                        <span className={`status-pill ${meta.pillClass}`}>
                          <span className="pill-dot" />
                          {meta.label}
                        </span>
                      </td>

                      {/* Action */}
                      <td className="cell-actions text-right">
                        <button
                          type="button"
                          className="btn btn-outline-secondary btn-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedOrderId(ord.id);
                          }}
                        >
                          Inspect
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="btn-icon-right">
                            <polyline points="9 18 15 12 9 6" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Slide-Over Detail Drawer ────────────────────────────────────── */}
      {selectedOrderId && (
        <div className="drawer-backdrop" onClick={() => setSelectedOrderId(null)}>
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            {/* Drawer Header */}
            <div className="drawer-header">
              <div className="drawer-title-group">
                <div className="drawer-badge-row">
                  <span className="drawer-kicker">Order Details & Audit</span>
                  {selectedOrder && (
                    <span className={`status-pill ${STATUS_META[selectedOrder.status]?.pillClass || ''}`}>
                      <span className="pill-dot" />
                      {STATUS_META[selectedOrder.status]?.label || selectedOrder.status}
                    </span>
                  )}
                </div>
                <h3 className="drawer-order-number">
                  {selectedOrder?.order_number || `Order #${selectedOrderId}`}
                </h3>
              </div>

              <button
                type="button"
                className="drawer-close-btn"
                onClick={() => setSelectedOrderId(null)}
                title="Close ticket drawer (Esc)"
              >
                ✕
              </button>
            </div>

            {/* Notification Messages */}
            {actionError && (
              <div className="alert-banner alert-danger mx-4 mt-3">
                <div className="alert-content">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{actionError}</span>
                </div>
                <button type="button" className="alert-close" onClick={() => setActionError(null)}>✕</button>
              </div>
            )}

            {actionSuccess && (
              <div className="alert-banner alert-success mx-4 mt-3">
                <div className="alert-content">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span>{actionSuccess}</span>
                </div>
                <button type="button" className="alert-close" onClick={() => setActionSuccess(null)}>✕</button>
              </div>
            )}

            {/* Drawer Body */}
            <div className="drawer-body">
              {isLoadingDetail && !selectedOrder ? (
                <div className="drawer-loading-box">
                  <div className="state-spinner" />
                  <p>Fetching full ticket details...</p>
                </div>
              ) : selectedOrder ? (
                <>
                  {/* Meta Information Cards */}
                  <div className="drawer-meta-grid">
                    <div className="drawer-meta-item">
                      <span className="meta-label">Fulfillment Mode</span>
                      <strong className="meta-value">
                        {selectedOrder.table_id !== null && selectedOrder.table_id !== undefined ? (
                          <span className="type-badge dine-in">
                            Table {selectedOrder.table_number || selectedOrder.table_id} (Dine-in)
                          </span>
                        ) : (
                          <span className="type-badge takeaway">Takeaway / Carryout</span>
                        )}
                      </strong>
                    </div>

                    <div className="drawer-meta-item">
                      <span className="meta-label">Ticket ID / PK</span>
                      <strong className="meta-value mono">#{selectedOrder.id}</strong>
                    </div>

                    <div className="drawer-meta-item">
                      <span className="meta-label">Placed Time</span>
                      <strong className="meta-value">{formatDateTime(selectedOrder.created_at)}</strong>
                    </div>

                    <div className="drawer-meta-item">
                      <span className="meta-label">Settled / Closed At</span>
                      <strong className="meta-value">
                        {selectedOrder.completed_at
                          ? formatDateTime(selectedOrder.completed_at)
                          : selectedOrder.status === 'cancelled'
                          ? 'Cancelled'
                          : 'In Progress'}
                      </strong>
                    </div>

                    <div className="drawer-meta-item">
                      <span className="meta-label">Payment Status</span>
                      <strong className="meta-value">
                        {selectedOrder.payment_status === 'paid' ? (
                          <span className="status-pill status-pill-available">
                            ✓ Paid ({selectedOrder.payment_method || 'Online'})
                          </span>
                        ) : (
                          <span className="status-pill status-pill-occupied">
                            Pending (Cash/Online)
                          </span>
                        )}
                      </strong>
                    </div>
                  </div>

                  {/* Itemized Line Items */}
                  <div className="drawer-items-section">
                    <h4 className="section-title">
                      <span>Ordered Dishes</span>
                      <span className="badge-item-count">
                        {(selectedOrder.items || []).length} items
                      </span>
                    </h4>

                    <div className="drawer-items-table-wrap">
                      <table className="drawer-items-table">
                        <thead>
                          <tr>
                            <th>Dish</th>
                            <th className="text-center">Qty</th>
                            <th className="text-right">Unit Price</th>
                            <th className="text-right">Line Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedOrder.items || []).map((item, idx) => {
                            const lineTotal = Number(item.unit_price || 0) * Number(item.quantity || 1);
                            return (
                              <tr key={item.id || idx}>
                                <td>
                                  <div className="dish-name-cell">
                                    <span className="dish-name">{item.menu_item_name || `Item #${item.menu_item_id}`}</span>
                                    {item.special_instructions && (
                                      <div className="dish-notes">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                                        </svg>
                                        <span>"{item.special_instructions}"</span>
                                      </div>
                                    )}
                                  </div>
                                </td>
                                <td className="text-center font-medium">× {item.quantity}</td>
                                <td className="text-right text-muted">{formatUSD(item.unit_price)}</td>
                                <td className="text-right font-medium">{formatUSD(lineTotal)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Financial Breakdown (Strictly Stored Authoritative Values) */}
                  <div className="drawer-financials-card">
                    <h4 className="financials-title">Financial Audit Breakdown</h4>

                    <div className="financial-row">
                      <span>Subtotal</span>
                      <span>{formatUSD(selectedOrder.subtotal)}</span>
                    </div>

                    <div className="financial-row">
                      <span>Taxes</span>
                      <span>{formatUSD(selectedOrder.tax)}</span>
                    </div>

                    {Number(selectedOrder.discount || 0) > 0 && (
                      <div className="financial-row discount-row">
                        <span>Discount Applied</span>
                        <span>- {formatUSD(selectedOrder.discount)}</span>
                      </div>
                    )}

                    <div className="financial-row total-row">
                      <strong>Final Settled Total</strong>
                      <strong className="text-terracotta">{formatUSD(selectedOrder.total)}</strong>
                    </div>
                  </div>

                  {/* State Machine Status Actions */}
                  <div className="drawer-actions-section">
                    <h4 className="actions-title">Lifecycle & Status Controls</h4>

                    {selectedOrder.status === 'completed' ? (
                      <div className="terminal-state-box box-completed">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                          <polyline points="22 4 12 14.01 9 11.01" />
                        </svg>
                        <div>
                          <strong>Terminal State: Completed</strong>
                          <p>Order is completed and closed. Table has been released and historical records are locked.</p>
                        </div>
                      </div>
                    ) : selectedOrder.status === 'cancelled' ? (
                      <div className="terminal-state-box box-cancelled">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="15" y1="9" x2="9" y2="15" />
                          <line x1="9" y1="9" x2="15" y2="15" />
                        </svg>
                        <div>
                          <strong>Terminal State: Cancelled</strong>
                          <p>This ticket was cancelled. Any associated dining table was automatically released.</p>
                        </div>
                      </div>
                    ) : nextAllowedActions.length > 0 ? (
                      <div className="actions-button-group">
                        {selectedOrder.payment_status !== 'paid' && selectedOrder.status !== 'cancelled' && (
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={handleSettleCash}
                            disabled={isUpdatingStatus}
                            title="Settle order with cash at counter"
                          >
                            💵 Settle Cash
                          </button>
                        )}
                        {nextAllowedActions.map((action) => {
                          if (action.status === 'cancelled') {
                            return (
                              <button
                                key={action.status}
                                type="button"
                                className="btn btn-outline-danger"
                                onClick={() => setConfirmCancelModal(true)}
                                disabled={isUpdatingStatus}
                              >
                                {isUpdatingStatus ? 'Updating...' : action.label}
                              </button>
                            );
                          }

                          return (
                            <button
                              key={action.status}
                              type="button"
                              className={`btn btn-${action.variant || 'primary'}`}
                              onClick={() => handleTransition(action.status)}
                              disabled={isUpdatingStatus}
                            >
                              {isUpdatingStatus ? 'Updating...' : action.label}
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="drawer-empty-box">
                  <p>Could not locate order details.</p>
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="drawer-footer">
              <button
                type="button"
                className="btn btn-secondary w-full"
                onClick={() => setSelectedOrderId(null)}
              >
                Close Audit View
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm Cancel Modal ────────────────────────────────────────── */}
      {confirmCancelModal && selectedOrder && (
        <div className="modal-backdrop" onClick={() => setConfirmCancelModal(false)}>
          <div className="modal-card modal-compact" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title text-danger">Void & Cancel Order?</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => setConfirmCancelModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <p>
                Are you sure you want to cancel order <strong>#{selectedOrder.order_number}</strong>?
              </p>
              <p className="modal-subtext mt-2">
                This is a terminal state. Any occupied table will be immediately freed, and this ticket can no longer be processed or modified.
              </p>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmCancelModal(false)}
                disabled={isUpdatingStatus}
              >
                Keep Order Active
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => handleTransition('cancelled')}
                disabled={isUpdatingStatus}
              >
                {isUpdatingStatus ? 'Cancelling...' : 'Confirm Cancellation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}