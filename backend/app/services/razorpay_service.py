import hashlib
import hmac
import logging
from typing import Any, Dict, Optional
import razorpay
from app.core.config import settings

logger = logging.getLogger("brew_and_co.payments")


def is_placeholder_credentials() -> bool:
    """Return True if Razorpay credentials are unset, development placeholders, or malformed."""
    key_id = (settings.RAZORPAY_KEY_ID or "").strip()
    key_secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    if not key_id or not key_secret:
        return True
    for marker in ("placeholder", "your_", "example", "changeme", "xxx"):
        if marker in key_id.lower() or marker in key_secret.lower():
            return True
    # Real keys start with 'rzp_test_' (or 'rzp_live_')
    if not (key_id.startswith("rzp_test_") or key_id.startswith("rzp_live_")):
        return True
    # Test key ID is standard 23 chars (rzp_test_ + 14 alphanumeric), at least 20
    if len(key_id) < 20:
        return True
    # Razorpay key secrets are 24-character alphanumeric strings
    if len(key_secret) < 20:
        return True
    return False


def get_razorpay_client() -> razorpay.Client:
    """Initialize official Razorpay SDK client."""
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_provider_order(
    amount_paise: int,
    currency: str = "INR",
    receipt: str = "",
    notes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Razorpay payment order via the official provider API.

    Raises:
        RuntimeError: If Razorpay credentials are unset or still placeholder values.
                      The caller (payment endpoint) must convert this into a safe HTTP 503.
        RuntimeError: If the Razorpay API call itself fails (network, auth, etc.).
    """
    if is_placeholder_credentials():
        raise RuntimeError(
            "Razorpay credentials are not configured. "
            "Add real RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET (starting with 'rzp_test_') "
            "to backend/.env — obtain them from Settings → API Keys in the Razorpay Dashboard."
        )

    client = get_razorpay_client()
    order_data = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt,
        "notes": notes or {},
        "payment_capture": 1,  # Auto-capture on authorization
    }
    try:
        response = client.order.create(data=order_data)
        return response
    except Exception as exc:
        err_msg = str(exc)
        logger.error(f"Razorpay order creation failed: {err_msg}", exc_info=True)
        if "authentication failed" in err_msg.lower():
            raise RuntimeError(
                "Payment provider authentication failed: Invalid Razorpay Key ID or Key Secret. "
                "Ensure that RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend/.env match an active "
                "Razorpay Test Mode key pair."
            ) from exc
        raise RuntimeError(f"Payment provider error: {err_msg}") from exc



def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """
    Verify Razorpay checkout payment signature using HMAC SHA-256 with key secret.
    Conforms strictly to Razorpay's official signature verification specification.
    """
    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return False

    secret = settings.RAZORPAY_KEY_SECRET or ""
    message = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, razorpay_signature)


def verify_webhook_signature(
    raw_body: bytes,
    signature: str,
) -> bool:
    """
    Verify Razorpay webhook signature using HMAC SHA-256 over exact raw request body.
    Conforms strictly to Razorpay's official webhook verification specification.
    """
    if not raw_body or not signature:
        return False

    secret = settings.RAZORPAY_WEBHOOK_SECRET or ""
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)
