import React, { useState, useEffect, useCallback } from 'react';
import { getQROrderStatus, createGuestPaymentOrder, verifyGuestPayment, getPublicPaymentConfig } from '../services/api';
import { openRazorpayCheckout } from '../utils/razorpay';

const STATUS_STEPS = [
  { key: 'pending', label: 'Received', desc: 'Order received by kitchen' },
  { key: 'in_progress', label: 'Preparing', desc: 'Being handcrafted by our baristas & chefs' },
  { key: 'served', label: 'Served', desc: 'Delivered fresh to your table' },
  { key: 'completed', label: 'Completed', desc: 'Order finalized' },
];

export default function QROrderStatusPage({ token, orderNumber, onNavigate }) {
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(new Date());

  // Payment state
  const [isPaying, setIsPaying] = useState(false);
  const [paymentError, setPaymentError] = useState(null);
  const [paymentSuccess, setPaymentSuccess] = useState(false);

  const fetchStatus = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true);
    setError(null);
    try {
      const data = await getQROrderStatus(orderNumber, token);
      setOrder(data);
      setLastRefreshed(new Date());
    } catch (err) {
      if (err.status === 403) {
        setError('Unauthorized: This order does not match your current table session.');
      } else if (err.status === 404) {
        setError('Order not found. Please check your order reference or consult the staff.');
      } else {
        setError(err.message || 'Unable to fetch current order status.');
      }
    } finally {
      if (isInitial) setLoading(false);
    }
  }, [orderNumber, token]);

  useEffect(() => {
    fetchStatus(true);
    const interval = setInterval(() => {
      fetchStatus(false);
    }, 15000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const getStepIndex = (status) => {
    switch (status) {
      case 'pending': return 0;
      case 'in_progress': return 1;
      case 'served': return 2;
      case 'completed': return 3;
      case 'cancelled': return -1;
      default: return 0;
    }
  };

  const currentStepIdx = order ? getStepIndex(order.status) : 0;
  const isCancelled = order?.status === 'cancelled';
  const isPaid = order?.payment_status === 'paid' || paymentSuccess;

  const handlePayOnline = async () => {
    if (!order || isPaying) return;
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
        order_number: order.order_number,
        qr_token: token,
      });

      await openRazorpayCheckout({
        keyId: orderRes.key_id,
        amountPaise: orderRes.amount_paise,
        currency: orderRes.currency,
        razorpayOrderId: orderRes.razorpay_order_id,
        orderNumber: order.order_number,
        onSuccess: async (payResponse) => {
          try {
            await verifyGuestPayment({
              order_number: order.order_number,
              qr_token: token,
              razorpay_order_id: payResponse.razorpay_order_id,
              razorpay_payment_id: payResponse.razorpay_payment_id,
              razorpay_signature: payResponse.razorpay_signature,
            });
            setPaymentSuccess(true);
            setOrder((prev) => ({
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

  if (loading) {
    return (
      <div className="qr-page">
        <div className="qr-loading">
          <div className="state-spinner" />
          <p>Tracking order {orderNumber}…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="qr-page">
        <header className="qr-header">
          <div className="qr-header-brand">
            <span className="qr-brand-name">Brew &amp; Co.</span>
          </div>
        </header>
        <div className="qr-error" style={{ margin: '2rem 1rem' }}>
          <div className="qr-error-icon">⚠</div>
          <h2>Tracking Error</h2>
          <p>{error}</p>
          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button
              type="button"
              className="qr-btn qr-btn-primary"
              onClick={() => fetchStatus(true)}
            >
              Retry
            </button>
            <button
              type="button"
              className="qr-btn qr-btn-secondary"
              onClick={() => onNavigate(`/order/${token}`)}
            >
              Back to Menu
            </button>
          </div>
        </div>
      </div>
    );
  }

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
          <span className="qr-brand-name">Brew &amp; Co.</span>
        </div>
        <div className="qr-table-badge">
          Table {order?.table_number}
        </div>
      </header>

      <div className="qr-status-container">
        {/* Status Header Card */}
        <div className="qr-status-hero">
          <div className="qr-status-badge-wrap">
            <span className={`qr-status-pill qr-status-pill-${order?.status}`}>
              {order?.status === 'in_progress' ? 'In Kitchen' : order?.status?.toUpperCase()}
            </span>
          </div>
          <h1 className="qr-status-title">Order #{order?.order_number}</h1>
          <p className="qr-status-subtitle">
            {isCancelled ? (
              <span style={{ color: '#D32F2F' }}>This order has been cancelled by staff.</span>
            ) : order?.status === 'completed' ? (
              <span>Your dining experience is completed. Thank you for visiting!</span>
            ) : order?.status === 'served' ? (
              <span>Your items have arrived at Table {order?.table_number}. Enjoy!</span>
            ) : order?.status === 'in_progress' ? (
              <span>The kitchen is crafting your order right now.</span>
            ) : (
              <span>We have received your order and queued it for preparation.</span>
            )}
          </p>
          <div className="qr-status-timestamp">
            Last checked: {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
        </div>

        {/* Progress Tracker (unless cancelled) */}
        {!isCancelled && (
          <div className="qr-progress-card">
            <div className="qr-timeline">
              {STATUS_STEPS.map((step, idx) => {
                const isDone = currentStepIdx > idx;
                const isCurrent = currentStepIdx === idx;
                return (
                  <div
                    key={step.key}
                    className={`qr-timeline-step ${isDone ? 'is-done' : ''} ${isCurrent ? 'is-current' : ''}`}
                  >
                    <div className="qr-timeline-marker">
                      {isDone ? (
                        <span>✓</span>
                      ) : (
                        <span>{idx + 1}</span>
                      )}
                    </div>
                    <div className="qr-timeline-content">
                      <div className="qr-timeline-label">{step.label}</div>
                      <div className="qr-timeline-desc">{step.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Order Details Ticket */}
        <div className="qr-ticket-card">
          <div className="qr-ticket-header">
            <div>
              <span className="qr-ticket-label">Receipt Summary</span>
              {order?.created_at && (
                <div style={{ fontSize: '0.75rem', color: '#888' }}>
                  {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>
            <span className="qr-ticket-number">Table {order?.table_number}</span>
          </div>

          <div className="qr-ticket-items">
            {order?.items?.map((item, idx) => (
              <div key={idx} className="qr-ticket-item">
                <div className="qr-ticket-item-left">
                  <span className="qr-ticket-item-qty">{item.quantity}×</span>
                  <div className="qr-ticket-item-details">
                    <span className="qr-ticket-item-name">{item.menu_item_name}</span>
                    {item.special_instructions && (
                      <span className="qr-ticket-item-notes">"{item.special_instructions}"</span>
                    )}
                  </div>
                </div>
                <span className="qr-ticket-item-price">
                  ₹{(Number(item.unit_price) * item.quantity).toFixed(2)}
                </span>
              </div>
            ))}
          </div>

          <div className="qr-ticket-totals">
            <div className="qr-ticket-total-row">
              <span>Subtotal</span>
              <span>₹{Number(order?.subtotal || 0).toFixed(2)}</span>
            </div>
            {Number(order?.tax || 0) > 0 && (
              <div className="qr-ticket-total-row">
                <span>Tax</span>
                <span>₹{Number(order?.tax || 0).toFixed(2)}</span>
              </div>
            )}
            <div className="qr-ticket-total-row qr-ticket-grand-total">
              <span>Total Amount</span>
              <span>₹{Number(order?.total || 0).toFixed(2)}</span>
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

        {/* Action Controls */}
        <div className="qr-status-actions">
          {!isPaid && !isCancelled && (
            <button
              type="button"
              className="qr-btn qr-btn-gold"
              onClick={handlePayOnline}
              disabled={isPaying}
            >
              {isPaying ? 'Connecting to Razorpay…' : `💳 Pay Online via Razorpay · ₹${Number(order?.total || 0).toFixed(2)}`}
            </button>
          )}

          <button
            type="button"
            className="qr-btn qr-btn-primary"
            onClick={() => onNavigate(`/order/${token}`)}
          >
            + Order More Items
          </button>
          <button
            type="button"
            className="qr-btn qr-btn-secondary"
            onClick={() => fetchStatus(false)}
          >
            ↻ Refresh Status
          </button>
        </div>
      </div>
    </div>
  );
}
