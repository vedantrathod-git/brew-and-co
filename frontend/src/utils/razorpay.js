/**
 * Helper to dynamically load the official Razorpay Checkout SDK.
 */
let razorpayLoadPromise = null;

export function loadRazorpaySDK() {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window not available'));
  if (window.Razorpay) return Promise.resolve(true);

  if (!razorpayLoadPromise) {
    razorpayLoadPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => {
        razorpayLoadPromise = null;
        reject(new Error('Failed to load Razorpay Checkout script. Check your internet connection.'));
      };
      document.body.appendChild(script);
    });
  }

  return razorpayLoadPromise;
}

/**
 * Open Razorpay Standard Checkout modal for a given order.
 *
 * @param {Object} params
 * @param {string} params.keyId - Public Razorpay key ID
 * @param {number} params.amountPaise - Amount in paise
 * @param {string} params.currency - Currency code (e.g. "INR")
 * @param {string} params.razorpayOrderId - Provider order ID
 * @param {string} params.orderNumber - Café order number
 * @param {string} [params.customerName] - Guest name
 * @param {Function} params.onSuccess - Callback on payment success: { razorpay_order_id, razorpay_payment_id, razorpay_signature }
 * @param {Function} params.onDismiss - Callback on modal close / cancellation / failure
 */
export async function openRazorpayCheckout({
  keyId,
  amountPaise,
  currency = 'INR',
  razorpayOrderId,
  orderNumber,
  customerName = '',
  onSuccess,
  onDismiss,
}) {
  if (!keyId || keyId.startsWith('rzp_test_placeholder')) {
    throw new Error('Razorpay is not configured with valid credentials. Please pay with cash at the counter.');
  }

  await loadRazorpaySDK();

  if (!window.Razorpay) {
    throw new Error('Razorpay SDK could not be initialized.');
  }

  const options = {
    key: keyId,
    amount: amountPaise,
    currency,
    name: 'Brew & Co.',
    description: `Dine-In Order #${orderNumber}`,
    image: 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=128&auto=format&fit=crop&q=80',
    order_id: razorpayOrderId,
    prefill: {
      name: customerName || '',
    },
    theme: {
      color: '#211714', // Midnight Espresso brand color
    },
    modal: {
      ondismiss: () => {
        if (onDismiss) onDismiss(new Error('Payment checkout was closed or cancelled by customer.'));
      },
    },
    handler: (response) => {
      if (onSuccess) {
        onSuccess({
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
        });
      }
    },
  };

  const rzp = new window.Razorpay(options);
  rzp.on('payment.failed', (response) => {
    if (onDismiss) {
      const errDetail = response.error?.description || 'Payment was declined or failed.';
      onDismiss(new Error(errDetail));
    }
  });

  rzp.open();
}
