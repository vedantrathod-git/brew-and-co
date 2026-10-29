import React, { useEffect, useState, useCallback } from 'react';
import { useCart } from '../context/CartContext';
import { formatUSD } from '../utils/formatters';
import { createQROrder, createGuestPaymentOrder, verifyGuestPayment, getPublicPaymentConfig } from '../services/api';
import { openRazorpayCheckout } from '../utils/razorpay';

function generateIdempotencyKey() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'cart-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 14);
}

export default function CustomerCartDrawer({ onNavigate }) {
  const {
    items,
    cartCount,
    subtotal,
    isCartOpen,
    setIsCartOpen,
    updateQuantity,
    removeFromCart,
    clearCart,
  } = useCart();

  // Order submission state
  const [customerName, setCustomerName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [orderResult, setOrderResult] = useState(null);

  // Payment state
  const [isPaying, setIsPaying] = useState(false);
  const [paymentError, setPaymentError] = useState(null);
  const [paymentSuccess, setPaymentSuccess] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isCartOpen) {
        setIsCartOpen(false);
      }
    };
    if (isCartOpen) {
      window.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isCartOpen, setIsCartOpen]);

  const handleClose = useCallback(() => {
    setIsCartOpen(false);
  }, [setIsCartOpen]);

  // Reset drawer state when opened
  useEffect(() => {
    if (isCartOpen) {
      setOrderResult(null);
      setSubmitError(null);
      setPaymentError(null);
      setPaymentSuccess(false);
    }
  }, [isCartOpen]);

  // Place order (takeaway — no QR token)
  const handlePlaceOrder = async () => {
    if (items.length === 0 || isSubmitting) return;
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const payload = {
        qr_token: null,
        items: items.map((item) => ({
          menu_item_id: item.id,
          quantity: item.quantity,
          special_instructions: null,
        })),
        idempotency_key: generateIdempotencyKey(),
        customer_name: customerName.trim() || null,
      };

      const result = await createQROrder(payload);
      setOrderResult(result);
      clearCart();
      setPaymentError(null);
      setPaymentSuccess(false);
    } catch (err) {
      setSubmitError(
        err.data?.detail || err.message || 'Could not place your order. Please try again.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  // Pay online via Razorpay
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

      // For takeaway orders, table_id is null so no qr_token needed
      const orderRes = await createGuestPaymentOrder({
        order_number: orderResult.order_number,
        qr_token: null,
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
              qr_token: null,
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
            setPaymentError(
              err.data?.detail || err.message || 'Payment signature verification failed.'
            );
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
      setPaymentError(
        err.data?.detail || err.message || 'Unable to initialise Razorpay checkout.'
      );
      setIsPaying(false);
    }
  };

  if (!isCartOpen) return null;

  const isPaid =
    orderResult?.payment_status === 'paid' || paymentSuccess;

  return (
    <div className="cart-drawer-overlay" onClick={handleClose}>
      <aside
        className="cart-drawer-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cart-drawer-title"
      >
        {/* Drawer Header */}
        <div className="cart-drawer-header">
          <div className="cart-header-title-box">
            <h2 id="cart-drawer-title" className="cart-drawer-title">
              {orderResult ? 'Order Confirmed' : 'Your Order'}
            </h2>
            {!orderResult && (
              <span className="cart-items-count">
                ({cartCount} {cartCount === 1 ? 'item' : 'items'})
              </span>
            )}
          </div>
          <button
            type="button"
            className="cart-drawer-close"
            onClick={handleClose}
            aria-label="Close cart drawer"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* ── ORDER CONFIRMATION VIEW ── */}
        {orderResult ? (
          <div className="cart-drawer-body cart-confirmation-body">
            {/* Success icon */}
            <div className="cart-confirmation-icon">✓</div>
            <h3 className="cart-confirmation-title">Order Placed!</h3>
            <p className="cart-confirmation-subtitle">
              Your order has been sent to our kitchen.
            </p>

            {/* Ticket */}
            <div className="cart-ticket-card">
              <div className="cart-ticket-header">
                <span className="cart-ticket-label">Order Ticket</span>
                <span className="cart-ticket-number">{orderResult.order_number}</span>
              </div>
              <div className="cart-ticket-items">
                {orderResult.items.map((item, idx) => (
                  <div key={idx} className="cart-ticket-item">
                    <span className="cart-ticket-item-name">
                      {item.quantity}× {item.menu_item_name}
                    </span>
                    <span className="cart-ticket-item-price">
                      ₹{(Number(item.unit_price) * item.quantity).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="cart-ticket-totals">
                <div className="cart-ticket-total-row">
                  <span>Subtotal</span>
                  <span>₹{Number(orderResult.subtotal).toFixed(2)}</span>
                </div>
                {Number(orderResult.tax) > 0 && (
                  <div className="cart-ticket-total-row">
                    <span>Tax</span>
                    <span>₹{Number(orderResult.tax).toFixed(2)}</span>
                  </div>
                )}
                <div className="cart-ticket-total-row cart-ticket-grand-total">
                  <span>Total</span>
                  <span>₹{Number(orderResult.total).toFixed(2)}</span>
                </div>
                <div className="cart-ticket-total-row">
                  <span>Payment</span>
                  <span
                    className={`cart-status-pill ${
                      isPaid ? 'cart-status-paid' : 'cart-status-pending'
                    }`}
                  >
                    {isPaid ? '✓ Paid (Razorpay)' : 'Pending'}
                  </span>
                </div>
              </div>
            </div>

            {/* Payment alerts */}
            {paymentError && (
              <div className="cart-alert cart-alert-error">⚠ {paymentError}</div>
            )}
            {paymentSuccess && (
              <div className="cart-alert cart-alert-success">
                ✓ Payment verified via Razorpay Sandbox!
              </div>
            )}

            {/* Actions */}
            <div className="cart-confirmation-actions">
              {!isPaid && (
                <button
                  id="cart-pay-razorpay-btn"
                  type="button"
                  className="cart-checkout-btn"
                  onClick={handlePayOnline}
                  disabled={isPaying}
                >
                  {isPaying
                    ? 'Connecting to Razorpay…'
                    : `💳 Pay Online · ₹${Number(orderResult.total).toFixed(2)}`}
                </button>
              )}
              <button
                type="button"
                className="cart-continue-btn"
                onClick={() => {
                  setOrderResult(null);
                  handleClose();
                  onNavigate('/menu');
                }}
              >
                Order More Items
              </button>
              {!isPaid && (
                <p className="cart-cash-note">
                  Or pay with cash at the counter when you collect your order.
                </p>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* ── CART ITEMS VIEW ── */}
            <div className="cart-drawer-body">
              {items.length === 0 ? (
                <div className="cart-empty-state">
                  <div className="cart-empty-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
                      <path d="M3 6h18" />
                      <path d="M16 10a4 4 0 0 1-8 0" />
                    </svg>
                  </div>
                  <h3 className="cart-empty-title">Your cart is empty</h3>
                  <p className="cart-empty-text">
                    Explore our specialty coffees, fresh French pastries, and brunch selections.
                  </p>
                  <button
                    type="button"
                    className="cart-browse-btn"
                    onClick={() => {
                      setIsCartOpen(false);
                      onNavigate('/menu');
                    }}
                  >
                    Browse Artisanal Menu
                  </button>
                </div>
              ) : (
                <ul className="cart-items-list" aria-label="Cart items">
                  {items.map((item) => (
                    <li key={item.id} className="cart-item-row">
                      <div className="cart-item-info">
                        <span className="cart-item-name">{item.name}</span>
                        {item.category_name && (
                          <span className="cart-item-cat">{item.category_name}</span>
                        )}
                        <span className="cart-item-unit-price">{formatUSD(item.price)} each</span>
                      </div>

                      <div className="cart-item-actions">
                        <div className="cart-qty-controls">
                          <button
                            type="button"
                            className="cart-qty-btn"
                            onClick={() => updateQuantity(item.id, -1)}
                            aria-label={`Decrease quantity of ${item.name}`}
                          >
                            &minus;
                          </button>
                          <span className="cart-qty-value">{item.quantity}</span>
                          <button
                            type="button"
                            className="cart-qty-btn"
                            onClick={() => updateQuantity(item.id, 1)}
                            aria-label={`Increase quantity of ${item.name}`}
                          >
                            +
                          </button>
                        </div>

                        <span className="cart-item-line-total">
                          {formatUSD(Number(item.price) * item.quantity)}
                        </span>

                        <button
                          type="button"
                          className="cart-item-remove"
                          onClick={() => removeFromCart(item.id)}
                          aria-label={`Remove ${item.name} from cart`}
                        >
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* ── FOOTER ── */}
            {items.length > 0 && (
              <div className="cart-drawer-footer">
                {/* Optional name field */}
                <div className="cart-name-field">
                  <label htmlFor="cart-customer-name" className="cart-name-label">
                    Your name (optional)
                  </label>
                  <input
                    id="cart-customer-name"
                    type="text"
                    className="cart-name-input"
                    placeholder="e.g. Alex"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    maxLength={80}
                  />
                </div>

                <div className="cart-subtotal-row">
                  <span className="cart-subtotal-label">Subtotal</span>
                  <span className="cart-subtotal-value">{formatUSD(subtotal)}</span>
                </div>

                {submitError && (
                  <div className="cart-alert cart-alert-error">⚠ {submitError}</div>
                )}

                {/* Primary CTA */}
                <button
                  id="cart-place-order-btn"
                  type="button"
                  className="cart-checkout-btn"
                  onClick={handlePlaceOrder}
                  disabled={isSubmitting || items.length === 0}
                >
                  {isSubmitting ? 'Placing Order…' : `Place Order · ${formatUSD(subtotal)}`}
                </button>

                <div className="cart-footer-buttons">
                  <button
                    type="button"
                    className="cart-clear-btn"
                    onClick={clearCart}
                  >
                    Clear Cart
                  </button>
                  <button
                    type="button"
                    className="cart-continue-btn"
                    onClick={() => {
                      setIsCartOpen(false);
                      onNavigate('/menu');
                    }}
                  >
                    Add More Items
                  </button>
                </div>

                <p className="cart-notice">
                  Place your order and pay online via Razorpay or with cash at the counter.
                </p>
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
