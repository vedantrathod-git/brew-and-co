import React, { useState } from 'react';
import { useCart } from '../context/CartContext';

export default function CustomerNavbar({ currentRoute, onNavigate }) {
  const { cartCount, setIsCartOpen } = useCart();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleNavClick = (route, e) => {
    e.preventDefault();
    setMobileMenuOpen(false);
    onNavigate(route);
  };

  return (
    <header className="customer-header">
      <div className="customer-header-inner">
        {/* Brand Identity */}
        <a
          href="/"
          className="customer-brand"
          onClick={(e) => handleNavClick('/', e)}
          aria-label="Brew & Co. Home"
        >
          <div className="customer-brand-symbol">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path d="M18 8h1a4 4 0 0 1 0 8h-1" />
              <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
              <line x1="6" y1="1" x2="6" y2="4" />
              <line x1="10" y1="1" x2="10" y2="4" />
              <line x1="14" y1="1" x2="14" y2="4" />
            </svg>
          </div>
          <div className="customer-brand-text">
            <span className="customer-brand-name">Brew &amp; Co.</span>
            <span className="customer-brand-tagline">Specialty Coffee &amp; Bakery</span>
          </div>
        </a>

        {/* Desktop Navigation Links */}
        <nav className="customer-desktop-nav" aria-label="Main Navigation">
          <a
            href="/"
            className={`customer-nav-link ${currentRoute === '/' || currentRoute === '/home' ? 'active' : ''}`}
            onClick={(e) => handleNavClick('/', e)}
          >
            Home
          </a>
          <a
            href="/menu"
            className={`customer-nav-link ${currentRoute === '/menu' ? 'active' : ''}`}
            onClick={(e) => handleNavClick('/menu', e)}
          >
            Artisanal Menu
          </a>
          <a
            href="#story"
            className="customer-nav-link"
            onClick={(e) => {
              e.preventDefault();
              if (currentRoute !== '/' && currentRoute !== '/home') {
                onNavigate('/');
                setTimeout(() => {
                  document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });
                }, 100);
              } else {
                document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });
              }
            }}
          >
            Our Story
          </a>
        </nav>

        {/* Header Actions: Cart & Staff Portal */}
        <div className="customer-header-actions">
          {/* Cart Trigger */}
          <button
            type="button"
            className="customer-cart-trigger"
            onClick={() => setIsCartOpen(true)}
            aria-label={`View cart containing ${cartCount} items`}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
              <path d="M3 6h18" />
              <path d="M16 10a4 4 0 0 1-8 0" />
            </svg>
            <span className="customer-cart-label">Cart</span>
            {cartCount > 0 && <span className="customer-cart-badge">{cartCount}</span>}
          </button>

          {/* Discrete Staff Portal Navigation */}
          <a
            href="/staff"
            className="customer-staff-link"
            onClick={(e) => handleNavClick('/staff', e)}
            title="Access Staff Operations Terminal"
            aria-label="Staff Operations Portal"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>Staff Portal</span>
          </a>

          {/* Mobile Menu Toggle Button */}
          <button
            type="button"
            className="customer-mobile-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="customer-mobile-menu">
          <nav aria-label="Mobile Navigation">
            <a
              href="/"
              className={`customer-mobile-link ${currentRoute === '/' || currentRoute === '/home' ? 'active' : ''}`}
              onClick={(e) => handleNavClick('/', e)}
            >
              Home
            </a>
            <a
              href="/menu"
              className={`customer-mobile-link ${currentRoute === '/menu' ? 'active' : ''}`}
              onClick={(e) => handleNavClick('/menu', e)}
            >
              Artisanal Menu
            </a>
            <a
              href="#story"
              className="customer-mobile-link"
              onClick={(e) => {
                e.preventDefault();
                setMobileMenuOpen(false);
                if (currentRoute !== '/' && currentRoute !== '/home') {
                  onNavigate('/');
                  setTimeout(() => {
                    document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });
                  }, 100);
                } else {
                  document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });
                }
              }}
            >
              Our Story
            </a>
            <a
              href="/staff"
              className="customer-mobile-link customer-mobile-staff-link"
              onClick={(e) => handleNavClick('/staff', e)}
            >
              Staff Portal &rarr;
            </a>
          </nav>
        </div>
      )}
    </header>
  );
}
