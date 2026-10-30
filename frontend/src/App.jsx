import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import MenuPage from './pages/MenuPage';
import TablesPage from './pages/TablesPage';
import OrdersPage from './pages/OrdersPage';
import KitchenPage from './pages/KitchenPage';
import DashboardPage from './pages/DashboardPage';
import OrderHistoryPage from './pages/OrderHistoryPage';
import UsersPage from './pages/UsersPage';
import InventoryPage from './pages/InventoryPage';
import LoginPage from './pages/LoginPage';
import CustomerLayout from './components/CustomerLayout';
import CustomerHomePage from './pages/CustomerHomePage';
import CustomerMenuPage from './pages/CustomerMenuPage';
import QROrderPage from './pages/QROrderPage';
import QROrderStatusPage from './pages/QROrderStatusPage';
import { CartProvider } from './context/CartContext';
import { getHealth, getCurrentUser, logoutUser } from './services/api';
import './index.css';

const TAB_META = {
  menu: {
    title: 'Menu Management',
    subtitle: 'Browse real-time dishes, filter categories, and inspect availability across the menu.',
  },
  dashboard: {
    title: 'Executive Dashboard',
    subtitle: 'High-level metrics, daily sales velocity, and key operational indicators.',
  },
  tables: {
    title: 'Tables & Floor Plan',
    subtitle: 'Dining room layout, seat capacities, and table occupancy management.',
  },
  inventory: {
    title: 'Inventory & Supplies',
    subtitle: 'Monitor stock levels, manage recipes, track wastage, and record supplier deliveries.',
  },
  orders: {
    title: 'Orders & POS Terminal',
    subtitle: 'Process dine-in and takeaway orders, manage active tickets, and complete payments.',
  },
  kitchen: {
    title: 'Kitchen Display System',
    subtitle: 'Line cook ticket board with prep times and order status progression.',
  },
  order_history: {
    title: 'Order Management & Audit',
    subtitle: 'Browse live and historical tickets, inspect guest line items, filter by fulfillment status, and track order lifecycles.',
  },
  users: {
    title: 'User Accounts & Roles',
    subtitle: 'Administer system accounts, assign station roles, and manage access security.',
  },
};

const DEFAULT_TAB_FOR_ROLE = {
  admin: 'menu',
  manager: 'dashboard',
  cashier: 'orders',
  kitchen: 'kitchen',
};

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('menu');
  const [backendStatus, setBackendStatus] = useState({
    healthy: false,
    version: null,
    checked: false,
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Client-side URL Routing State
  const [currentUrl, setCurrentUrl] = useState(() => {
    if (typeof window !== 'undefined') {
      return {
        pathname: window.location.pathname || '/',
        search: window.location.search || '',
      };
    }
    return { pathname: '/', search: '' };
  });

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentUrl({
        pathname: window.location.pathname || '/',
        search: window.location.search || '',
      });
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = useCallback((toPath) => {
    if (typeof window !== 'undefined') {
      window.history.pushState({}, '', toPath);
      const url = new URL(window.location.origin + toPath);
      setCurrentUrl({
        pathname: url.pathname || '/',
        search: url.search || '',
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, []);

  // Check initial authentication state in background
  useEffect(() => {
    let isMounted = true;
    getCurrentUser()
      .then((user) => {
        if (isMounted && user && typeof user === 'object' && user.role) {
          setCurrentUser(user);
          setActiveTab(DEFAULT_TAB_FOR_ROLE[user.role] || 'menu');
        } else if (isMounted) {
          setCurrentUser(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setCurrentUser(null);
        }
      })
      .finally(() => {
        if (isMounted) {
          setAuthLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const checkConnectivity = useCallback(async () => {
    try {
      const data = await getHealth();
      setBackendStatus({
        healthy: data.status === 'healthy',
        version: data.version || '0.1.0',
        checked: true,
      });
    } catch (err) {
      setBackendStatus({
        healthy: false,
        version: null,
        checked: true,
      });
    }
  }, []);

  useEffect(() => {
    checkConnectivity();
    const timer = setInterval(checkConnectivity, 15000);
    return () => clearInterval(timer);
  }, [checkConnectivity]);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    setActiveTab(DEFAULT_TAB_FOR_ROLE[user.role] || 'menu');
    setRefreshKey((prev) => prev + 1);
    navigate('/staff');
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setCurrentUser(null);
      navigate('/login');
    }
  };

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await checkConnectivity();
    setRefreshKey((prev) => prev + 1);
    setTimeout(() => setIsRefreshing(false), 300);
  };

  // Handle QR table ordering routes (public, case-sensitive token)
  const rawPathname = currentUrl.pathname.replace(/\/+$/, '') || '/';
  const qrStatusMatch = rawPathname.match(/^\/order\/([^/]+)\/status\/([^/]+)$/i);
  if (qrStatusMatch) {
    return (
      <QROrderStatusPage
        token={qrStatusMatch[1]}
        orderNumber={qrStatusMatch[2]}
        onNavigate={navigate}
      />
    );
  }

  const qrOrderMatch = rawPathname.match(/^\/order\/([^/]+)$/i);
  if (qrOrderMatch) {
    return (
      <QROrderPage
        token={qrOrderMatch[1]}
        onNavigate={navigate}
      />
    );
  }

  // Determine route mode: Customer Website vs Staff Portal
  const pathname = currentUrl.pathname.toLowerCase().replace(/\/+$/, '') || '/';
  const isStaffRoute = pathname === '/staff' || pathname === '/login';

  // ── BRANCH 1: Public Customer Website Routes ──────────────────────────────
  if (!isStaffRoute) {
    // Extract query parameter if visiting menu with category filter
    const searchParams = new URLSearchParams(currentUrl.search);
    const categoryParam = searchParams.get('category');

    return (
      <CartProvider>
        <CustomerLayout currentRoute={pathname} onNavigate={navigate}>
          {pathname === '/menu' ? (
            <CustomerMenuPage
              key={`menu-${categoryParam || 'all'}`}
              initialCategoryId={categoryParam}
            />
          ) : (
            <CustomerHomePage onNavigate={navigate} />
          )}
        </CustomerLayout>
      </CartProvider>
    );
  }

  // ── BRANCH 2: Protected Staff Portal Routes (/staff and /login) ───────────

  // Splash loading while verifying session token for staff portal
  if (authLoading) {
    return (
      <div className="login-screen-wrapper">
        <div className="auth-splash-box">
          <div className="state-spinner" />
          <h2 className="auth-splash-title">Brew &amp; Co. POS Suite</h2>
          <p className="auth-splash-subtext">Verifying station security &amp; credentials...</p>
        </div>
      </div>
    );
  }

  // Unauthenticated visitor on /staff or /login -> Show Staff Login Page
  if (!currentUser) {
    return (
      <div>
        <div style={{
          backgroundColor: '#211714',
          borderBottom: '1px solid rgba(197, 164, 109, 0.2)',
          padding: '0.65rem 1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span style={{ color: '#C5A46D', fontSize: '0.85rem', fontWeight: 600 }}>
            Brew &amp; Co. Operations Management
          </span>
          <button
            type="button"
            onClick={() => navigate('/')}
            style={{
              background: 'none',
              border: '1px solid rgba(197, 164, 109, 0.4)',
              color: '#F5EFE5',
              padding: '0.35rem 0.85rem',
              borderRadius: '9999px',
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            &larr; Back to Customer Website
          </button>
        </div>
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      </div>
    );
  }

  // Authenticated Staff Member -> Render POS and Operations Suite
  const currentTabMeta = TAB_META[activeTab] || TAB_META.menu;

  return (
    <div className="pos-app-layout">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        backendStatus={backendStatus}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      <div className="main-viewport">
        {/* Top bar with quick customer website link for staff */}
        <div style={{
          backgroundColor: '#211714',
          borderBottom: '1px solid rgba(197, 164, 109, 0.15)',
          padding: '0.45rem 1.75rem',
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'center',
          gap: '1rem',
        }}>
          <button
            type="button"
            onClick={() => navigate('/')}
            style={{
              background: 'rgba(197, 164, 109, 0.12)',
              border: '1px solid rgba(197, 164, 109, 0.35)',
              color: '#C5A46D',
              padding: '0.25rem 0.75rem',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            &larr; View Customer Website
          </button>
        </div>

        <Header
          title={currentTabMeta.title}
          subtitle={currentTabMeta.subtitle}
          onRefresh={handleManualRefresh}
          isRefreshing={isRefreshing}
          currentUser={currentUser}
          onLogout={handleLogout}
        />

        <main className="content-scroll-container">
          {activeTab === 'menu' && <MenuPage key={refreshKey} />}
          {activeTab === 'dashboard' && <DashboardPage key={refreshKey} onNavigate={setActiveTab} />}
          {activeTab === 'tables' && <TablesPage key={refreshKey} currentUser={currentUser} />}
          {activeTab === 'inventory' && <InventoryPage key={refreshKey} currentUser={currentUser} />}
          {activeTab === 'orders' && <OrdersPage key={refreshKey} />}
          {activeTab === 'kitchen' && <KitchenPage key={refreshKey} />}
          {activeTab === 'order_history' && <OrderHistoryPage key={refreshKey} onNavigate={setActiveTab} />}
          {activeTab === 'users' && currentUser.role === 'admin' && <UsersPage key={refreshKey} currentUser={currentUser} />}
        </main>
      </div>
    </div>
  );
}
