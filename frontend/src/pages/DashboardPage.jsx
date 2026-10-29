import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getOrders, getTables, getMenuItems, getCategories } from '../services/api';
import { formatUSD } from '../utils/formatters';

export default function DashboardPage({ onNavigate }) {
  const [orders, setOrders] = useState([]);
  const [tables, setTables] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);

  const isFetchingRef = useRef(false);

  const loadDashboardData = useCallback(async (isManual = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    if (isManual) {
      setIsRefreshing(true);
    }

    try {
      const [ords, tbls, items, cats] = await Promise.all([
        getOrders(),
        getTables(),
        getMenuItems(),
        getCategories(),
      ]);

      setOrders(Array.isArray(ords) ? ords : []);
      setTables(Array.isArray(tbls) ? tbls : []);
      setMenuItems(Array.isArray(items) ? items : []);
      setCategories(Array.isArray(cats) ? cats : []);
      setLastRefreshedAt(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to load dashboard metrics:', err);
      if (orders.length === 0) {
        setError(err.message || 'Unable to communicate with restaurant backend services.');
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      isFetchingRef.current = false;
    }
  }, [orders.length]);

  useEffect(() => {
    loadDashboardData(false);
  }, [loadDashboardData]);

  // Operational Calculations (Derived strictly from verified database records)
  const metrics = useMemo(() => {
    const totalOrders = orders.length;
    const activeOrders = orders.filter((o) => ['pending', 'in_progress', 'served'].includes(o.status));
    const pendingOrders = orders.filter((o) => o.status === 'pending');
    const inPrepOrders = orders.filter((o) => o.status === 'in_progress');
    const servedOrders = orders.filter((o) => o.status === 'served');
    const completedOrders = orders.filter((o) => o.status === 'completed');
    const cancelledOrders = orders.filter((o) => o.status === 'cancelled');

    // Financial Values (Documented scope: Server-calculated gross order totals)
    const completedOrderValue = completedOrders.reduce((sum, o) => sum + (Number(o.total) || 0), 0);
    const totalGrossOrderValue = orders.reduce((sum, o) => sum + (Number(o.total) || 0), 0);
    const avgTicketValue = completedOrders.length > 0 ? completedOrderValue / completedOrders.length : 0;

    // Floor & Table Metrics
    const totalTables = tables.length;
    const availableTables = tables.filter((t) => t.status === 'available');
    const occupiedTables = tables.filter((t) => t.status === 'occupied');
    const reservedTables = tables.filter((t) => t.status === 'reserved');
    const totalCapacity = tables.reduce((sum, t) => sum + (Number(t.capacity) || 0), 0);
    const occupancyRate = totalTables > 0 ? Math.round((occupiedTables.length / totalTables) * 100) : 0;

    // Menu Catalog Metrics
    const totalMenuItems = menuItems.length;
    const availableItems = menuItems.filter((m) => m.is_available);
    const outOfStockItems = menuItems.filter((m) => !m.is_available);
    const catalogAvailabilityRate = totalMenuItems > 0 ? Math.round((availableItems.length / totalMenuItems) * 100) : 0;

    return {
      totalOrders,
      activeOrdersCount: activeOrders.length,
      pendingCount: pendingOrders.length,
      inPrepCount: inPrepOrders.length,
      servedCount: servedOrders.length,
      completedCount: completedOrders.length,
      cancelledCount: cancelledOrders.length,
      completedOrderValue,
      totalGrossOrderValue,
      avgTicketValue,
      totalTables,
      availableTablesCount: availableTables.length,
      occupiedTablesCount: occupiedTables.length,
      reservedTablesCount: reservedTables.length,
      totalCapacity,
      occupancyRate,
      totalMenuItems,
      availableItemsCount: availableItems.length,
      outOfStockCount: outOfStockItems.length,
      catalogAvailabilityRate,
      categoriesCount: categories.length,
    };
  }, [orders, tables, menuItems, categories]);

  // Recent orders sorted newest first
  const recentOrdersList = useMemo(() => {
    return [...orders].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [orders]);

  return (
    <div className="page-content dashboard-page-layout">
      {/* Top Welcome & Meta Bar */}
      <section className="dashboard-top-bar">
        <div className="dashboard-heading-wrap">
          <h2 className="dashboard-heading">Executive & Operations Overview</h2>
          <p className="dashboard-subheading">
            Live ticket velocity, dining floor occupancy, menu catalog health, and verified order values.
          </p>
        </div>

        <div className="dashboard-top-actions">
          <div className="sync-badge">
            <span className="live-indicator-dot" />
            <span className="sync-text">
              {lastRefreshedAt
                ? `Last synced: ${lastRefreshedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
                : 'Loading...'}
            </span>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-icon"
            onClick={() => loadDashboardData(true)}
            disabled={isRefreshing}
            title="Refresh dashboard metrics from backend"
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
            <span>{isRefreshing ? 'Syncing...' : 'Refresh All'}</span>
          </button>
        </div>
      </section>

      {/* Loading or Error States */}
      {loading && orders.length === 0 ? (
        <div className="metrics-grid">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="metric-card skeleton-card">
              <div className="skeleton-line skeleton-badge" />
              <div className="skeleton-line skeleton-title" />
              <div className="skeleton-line skeleton-desc" />
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
            <h3>Unable to Load Dashboard Data</h3>
            <p className="state-message">{error}</p>
            <button type="button" className="btn btn-primary" onClick={() => loadDashboardData(true)}>
              Retry Connection
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Section 1: Core Key Performance Metrics */}
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
              <div className="metric-value">{metrics.activeOrdersCount}</div>
              <div className="metric-subtext">
                {metrics.pendingCount} pending • {metrics.inPrepCount} in prep • {metrics.servedCount} served
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-label">Completed Order Value</span>
                <span className="metric-icon-subtle">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2v20" />
                    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                  </svg>
                </span>
              </div>
              <div className="metric-value">{formatUSD(metrics.completedOrderValue)}</div>
              <div className="metric-subtext">Across {metrics.completedCount} completed tickets</div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-label">Floor Occupancy</span>
                <span className="metric-icon-subtle">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 18v3" />
                    <path d="M20 18v3" />
                    <path d="M2 14h20" />
                    <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
                  </svg>
                </span>
              </div>
              <div className="metric-value">{metrics.occupancyRate}%</div>
              <div className="metric-subtext">
                {metrics.occupiedTablesCount} of {metrics.totalTables} tables occupied ({metrics.totalCapacity} seats)
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <span className="metric-label">Menu In-Stock Ratio</span>
                <span className="metric-icon-subtle">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                </span>
              </div>
              <div className="metric-value">{metrics.catalogAvailabilityRate}%</div>
              <div className="metric-subtext">
                {metrics.availableItemsCount} ready • {metrics.outOfStockCount} out of stock
              </div>
            </div>
          </section>

          {/* Section 2: Financial Scope & Operational Insights Grid */}
          <div className="dashboard-panels-grid">
            {/* Panel A: Gross Order Value Breakdown */}
            <div className="dashboard-panel">
              <div className="panel-header">
                <div className="panel-title-wrap">
                  <h3 className="panel-title">Order Value & Financial Scope</h3>
                  <p className="panel-subtitle">Authoritative totals from recorded database tickets</p>
                </div>
              </div>

              <div className="panel-body">
                <div className="financial-stats-grid">
                  <div className="financial-stat-box">
                    <span className="stat-label">Gross Order Value (All Orders)</span>
                    <strong className="stat-num">{formatUSD(metrics.totalGrossOrderValue)}</strong>
                    <span className="stat-hint">Total volume of all {metrics.totalOrders} tickets</span>
                  </div>

                  <div className="financial-stat-box">
                    <span className="stat-label">Completed Orders Value</span>
                    <strong className="stat-num stat-accent">{formatUSD(metrics.completedOrderValue)}</strong>
                    <span className="stat-hint">Finished & fulfilled orders</span>
                  </div>

                  <div className="financial-stat-box">
                    <span className="stat-label">Average Ticket Size</span>
                    <strong className="stat-num">{formatUSD(metrics.avgTicketValue)}</strong>
                    <span className="stat-hint">Per completed dining ticket</span>
                  </div>
                </div>

                <div className="scope-notice-banner">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                  </svg>
                  <span>
                    <strong>Accounting Notice:</strong> Figures represent gross order values from recorded database tickets.
                    Payment collection and tender settlement will be integrated in subsequent cashier phases.
                  </span>
                </div>
              </div>
            </div>

            {/* Panel B: Dining Floor Proportions */}
            <div className="dashboard-panel">
              <div className="panel-header">
                <div className="panel-title-wrap">
                  <h3 className="panel-title">Dining Floor Occupancy Breakdown</h3>
                  <p className="panel-subtitle">{metrics.totalCapacity} total seat capacity across {metrics.totalTables} tables</p>
                </div>
                {onNavigate && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => onNavigate('tables')}
                  >
                    Floor Plan →
                  </button>
                )}
              </div>

              <div className="panel-body">
                {/* Pure CSS Proportional Progress Bar */}
                <div className="table-proportion-bar" title="Dining Floor Capacity Distribution">
                  <div
                    className="bar-seg bar-available"
                    style={{
                      width: `${metrics.totalTables > 0 ? (metrics.availableTablesCount / metrics.totalTables) * 100 : 0}%`,
                    }}
                  />
                  <div
                    className="bar-seg bar-occupied"
                    style={{
                      width: `${metrics.totalTables > 0 ? (metrics.occupiedTablesCount / metrics.totalTables) * 100 : 0}%`,
                    }}
                  />
                  <div
                    className="bar-seg bar-reserved"
                    style={{
                      width: `${metrics.totalTables > 0 ? (metrics.reservedTablesCount / metrics.totalTables) * 100 : 0}%`,
                    }}
                  />
                </div>

                {/* Table Legend */}
                <div className="table-legend-grid">
                  <div className="legend-item">
                    <span className="legend-dot dot-available" />
                    <div className="legend-text">
                      <span className="legend-label">Available Tables</span>
                      <strong>{metrics.availableTablesCount} ({metrics.totalTables > 0 ? Math.round((metrics.availableTablesCount / metrics.totalTables) * 100) : 0}%)</strong>
                    </div>
                  </div>

                  <div className="legend-item">
                    <span className="legend-dot dot-occupied" />
                    <div className="legend-text">
                      <span className="legend-label">Occupied Tables</span>
                      <strong>{metrics.occupiedTablesCount} ({metrics.occupancyRate}%)</strong>
                    </div>
                  </div>

                  <div className="legend-item">
                    <span className="legend-dot dot-reserved" />
                    <div className="legend-text">
                      <span className="legend-label">Reserved Tables</span>
                      <strong>{metrics.reservedTablesCount} ({metrics.totalTables > 0 ? Math.round((metrics.reservedTablesCount / metrics.totalTables) * 100) : 0}%)</strong>
                    </div>
                  </div>
                </div>

                <div className="panel-quick-actions">
                  <span className="quick-action-text">
                    Ready for walk-in guests: <strong>{metrics.availableTablesCount} tables</strong>
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Recent Orders Ticket Stream */}
          <section className="dashboard-panel">
            <div className="panel-header">
              <div className="panel-title-wrap">
                <h3 className="panel-title">Recent Tickets Stream</h3>
                <p className="panel-subtitle">Latest tickets submitted through POS and kitchen channels</p>
              </div>

              <div className="header-actions">
                {onNavigate && (
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() => onNavigate('orders')}
                  >
                    + New Ticket in POS
                  </button>
                )}
              </div>
            </div>

            <div className="panel-body">
              {recentOrdersList.length === 0 ? (
                <div className="state-card state-empty">
                  <div className="state-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                    </svg>
                  </div>
                  <div className="state-body">
                    <h3>No Recorded Orders</h3>
                    <p className="state-message">Orders placed in the POS register will appear in this real-time stream.</p>
                  </div>
                </div>
              ) : (
                <div className="dashboard-recent-orders-table">
                  <div className="dash-table-header">
                    <span>Order Number</span>
                    <span>Service</span>
                    <span>Placed</span>
                    <span>Status</span>
                    <span>Items</span>
                    <span className="text-right">Total</span>
                  </div>

                  <div className="dash-table-body">
                    {recentOrdersList.slice(0, 6).map((ord) => {
                      const isDineIn = ord.table_id !== null && ord.table_id !== undefined;
                      const statusClass = {
                        pending: 'status-pill-occupied',
                        in_progress: 'status-pill-reserved',
                        served: 'status-pill-available',
                        completed: 'status-pill-available',
                        cancelled: 'status-pill-unavailable',
                      }[ord.status] || 'status-pill-unavailable';

                      return (
                        <div key={ord.id} className="dash-table-row">
                          <span className="dash-col-code">{ord.order_number}</span>
                          <span className="dash-col-service">
                            {isDineIn ? `Table ${ord.table_number || `#${ord.table_id}`}` : 'Takeaway'}
                          </span>
                          <span className="dash-col-time">
                            {new Date(ord.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          <span>
                            <span className={`status-pill ${statusClass}`}>
                              <span className="pill-dot" />
                              {ord.status.toUpperCase()}
                            </span>
                          </span>
                          <span className="dash-col-items">
                            {(ord.items || []).length} {(ord.items || []).length === 1 ? 'item' : 'items'}
                          </span>
                          <span className="dash-col-total text-right">
                            {formatUSD(ord.total)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Section 4: Operations Shortcuts Navigation Bar */}
          {onNavigate && (
            <section className="dashboard-shortcuts-grid">
              <button
                type="button"
                className="shortcut-card"
                onClick={() => onNavigate('orders')}
              >
                <div className="shortcut-icon-wrap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                    <path d="M3 6h18" />
                    <path d="M16 10a4 4 0 0 1-8 0" />
                  </svg>
                </div>
                <div className="shortcut-text">
                  <strong>Open POS Terminal</strong>
                  <span>Create dine-in and takeaway tickets</span>
                </div>
              </button>

              <button
                type="button"
                className="shortcut-card"
                onClick={() => onNavigate('kitchen')}
              >
                <div className="shortcut-icon-wrap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2v20" />
                    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                  </svg>
                </div>
                <div className="shortcut-text">
                  <strong>Kitchen Display Board</strong>
                  <span>Line cook orders & preparation timers</span>
                </div>
              </button>

              <button
                type="button"
                className="shortcut-card"
                onClick={() => onNavigate('tables')}
              >
                <div className="shortcut-icon-wrap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 18v3" />
                    <path d="M20 18v3" />
                    <path d="M2 14h20" />
                    <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
                  </svg>
                </div>
                <div className="shortcut-text">
                  <strong>Tables & Floor Plan</strong>
                  <span>Seating capacities & table occupancy</span>
                </div>
              </button>

              <button
                type="button"
                className="shortcut-card"
                onClick={() => onNavigate('menu')}
              >
                <div className="shortcut-icon-wrap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
                    <path d="M7 2v20" />
                    <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
                  </svg>
                </div>
                <div className="shortcut-text">
                  <strong>Menu Catalog</strong>
                  <span>Dishes, pricing, and stock availability</span>
                </div>
              </button>

              <button
                type="button"
                className="shortcut-card"
                onClick={() => onNavigate('order_history')}
              >
                <div className="shortcut-icon-wrap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                </div>
                <div className="shortcut-text">
                  <strong>Order History</strong>
                  <span>Audit tickets, line items & guest receipts</span>
                </div>
              </button>
            </section>
          )}
        </>
      )}
    </div>
  );
}
