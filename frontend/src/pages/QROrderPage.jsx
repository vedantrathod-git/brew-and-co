import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { getPublicMenu, getQRTableInfo, createQROrder, createGuestPaymentOrder, verifyGuestPayment, getPublicPaymentConfig } from '../services/api';

import { filterCuratedMenu } from '../utils/curatedCatalog';
import DishImage from '../components/DishImage';
import { openRazorpayCheckout } from '../utils/razorpay';

/**
 * QROrderPage — Mobile-first dine-in ordering experience for customers who scan
 * a table QR code. Renders at /order/:token.
 *
 * Uses its own local cart state (independent of the customer website CartContext)
 * to avoid localStorage collisions between browsing sessions.
 */
export default function QROrderPage({ token, onNavigate }) {
  // Table and loading state
  const [tableInfo, setTableInfo] = useState(null);
  const [tableError, setTableError] = useState(null);
  const [tableLoading, setTableLoading] = useState(true);

  // Menu state
  const [categories, setCategories] = useState([]);
  const [items, setItems] = useState([]);
  const [menuLoading, setMenuLoading] = useState(true);

  // Filters
  const [selectedCategoryId, setSelectedCategoryId] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Local cart state (not shared with main customer website)
  const [cart, setCart] = useState([]);
  const [cartOpen, setCartOpen] = useState(false);

  // Order submission
  const [customerName, setCustomerName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [orderResult, setOrderResult] = useState(null);

  // Payment state
  const [isPaying, setIsPaying] = useState(false);
  const [paymentError, setPaymentError] = useState(null);
  const [paymentSuccess, setPaymentSuccess] = useState(false);

  // Product detail
  const [selectedProduct, setSelectedProduct] = useState(null);

  // Validate QR token on mount
  useEffect(() => {
    let isMounted = true;
    setTableLoading(true);
    getQRTableInfo(token)
      .then((info) => {
        if (isMounted) setTableInfo(info);
      })
      .catch((err) => {
        if (isMounted) {
          setTableError(
            err.status === 404
              ? 'This QR code is invalid or has been deactivated. Please ask café staff for assistance.'
              : 'Unable to verify your table. Please check your connection and try again.'
          );
        }
      })
      .finally(() => {
        if (isMounted) setTableLoading(false);
      });
    return () => { isMounted = false; };
  }, [token]);

  // Load curated menu
  useEffect(() => {
    let isMounted = true;
    getPublicMenu()
      .then((raw) => {
        const curated = filterCuratedMenu(raw);
        if (isMounted) {
          setCategories(curated.categories || []);
          setItems(curated.items || []);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (isMounted) setMenuLoading(false);
      });
    return () => { isMounted = false; };
  }, []);

  // Filter items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (selectedCategoryId !== 'all' && item.category_id !== Number(selectedCategoryId)) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        return (
          (item.name && item.name.toLowerCase().includes(q)) ||
          (item.description && item.description.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [items, selectedCategoryId, searchQuery]);

  // Cart operations
  const addToCart = useCallback((item) => {
    setCart((prev) => {
      const existing = prev.find((c) => c.id === item.id);
      if (existing) {
        return prev.map((c) => c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c);
      }
      return [...prev, { id: item.id, name: item.name, price: item.price, quantity: 1, notes: '' }];
    });
  }, []);

  const updateQuantity = useCallback((itemId, delta) => {
    setCart((prev) => {
      return prev
        .map((c) => c.id === itemId ? { ...c, quantity: c.quantity + delta } : c)
        .filter((c) => c.quantity > 0);
    });
  }, []);

  const updateNotes = useCallback((itemId, notes) => {
    setCart((prev) => prev.map((c) => c.id === itemId ? { ...c, notes } : c));
  }, []);

  const clearCart = useCallback(() => setCart([]), []);

  const cartCount = useMemo(() => cart.reduce((s, c) => s + c.quantity, 0), [cart]);
  const cartSubtotal = useMemo(
    () => cart.reduce((s, c) => s + Number(c.price) * c.quantity, 0),
    [cart]
  );

  // Generate idempotency key
  const generateIdempotencyKey = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'qr-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 14);
  };

  // Submit order
  const handleSubmitOrder = async () => {
    if (cart.length === 0 || isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const payload = {
        qr_token: token,
        items: cart.map((c) => ({
          menu_item_id: c.id,
          quantity: c.quantity,
          special_instructions: c.notes.trim() || null,
        })),
        idempotency_key: generateIdempotencyKey(),
        customer_name: customerName.trim() || null,
      };

      const result = await createQROrder(payload);
      setOrderResult(result);
      setCart([]);
      setPaymentError(null);
      setPaymentSuccess(false);
    } catch (err) {
      setSubmitError(
        err.data?.detail || err.message || 'Order submission failed. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  // Pay Online via Razorpay
  const handlePayOnline = async () => {
    if (!orderResult || isPaying) return;
    setIsPaying(true);
    setPaymentError(null);

    try {
      // ── Pre-flight: verify real credentials are configured ──────────
      const config = await getPublicPaymentConfig();
      if (!config.razorpay_configured || config.key_id.startsWith('rzp_test_placeholder')) {
        setPaymentError(
          'Online payment is not yet configured for this café. ' +
          'Please pay with cash at the counter when collecting your order.'
        );
        setIsPaying(false);
        return;
      }
      // ────────────────────────────────────────────────────────────────

      const orderRes = await createGuestPaymentOrder({
        order_number: orderResult.order_number,
        qr_token: token,
      });

      await openRazorpayCheckout({
        keyId: orderRes.key_id,
        amountPaise: orderRes.amount_paise,
        currency: orderRes.currency,
        razorpayOrderId: orderRes.razorpay_order_id,
        orderNumber: orderResult.order_number,
        customerName: customerName.trim() || undefined,
        onSuccess: async (payResponse) => {
          try {
            await verifyGuestPayment({
              order_number: orderResult.order_number,
              qr_token: token,
              razorpay_order_id: payResponse.razorpay_order_id,
              razorpay_payment_id: payResponse.razorpay_payment_id,
              razorpay_signature: payResponse.razorpay_signature,
            });
            setPaymentSuccess(true);
            setOrderResult((prev) => ({
              ...prev,
              payment_status: 'paid',
              payment_method: 'razorpay',
            }));
          } catch (err) {
            setPaymentError(err.data?.detail || err.message || 'Payment signature verification failed.');
          } finally {
            setIsPaying(false);
          }
        },
        onDismiss: (err) => {
          setIsPaying(false);
          if (err && err.message) {
            setPaymentError(err.message);
          }
        },
      });
    } catch (err) {
      setPaymentError(err.data?.detail || err.message || 'Unable to initialize Razorpay checkout.');
      setIsPaying(false);
    }
  };


  // ── ORDER CONFIRMATION VIEW ──────────────────────────────────────────
  if (orderResult) {
    const isPaid = orderResult.payment_status === 'paid' || paymentSuccess;

    return (
      <div className="qr-page">
        <div className="qr-confirmation">
          <div className="qr-confirmation-icon">✓</div>
          <h1 className="qr-confirmation-title">Order Placed!</h1>
          <p className="qr-confirmation-subtitle">
            Your order has been sent to the kitchen at <strong>Table {orderResult.table_number}</strong>.
          </p>

          <div className="qr-ticket-card">
            <div className="qr-ticket-header">
              <span className="qr-ticket-label">Order Ticket</span>
              <span className="qr-ticket-number">{orderResult.order_number}</span>
            </div>
            <div className="qr-ticket-items">
              {orderResult.items.map((item, idx) => (
                <div key={idx} className="qr-ticket-item">
                  <span className="qr-ticket-item-name">
                    {item.quantity}× {item.menu_item_name}
                  </span>
                  <span className="qr-ticket-item-price">
                    ₹{(Number(item.unit_price) * item.quantity).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
            <div className="qr-ticket-totals">
              <div className="qr-ticket-total-row">
                <span>Subtotal</span>
                <span>₹{Number(orderResult.subtotal).toFixed(2)}</span>
              </div>
              {Number(orderResult.tax) > 0 && (
                <div className="qr-ticket-total-row">
                  <span>Tax</span>
                  <span>₹{Number(orderResult.tax).toFixed(2)}</span>
                </div>
              )}
              <div className="qr-ticket-total-row qr-ticket-grand-total">
                <span>Total</span>
                <span>₹{Number(orderResult.total).toFixed(2)}</span>
              </div>
              <div className="qr-ticket-total-row qr-ticket-payment-status">
                <span>Payment Status</span>
                <span className={`qr-status-pill ${isPaid ? 'qr-status-pill-served' : 'qr-status-pill-pending'}`}>
                  {isPaid ? '✓ Paid Online (Razorpay)' : 'Pending (Cash / Online)'}
                </span>
              </div>
            </div>
          </div>

          {paymentError && (
            <div className="qr-payment-alert qr-payment-error">
              <span>⚠ {paymentError}</span>
            </div>
          )}

          {paymentSuccess && (
            <div className="qr-payment-alert qr-payment-success">
              <span>✓ Payment verified and confirmed via Razorpay Sandbox!</span>
            </div>
          )}

          <div className="qr-confirmation-actions">
            {!isPaid && (
              <button
                type="button"
                className="qr-btn qr-btn-gold"
                onClick={handlePayOnline}
                disabled={isPaying}
              >
                {isPaying ? 'Connecting to Razorpay…' : `💳 Pay Online via Razorpay · ₹${Number(orderResult.total).toFixed(2)}`}
              </button>
            )}

            <button
              type="button"
              className="qr-btn qr-btn-primary"
              onClick={() => onNavigate(`/order/${token}/status/${orderResult.order_number}`)}
            >
              Track Order Status
            </button>
            <button
              type="button"
              className="qr-btn qr-btn-secondary"
              onClick={() => setOrderResult(null)}
            >
              Order More Items
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── LOADING / ERROR STATES ───────────────────────────────────────────
  if (tableLoading) {
    return (
      <div className="qr-page">
        <div className="qr-loading">
          <div className="state-spinner" />
          <p>Verifying your table…</p>
        </div>
      </div>
    );
  }

  if (tableError) {
    return (
      <div className="qr-page">
        <div className="qr-error">
          <div className="qr-error-icon">⚠</div>
          <h2>QR Code Error</h2>
          <p>{tableError}</p>
        </div>
      </div>
    );
  }

  // ── MAIN QR ORDERING EXPERIENCE ──────────────────────────────────────
  return (
    <div className="qr-page">
      {/* Header */}
      <header className="qr-header">
        <div className="qr-header-brand">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" className="qr-brand-icon">
            <path d="M18 8h1a4 4 0 0 1 0 8h-1" />
            <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
            <line x1="6" y1="1" x2="6" y2="4" />
            <line x1="10" y1="1" x2="10" y2="4" />
            <line x1="14" y1="1" x2="14" y2="4" />
          </svg>
          <span className="qr-brand-name">Brew & Co.</span>
        </div>
        <div className="qr-table-badge">
          Table {tableInfo?.table_number}
        </div>
      </header>

      <div className="qr-menu-title-section">
        <h1 className="qr-menu-heading">Dine-In Menu</h1>
        <p className="qr-menu-subheading">Browse, customize &amp; order from your seat</p>
      </div>

      {/* Category Pills */}
      <div className="qr-category-bar">
        <button
          type="button"
          className={`qr-category-pill ${selectedCategoryId === 'all' ? 'active' : ''}`}
          onClick={() => setSelectedCategoryId('all')}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat.id}
            type="button"
            className={`qr-category-pill ${selectedCategoryId === cat.id ? 'active' : ''}`}
            onClick={() => setSelectedCategoryId(cat.id)}
          >
            {cat.name} ({cat.item_count})
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="qr-search-bar">
        <input
          type="text"
          className="qr-search-input"
          placeholder="Search menu…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button type="button" className="qr-search-clear" onClick={() => setSearchQuery('')}>✕</button>
        )}
      </div>

      {/* Menu Items Grid */}
      {menuLoading ? (
        <div className="qr-loading" style={{ minHeight: '200px' }}>
          <div className="state-spinner" />
        </div>
      ) : (
        <div className="qr-items-grid">
          {filteredItems.map((item) => {
            const inCart = cart.find((c) => c.id === item.id);
            return (
              <div key={item.id} className="qr-item-card">
                <div className="qr-item-image" onClick={() => setSelectedProduct(item)}>
                  <DishImage product={item} className="qr-item-img" />
                </div>
                <div className="qr-item-info">
                  <h3 className="qr-item-name" onClick={() => setSelectedProduct(item)}>
                    {item.name}
                  </h3>
                  <p className="qr-item-price">₹{Number(item.price).toFixed(2)}</p>
                  {inCart ? (
                    <div className="qr-item-qty-controls">
                      <button type="button" onClick={() => updateQuantity(item.id, -1)}>−</button>
                      <span>{inCart.quantity}</span>
                      <button type="button" onClick={() => updateQuantity(item.id, 1)}>+</button>
                    </div>
                  ) : (
                    <button type="button" className="qr-add-btn" onClick={() => addToCart(item)}>
                      + Add
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {filteredItems.length === 0 && (
            <p className="qr-empty-msg">No items match your search.</p>
          )}
        </div>
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <div className="qr-modal-overlay" onClick={() => setSelectedProduct(null)}>
          <div className="qr-modal-content" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="qr-modal-close" onClick={() => setSelectedProduct(null)}>✕</button>
            <DishImage product={selectedProduct} className="qr-modal-image" />
            <h2 className="qr-modal-title">{selectedProduct.name}</h2>
            <p className="qr-modal-desc">{selectedProduct.description || 'A hand-crafted Brew & Co. original.'}</p>
            <p className="qr-modal-price">₹{Number(selectedProduct.price).toFixed(2)}</p>
            <button
              type="button"
              className="qr-btn qr-btn-primary"
              onClick={() => { addToCart(selectedProduct); setSelectedProduct(null); }}
            >
              Add to Order
            </button>
          </div>
        </div>
      )}

      {/* Cart Review Drawer */}
      {cartOpen && (
        <div className="qr-cart-overlay" onClick={() => setCartOpen(false)}>
          <div className="qr-cart-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="qr-cart-header">
              <h2>Your Order</h2>
              <button type="button" onClick={() => setCartOpen(false)}>✕</button>
            </div>
            {cart.length === 0 ? (
              <p className="qr-cart-empty">Your order is empty. Browse the menu to add items.</p>
            ) : (
              <>
                <div className="qr-cart-items">
                  {cart.map((c) => (
                    <div key={c.id} className="qr-cart-item">
                      <div className="qr-cart-item-top">
                        <span className="qr-cart-item-name">{c.name}</span>
                        <span className="qr-cart-item-price">₹{(Number(c.price) * c.quantity).toFixed(2)}</span>
                      </div>
                      <div className="qr-cart-item-controls">
                        <div className="qr-item-qty-controls">
                          <button type="button" onClick={() => updateQuantity(c.id, -1)}>−</button>
                          <span>{c.quantity}</span>
                          <button type="button" onClick={() => updateQuantity(c.id, 1)}>+</button>
                        </div>
                      </div>
                      <input
                        type="text"
                        className="qr-cart-notes-input"
                        placeholder="Special instructions…"
                        value={c.notes}
                        onChange={(e) => updateNotes(c.id, e.target.value)}
                        maxLength={255}
                      />
                    </div>
                  ))}
                </div>

                <div className="qr-cart-footer">
                  <div className="qr-cart-name-input">
                    <input
                      type="text"
                      placeholder="Your name (optional)"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      maxLength={50}
                    />
                  </div>
                  <div className="qr-cart-subtotal">
                    <span>Subtotal</span>
                    <span>₹{cartSubtotal.toFixed(2)}</span>
                  </div>
                  {submitError && <p className="qr-submit-error">{submitError}</p>}
                  <button
                    type="button"
                    className="qr-btn qr-btn-primary qr-btn-block"
                    disabled={isSubmitting}
                    onClick={handleSubmitOrder}
                  >
                    {isSubmitting ? 'Placing Order…' : `Place Order · ₹${cartSubtotal.toFixed(2)}`}
                  </button>
                  <button
                    type="button"
                    className="qr-btn qr-btn-ghost"
                    onClick={clearCart}
                  >
                    Clear Order
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Floating Cart Bar */}
      {cart.length > 0 && !cartOpen && (
        <div className="qr-floating-cart" onClick={() => setCartOpen(true)}>
          <div className="qr-floating-cart-left">
            <span className="qr-floating-cart-count">{cartCount}</span>
            <span className="qr-floating-cart-label">{cartCount === 1 ? 'item' : 'items'}</span>
          </div>
          <span className="qr-floating-cart-text">View Order</span>
          <span className="qr-floating-cart-total">₹{cartSubtotal.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}
