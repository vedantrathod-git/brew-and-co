import React from 'react';

const TAB_ROLES = {
  menu: ['admin', 'manager', 'cashier'],
  tables: ['admin', 'manager', 'cashier'],
  inventory: ['admin', 'manager', 'cashier', 'kitchen'],
  orders: ['admin', 'manager', 'cashier'],
  kitchen: ['admin', 'manager', 'kitchen'],
  order_history: ['admin', 'manager', 'cashier', 'kitchen'],
  dashboard: ['admin', 'manager'],
  users: ['admin'],
};

const ALL_NAV_GROUPS = [
  {
    label: 'Operations',
    items: [
      {
        id: 'menu',
        label: 'Menu Items',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
            <path d="M7 2v20" />
            <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
          </svg>
        ),
      },
      {
        id: 'tables',
        label: 'Tables & Seating',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 18v3" />
            <path d="M20 18v3" />
            <path d="M2 14h20" />
            <path d="M6 14V6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8" />
          </svg>
        ),
      },
      {
        id: 'inventory',
        label: 'Inventory',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
            <path d="m3.3 7 8.7 5 8.7-5" />
            <path d="M12 22V12" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Service',
    items: [
      {
        id: 'orders',
        label: 'Orders & POS',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
            <path d="M3 6h18" />
            <path d="M16 10a4 4 0 0 1-8 0" />
          </svg>
        ),
      },
      {
        id: 'kitchen',
        label: 'Kitchen Display',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v20" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        ),
      },
      {
        id: 'order_history',
        label: 'Order History',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Overview',
    items: [
      {
        id: 'dashboard',
        label: 'Dashboard',
        badge: 'Live',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="7" height="9" x="3" y="3" rx="1" />
            <rect width="7" height="5" x="14" y="3" rx="1" />
            <rect width="7" height="9" x="14" y="12" rx="1" />
            <rect width="7" height="5" x="3" y="16" rx="1" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Administration',
    items: [
      {
        id: 'users',
        label: 'Staff Accounts',
        badge: 'Admin',
        icon: (
          <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        ),
      },
    ],
  },
];

export default function Sidebar({ activeTab, onSelectTab, backendStatus, currentUser, onLogout }) {
  const userRole = currentUser?.role || 'cashier';

  // Filter navigation items by role permissions
  const visibleGroups = ALL_NAV_GROUPS.map((group) => {
    const items = group.items.filter((item) => {
      const allowed = TAB_ROLES[item.id];
      return !allowed || allowed.includes(userRole);
    });
    return { ...group, items };
  }).filter((group) => group.items.length > 0);

  const getInitials = (name, username) => {
    if (name) {
      const parts = name.trim().split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return name.slice(0, 2).toUpperCase();
    }
    return (username || 'U').slice(0, 2).toUpperCase();
  };

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-brand">
        <div className="brand-icon-box" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 8h1a4 4 0 1 1 0 8h-1" />
            <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
            <line x1="6" y1="2" x2="6" y2="4" />
            <line x1="10" y1="2" x2="10" y2="4" />
            <line x1="14" y1="2" x2="14" y2="4" />
          </svg>
        </div>
        <div className="brand-meta">
          <span className="brand-title">Brew &amp; Co.</span>
          <span className="brand-subtitle">Artisanal Café Suite</span>
        </div>
      </div>

      {/* Navigation Sections */}
      <nav className="sidebar-nav">
        {visibleGroups.map((group) => (
          <div key={group.label} className="nav-section">
            <div className="nav-section-label">{group.label}</div>
            {group.items.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  id={`nav-link-${item.id}`}
                  data-tab={item.id}
                  type="button"
                  className={`nav-link ${isActive ? 'active' : ''}`}
                  onClick={() => onSelectTab(item.id)}
                >
                  <span className="nav-icon-wrap">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                  {item.badge && <span className="nav-pill">{item.badge}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User Session & System Status Footer */}
      <div className="sidebar-footer">
        {currentUser && (
          <div className="sidebar-user-card">
            <div className="user-avatar-badge">
              {getInitials(currentUser.full_name, currentUser.username)}
            </div>
            <div className="user-info-text">
              <span className="user-display-name">{currentUser.full_name || currentUser.username}</span>
              <span className={`role-badge role-${currentUser.role || 'staff'}`}>{(currentUser.role || 'staff').toUpperCase()}</span>
            </div>
            <button
              type="button"
              className="user-logout-btn"
              onClick={onLogout}
              title="Sign out of station"
              aria-label="Sign out of station"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        )}

        <div className="system-status-indicator">
          <span className={`status-dot ${backendStatus.healthy ? 'status-online' : 'status-offline'}`} />
          <div className="status-meta">
            <span className="status-name">FastAPI Backend</span>
            <span className="status-state">{backendStatus.healthy ? 'Connected' : 'Offline'}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
