import React from 'react';

export default function Header({
  title,
  subtitle,
  onRefresh,
  isRefreshing,
  currentUser,
  onLogout,
}) {
  const getInitials = (name, username) => {
    if (name) {
      const parts = name.trim().split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return name.slice(0, 2).toUpperCase();
    }
    return (username || 'U').slice(0, 2).toUpperCase();
  };

  return (
    <header className="main-header">
      <div className="header-titles">
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>

      <div className="header-actions">
        {onRefresh && (
          <button
            type="button"
            className="btn btn-secondary btn-icon"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh live data from server"
            aria-label="Refresh live data from server"
          >
            <svg
              className={`refresh-icon ${isRefreshing ? 'spin' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
              <path d="M16 16h5v5" />
            </svg>
            <span className="btn-text-desktop">{isRefreshing ? 'Syncing...' : 'Refresh'}</span>
          </button>
        )}

        {currentUser && onLogout && (
          <div className="header-user-mobile-wrap" title={`Logged in as ${currentUser.full_name || currentUser.username} (${currentUser.role})`}>
            <div className="header-user-badge">
              <span className="header-user-avatar">
                {getInitials(currentUser.full_name, currentUser.username)}
              </span>
              <span className="header-user-name">{currentUser.full_name || currentUser.username}</span>
              <span className={`role-badge role-${currentUser.role}`}>{currentUser.role.toUpperCase()}</span>
            </div>
            <button
              type="button"
              className="header-logout-btn"
              onClick={onLogout}
              title="Sign out of station"
              aria-label="Sign out of station"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              <span className="btn-text-desktop">Logout</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
