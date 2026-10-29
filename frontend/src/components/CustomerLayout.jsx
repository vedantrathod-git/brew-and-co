import React from 'react';
import CustomerNavbar from './CustomerNavbar';
import CustomerFooter from './CustomerFooter';
import CustomerCartDrawer from './CustomerCartDrawer';

export default function CustomerLayout({ children, currentRoute, onNavigate }) {
  return (
    <div className="customer-app-layout">
      {/* Brand Navigation Header */}
      <CustomerNavbar currentRoute={currentRoute} onNavigate={onNavigate} />

      {/* Main Customer View */}
      <main className="customer-main-content">
        {children}
      </main>

      {/* Slide-out Cart Drawer */}
      <CustomerCartDrawer onNavigate={onNavigate} />

      {/* Brand Footer */}
      <CustomerFooter onNavigate={onNavigate} />
    </div>
  );
}
