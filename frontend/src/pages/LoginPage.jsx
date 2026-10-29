import React, { useState } from 'react';
import { loginUser } from '../services/api';

// In production, demo accounts and quick-fill buttons are strictly disabled
// to prevent credential exposure or unauthorized station access.
const SHOW_DEMO_ACCOUNTS = !import.meta.env.PROD && (import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEMO_LOGIN === 'true');

const DEMO_ACCOUNTS = [
  {
    role: 'admin',
    label: 'Admin Station',
    badge: 'Full Access',
    username: 'admin',
    password: 'AdminPass123!',
    desc: 'System management, all operations & user accounts',
  },
  {
    role: 'manager',
    label: 'Manager Station',
    badge: 'Operations',
    username: 'manager',
    password: 'ManagerPass123!',
    desc: 'Menu catalog, floor plan, POS & orders management',
  },
  {
    role: 'cashier',
    label: 'Cashier Station',
    badge: 'POS & Billing',
    username: 'cashier',
    password: 'CashierPass123!',
    desc: 'Order creation, table seating & guest bill audits',
  },
  {
    role: 'kitchen',
    label: 'Kitchen Station',
    badge: 'KDS Display',
    username: 'kitchen',
    password: 'KitchenPass123!',
    desc: 'Live ticket queue & dish preparation status updates',
  },
];

export default function LoginPage({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Please provide both username and password.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await loginUser({
        username: username.trim(),
        password,
      });

      if (response && response.user) {
        onLoginSuccess(response.user);
      }
    } catch (err) {
      console.error('Login failed:', err);
      setError(err.message || 'Incorrect username or password. Please verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (acc) => {
    setUsername(acc.username);
    setPassword(acc.password);
    setError(null);
  };

  return (
    <div className="login-screen-wrapper">
      <div className="login-container">
        {/* Brand Header */}
        <div className="login-brand-box">
          <div className="login-icon-wrap">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M3 9h18" />
              <path d="M9 21V9" />
            </svg>
          </div>
          <h1 className="login-brand-title">Restaurant POS</h1>
          <p className="login-brand-subtitle">Operations & Point-of-Sale Suite</p>
        </div>

        {/* Login Form Card */}
        <div className="login-card">
          <div className="login-card-header">
            <h2 className="login-title">Staff Sign In</h2>
            <p className="login-instruction">
              Enter your credentials to unlock your designated terminal station.
            </p>
          </div>

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
            </div>
          )}

          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="login-username" className="form-label">
                Username or Email
              </label>
              <div className="input-with-icon">
                <svg className="field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <input
                  id="login-username"
                  type="text"
                  className="form-input with-left-icon"
                  placeholder="e.g. admin or cashier"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="login-password" className="form-label">
                Password
              </label>
              <div className="input-with-icon">
                <svg className="field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  className="form-input with-left-icon with-right-icon"
                  placeholder="Enter station password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="toggle-password-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
                      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                      <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
                      <line x1="2" y1="2" x2="22" y2="22" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block btn-lg mt-3"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="btn-spinner" />
                  <span>Authenticating Station...</span>
                </>
              ) : (
                <span>Sign In to Terminal</span>
              )}
            </button>
          </form>

          {/* Quick Demo Fillers (Only shown in Development or when explicitly enabled) */}
          {SHOW_DEMO_ACCOUNTS && (
            <div className="demo-accounts-section">
              <div className="demo-divider">
                <span>Quick Test Access (Pre-Configured Roles)</span>
              </div>

              <div className="demo-buttons-grid">
                {DEMO_ACCOUNTS.map((acc) => (
                  <button
                    key={acc.role}
                    type="button"
                    className="demo-card-btn"
                    onClick={() => fillDemo(acc)}
                    title={`Fill credentials for ${acc.label}`}
                  >
                    <div className="demo-card-top">
                      <strong className="demo-role-name">{acc.label}</strong>
                      <span className={`role-badge role-${acc.role}`}>{acc.badge}</span>
                    </div>
                    <span className="demo-role-desc">{acc.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="login-footer">
          <span>Protected with HTTP-only tokens & Role-Based Access Control</span>
        </div>
      </div>
    </div>
  );
}
