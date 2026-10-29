import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getOrders, updateOrder } from '../services/api';

// Status badge styling helper
const STATUS_CONFIG = {
  pending: {
    label: 'Pending',
    pillClass: 'status-pill-occupied',
    cardClass: 'kds-card-pending',
    indicator: 'Queued',
  },
  in_progress: {
    label: 'In Preparation',
    pillClass: 'status-pill-reserved',
    cardClass: 'kds-card-in-progress',
    indicator: 'Cooking',
  },
  served: {
    label: 'Served to Table',
    pillClass: 'status-pill-available',
    cardClass: 'kds-card-served',
    indicator: 'Plated',
  },
  completed: {
    label: 'Completed',
    pillClass: 'status-pill-available',
    cardClass: 'kds-card-completed',
    indicator: 'Finished',
  },
  cancelled: {
    label: 'Cancelled',
    pillClass: 'status-pill-unavailable',
    cardClass: 'kds-card-cancelled',
    indicator: 'Voided',
  },
};

export default function KitchenPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('active'); // 'active', 'all', 'pending', 'in_progress', 'served', 'completed', 'cancelled'
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  // Map of orderId -> in-flight updating state boolean
  const [updatingOrders, setUpdatingOrders] = useState({});
  // Action error message per order or global
  const [actionError, setActionError] = useState(null);

  // Guard against concurrent overlapping polling requests
  const isFetchingRef = useRef(false);

  // Load orders from backend API
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
      console.error('KDS failed to fetch orders:', err);
      // If initial load, set full error state; if periodic poll, retain existing data and show warning
      if (orders.length === 0) {
        setError(err.message || 'Unable to connect to kitchen queue service.');
      } else {
        setActionError('Network hiccup during background refresh. Displaying last confirmed tickets.');
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      isFetchingRef.current = false;
    }
  }, [orders.length]);

  // Initial load
  useEffect(() => {
    fetchOrders(false);
  }, [fetchOrders]);

  // Periodic polling every 10 seconds for real-time kitchen sync
  useEffect(() => {
    const pollInterval = setInterval(() => {
      fetchOrders(false);
    }, 10000);

    return () => clearInterval(pollInterval);
  }, [fetchOrders]);

  // Summary Operational Counts
  const counts = useMemo(() => {
    const active = orders.filter((o) => ['pending', 'in_progress', 'served'].includes(o.status)).length;
    const pending = orders.filter((o) => o.status === 'pending').length;
    const inProgress = orders.filter((o) => o.status === 'in_progress').length;
    const served = orders.filter((o) => o.status === 'served').length;
    const completed = orders.filter((o) => o.status === 'completed').length;
    return { active, pending, inProgress, served, completed };
  }, [orders]);

  // Filter and sort tickets (Oldest active orders first = FIFO kitchen ticket queue)
  const displayedOrders = useMemo(() => {
    let list = [...orders];

    if (statusFilter === 'active') {
      list = list.filter((o) => ['pending', 'in_progress', 'served'].includes(o.status));
    } else if (statusFilter !== 'all') {
      list = list.filter((o) => o.status === statusFilter);
    }

    // Sort: ascending by creation time (or ID), so oldest active orders appear at the front
    return list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, [orders, statusFilter]);

  // Handle Valid Order Status Transitions
  const handleTransition = async (order, targetStatus) => {
    setUpdatingOrders((prev) => ({ ...prev, [order.id]: true }));
    setActionError(null);

    try {
      const updated = await updateOrder(order.id, { status: targetStatus });

      // Update confirmed in state
      setOrders((prevOrders) =>
        prevOrders.map((o) => (o.id === order.id ? { ...o, ...updated } : o))
      );
    } catch (err) {
      console.error(`Failed to transition order ${order.order_number} to ${targetStatus}:`, err);
      setActionError(
        `Failed to update Order #${order.order_number}: ${err.message || 'Server rejected transition'}`
      );
    } finally {
      setUpdatingOrders((prev) => ({ ...prev, [order.id]: false }));
    }
  };

  // Helper for computing elapsed minutes
  const getElapsedMinutes = (createdAt) => {
    if (!createdAt) return 0;
    const elapsedMs = Date.now() - new Date(createdAt).getTime();
    return Math.max(0, Math.floor(elapsedMs / 60000));
  };

  return (
    <div className="page-content kds-page-layout">
      {/* KDS Control & Meta Bar */}
      <section className="kds-top-bar">
        <div className="kds-info">
          <h2 className="kds-heading">Live Kitchen Ticket Board</h2>
          <p className="kds-subheading">
            Live order queue, preparation stages, and line cook ticket progression.
          </p>
        </div>

        <div className="kds-top-actions">
          <div className="kds-sync-meta">
            <span className="live-indicator-dot" />
            <span className="sync-text">
              {lastRefreshedAt
                ? `Last synced: ${lastRefreshedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
                : 'Syncing...'}
            </span>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-icon"
            onClick={() => fetchOrders(true)}
            disabled={isRefreshing}
            title="Refresh kitchen tickets"
          >
            <svg
              className={`refresh-icon ${isRefreshing ? 'spin' : ''}`}
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
              <path d="M16 16h5v5" />
            </svg>
            <span>{isRefreshing ? 'Syncing...' : 'Sync Queue'}</span>
          </button>
        </div>
      </section>

      {/* Non-blocking Action Error Banner */}
      {actionError && (
        <div className="kds-alert-banner">
          <div className="kds-alert-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{actionError}</span>
          </div>
          <button type="button" className="kds-alert-close" onClick={() => setActionError(null)}>
            ✕
          </button>
        </div>
      )}

      {/* Operational Summary Cards */}
      <section className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Active Ticket Queue</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" />
                <path d="M3 9h18" />
                <path d="M9 21V9" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : counts.active}</div>
          <div className="metric-subtext">Pending & Cooking Tickets</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Pending / Waiting</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : counts.pending}</div>
          <div className="metric-subtext">Needs cook assignment</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">In Preparation</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v20" />
                <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : counts.inProgress}</div>
          <div className="metric-subtext">Currently on the cook line</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Served / Ready</span>
            <span className="metric-icon-subtle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </span>
          </div>
          <div className="metric-value">{loading ? '—' : counts.served}</div>
          <div className="metric-subtext">Plated and delivered</div>
        </div>
      </section>

      {/* Filter Tabs Bar */}
      <section className="kds-filters-bar">
        <div className="category-pills-bar">
          <button
            type="button"
            className={`category-pill ${statusFilter === 'active' ? 'active' : ''}`}
            onClick={() => setStatusFilter('active')}
          >
            Active Queue ({counts.active})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => setStatusFilter('all')}
          >
            All Orders ({orders.length})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'pending' ? 'active' : ''}`}
            onClick={() => setStatusFilter('pending')}
          >
            Pending ({counts.pending})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'in_progress' ? 'active' : ''}`}
            onClick={() => setStatusFilter('in_progress')}
          >
            In Preparation ({counts.inProgress})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'served' ? 'active' : ''}`}
            onClick={() => setStatusFilter('served')}
          >
            Served ({counts.served})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'completed' ? 'active' : ''}`}
            onClick={() => setStatusFilter('completed')}
          >
            Completed ({counts.completed})
          </button>
          <button
            type="button"
            className={`category-pill ${statusFilter === 'cancelled' ? 'active' : ''}`}
            onClick={() => setStatusFilter('cancelled')}
          >
            Cancelled
          </button>
        </div>
      </section>

      {/* KDS Ticket Cards Grid */}
      {loading && orders.length === 0 ? (
        <div className="kds-tickets-grid">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="kds-ticket-card skeleton-card">
              <div className="skeleton-line skeleton-badge" />
              <div className="skeleton-line skeleton-title" />
              <div className="skeleton-line skeleton-desc" />
              <div className="skeleton-line skeleton-desc short" />
              <div className="skeleton-footer">
                <div className="skeleton-line skeleton-pill" />
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
            <h3>Unable to Load Kitchen Queue</h3>
            <p className="state-message">{error}</p>
            <button type="button" className="btn btn-primary" onClick={() => fetchOrders(true)}>
              Retry Connection
            </button>
          </div>
        </div>
      ) : displayedOrders.length === 0 ? (
        <div className="state-card state-empty">
          <div className="state-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v20" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          </div>
          <div className="state-body">
            <h3>No Orders in This Queue</h3>
            <p className="state-message">
              {statusFilter === 'active'
                ? 'All kitchen tickets are currently clear! New orders from the POS terminal will appear here automatically.'
                : `There are currently no orders with status "${statusFilter}".`}
            </p>
            {statusFilter !== 'active' && (
              <button type="button" className="btn btn-secondary" onClick={() => setStatusFilter('active')}>
                View Active Queue
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="kds-tickets-grid">
          {displayedOrders.map((order) => {
            const isDineIn = order.table_id !== null && order.table_id !== undefined;
            const config = STATUS_CONFIG[order.status] || STATUS_CONFIG.pending;
            const elapsedMins = getElapsedMinutes(order.created_at);
            const isDelayed = elapsedMins >= 15 && ['pending', 'in_progress'].includes(order.status);
            const isUpdating = !!updatingOrders[order.id];

            return (
              <article key={order.id} className={`kds-ticket-card ${config.cardClass} ${isDelayed ? 'kds-delayed' : ''}`}>
                {/* Ticket Top Header */}
                <header className="kds-card-top">
                  <div className="kds-id-group">
                    <span className="kds-order-number">{order.order_number}</span>
                    <span className={`kds-service-badge ${isDineIn ? 'service-dine-in' : 'service-takeaway'}`}>
                      {isDineIn ? (
                        <>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M4 18v3" />
                            <path d="M20 18v3" />
                            <path d="M2 14h20" />
                            <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
                          </svg>
                          <span>Table {order.table_number || `#${order.table_id}`}</span>
                        </>
                      ) : (
                        <>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                          </svg>
                          <span>Takeaway</span>
                        </>
                      )}
                    </span>
                  </div>

                  <div className="kds-status-wrap">
                    <span className={`status-pill ${config.pillClass}`}>
                      <span className="pill-dot" />
                      {config.label}
                    </span>
                  </div>
                </header>

                {/* Timing Row */}
                <div className="kds-timer-row">
                  <span className="kds-placed-time">
                    Placed:{' '}
                    {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className={`kds-elapsed-badge ${isDelayed ? 'elapsed-urgent' : ''}`}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                    <span>{elapsedMins === 0 ? '< 1m ago' : `${elapsedMins}m ago`}</span>
                    {isDelayed && <strong className="delay-flag">DELAYED</strong>}
                  </span>
                </div>

                {/* Ticket Items List */}
                <div className="kds-items-box">
                  <div className="kds-items-label">Preparation Items ({(order.items || []).length}):</div>
                  <ul className="kds-items-list">
                    {(order.items || []).map((item) => (
                      <li key={item.id} className="kds-item-row">
                        <div className="kds-item-main">
                          <span className="kds-item-qty">{item.quantity}×</span>
                          <span className="kds-item-name">
                            {item.menu_item_name || `Item #${item.menu_item_id}`}
                          </span>
                        </div>

                        {/* Highlighted Special Cooking Instructions */}
                        {item.special_instructions && (
                          <div className="kds-special-note">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                              <line x1="12" y1="9" x2="12" y2="13" />
                              <line x1="12" y1="17" x2="12.01" y2="17" />
                            </svg>
                            <span>NOTE: "{item.special_instructions}"</span>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Status Action Buttons (Enforcing Backend State Machine) */}
                <footer className="kds-card-actions">
                  {/* PENDING: Start Prep or Cancel */}
                  {order.status === 'pending' && (
                    <div className="kds-btn-group">
                      <button
                        type="button"
                        className="btn btn-primary kds-action-btn"
                        disabled={isUpdating}
                        onClick={() => handleTransition(order, 'in_progress')}
                      >
                        {isUpdating ? 'Updating...' : 'Start Cooking'}
                      </button>

                      {/* For takeaway, can also complete directly */}
                      {!isDineIn && (
                        <button
                          type="button"
                          className="btn btn-secondary kds-action-btn"
                          disabled={isUpdating}
                          onClick={() => handleTransition(order, 'completed')}
                        >
                          Complete Order
                        </button>
                      )}

                      <button
                        type="button"
                        className="btn btn-secondary kds-cancel-btn"
                        disabled={isUpdating}
                        onClick={() => handleTransition(order, 'cancelled')}
                        title="Void/Cancel this order"
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {/* IN_PROGRESS: Mark Served (Dine-in) or Complete (Takeaway) */}
                  {order.status === 'in_progress' && (
                    <div className="kds-btn-group">
                      {isDineIn ? (
                        <button
                          type="button"
                          className="btn btn-primary kds-action-btn"
                          disabled={isUpdating}
                          onClick={() => handleTransition(order, 'served')}
                        >
                          {isUpdating ? 'Updating...' : 'Mark as Served'}
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-primary kds-action-btn"
                          disabled={isUpdating}
                          onClick={() => handleTransition(order, 'completed')}
                        >
                          {isUpdating ? 'Updating...' : 'Complete Takeaway'}
                        </button>
                      )}

                      <button
                        type="button"
                        className="btn btn-secondary kds-cancel-btn"
                        disabled={isUpdating}
                        onClick={() => handleTransition(order, 'cancelled')}
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {/* SERVED: Complete or Cancel */}
                  {order.status === 'served' && (
                    <div className="kds-btn-group">
                      <button
                        type="button"
                        className="btn btn-primary kds-action-btn"
                        disabled={isUpdating}
                        onClick={() => handleTransition(order, 'completed')}
                      >
                        {isUpdating ? 'Updating...' : 'Complete Order'}
                      </button>

                      <button
                        type="button"
                        className="btn btn-secondary kds-cancel-btn"
                        disabled={isUpdating}
                        onClick={() => handleTransition(order, 'cancelled')}
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {/* COMPLETED / CANCELLED: Terminal States */}
                  {['completed', 'cancelled'].includes(order.status) && (
                    <div className="kds-terminal-label">
                      <span>
                        Ticket {order.status === 'completed' ? 'Completed' : 'Cancelled'}{' '}
                        {order.completed_at
                          ? `at ${new Date(order.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                          : ''}
                      </span>
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
