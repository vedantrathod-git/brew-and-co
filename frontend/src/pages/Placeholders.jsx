import React from 'react';

export function DashboardPlaceholder() {
  return (
    <div className="page-content">
      <div className="placeholder-panel">
        <div className="placeholder-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <rect width="7" height="9" x="3" y="3" rx="1" />
            <rect width="7" height="5" x="14" y="3" rx="1" />
            <rect width="7" height="9" x="14" y="12" rx="1" />
            <rect width="7" height="5" x="3" y="16" rx="1" />
          </svg>
        </div>
        <h2>Operational Metrics & Shift Overview</h2>
        <p>
          Real-time daily revenue, average ticket size, order velocity, and top-selling menu items
          will appear here. Backend endpoints for Orders and Menu Items are already live and tested.
        </p>
        <div className="placeholder-badges">
          <span className="badge-info">Scheduled: Phase 6</span>
          <span className="badge-neutral">APIs: /api/orders, /api/menu-items</span>
        </div>
      </div>
    </div>
  );
}

export function OrdersPlaceholder() {
  return (
    <div className="page-content">
      <div className="placeholder-panel">
        <div className="placeholder-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
            <path d="M3 6h18" />
            <path d="M16 10a4 4 0 0 1-8 0" />
          </svg>
        </div>
        <h2>Orders & Point of Sale Terminal</h2>
        <p>
          Cashier terminal for dine-in and takeaway orders, item modifier selection, automated discount calculations,
          and bill settlement powered by the forward-only order state machine.
        </p>
        <div className="placeholder-badges">
          <span className="badge-info">Scheduled: Phase 6</span>
          <span className="badge-neutral">API: /api/orders</span>
        </div>
      </div>
    </div>
  );
}

export function KitchenPlaceholder() {
  return (
    <div className="page-content">
      <div className="placeholder-panel">
        <div className="placeholder-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v20" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        </div>
        <h2>Kitchen Display System (KDS)</h2>
        <p>
          Line cook ticket board with preparation timers, course progression, and status controls
          (<code>pending</code> → <code>in_progress</code> → <code>served</code>).
        </p>
        <div className="placeholder-badges">
          <span className="badge-info">Scheduled: Phase 6</span>
          <span className="badge-neutral">Real-Time Ticket Queue</span>
        </div>
      </div>
    </div>
  );
}
