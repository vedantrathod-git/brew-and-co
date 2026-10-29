#!/usr/bin/env python3
"""Phase 22 — Unit Test Suite for Razorpay Payment Integration.

Tests cover:
1. Missing / placeholder credential detection (is_placeholder_credentials).
2. Refusal to create provider order with placeholder credentials (HTTP 503 / RuntimeError).
3. Genuine provider order creation via official Razorpay SDK (mocked in tests).
4. Provider API failure handling and error isolation.
5. HMAC SHA-256 signature verification (valid, invalid, tampered, empty).
6. Webhook raw body signature verification (valid, invalid, empty).
7. Public config endpoint logic (razorpay_configured flag).
8. Guest/Takeaway order support (no qr_token required when table_id is None).
9. Dine-in table scope protection (403 when qr_token missing or mismatched).
10. Payment idempotency (reusing created payment on retry without duplicate provider call).
11. Already-paid order protection (409 Conflict).
"""

from decimal import Decimal
import hashlib
import hmac
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.models.order import Order
from app.models.payment import Payment
from app.models.table import RestaurantTable
from app.schemas.payment import (
    PaymentConfigResponse,
    PaymentOrderCreateRequest,
    PaymentVerifyRequest,
)
from app.services.razorpay_service import (
    create_provider_order,
    is_placeholder_credentials,
    verify_payment_signature,
    verify_webhook_signature,
)
from app.api.payments import (
    get_public_payment_config,
    create_guest_payment_order,
    verify_guest_payment,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Credential Validation & Placeholder Detection
# ─────────────────────────────────────────────────────────────────────────────

def test_placeholder_credentials_detection():
    """Verify is_placeholder_credentials correctly identifies unset or dummy keys."""
    # Placeholder key and secret
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_placeholder"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "placeholder_secret"):
        assert is_placeholder_credentials() is True

    # Empty key
    with patch.object(settings, "RAZORPAY_KEY_ID", ""), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "validsecret123"):
        assert is_placeholder_credentials() is True

    # Example template string
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_your_key_id_here"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "your_razorpay_test_secret_here"):
        assert is_placeholder_credentials() is True

    # Real-looking test key
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"):
        assert is_placeholder_credentials() is False

    # Malformed / truncated secret (e.g. 19 chars instead of 24)
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_Ttk2qrS9p9PqjC"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "DbqLzmBX7xZ4oV8ANCI"):
        assert is_placeholder_credentials() is True

    # Malformed / short key ID
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_short"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"):
        assert is_placeholder_credentials() is True


def test_missing_credentials_raises_runtime_error():
    """Verify create_provider_order refuses to run with placeholder credentials."""
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_placeholder"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "placeholder_secret"):
        with pytest.raises(RuntimeError) as exc_info:
            create_provider_order(amount_paise=25000, receipt="ORD-101")
        assert "Razorpay credentials are not configured" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Genuine Provider Order Creation (Mocked SDK Call)
# ─────────────────────────────────────────────────────────────────────────────

def test_genuine_provider_order_creation_calls_sdk():
    """Verify that when real test credentials are configured, the official SDK is called."""
    mock_order_response = {
        "id": "order_EKwxwAgIt4KiUm",
        "entity": "order",
        "amount": 45000,
        "amount_paid": 0,
        "amount_due": 45000,
        "currency": "INR",
        "receipt": "ORD-450",
        "status": "created",
        "notes": {"order_id": 12},
    }

    mock_client = MagicMock()
    mock_client.order.create.return_value = mock_order_response

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"), \
         patch("app.services.razorpay_service.get_razorpay_client", return_value=mock_client):

        result = create_provider_order(
            amount_paise=45000,
            currency="INR",
            receipt="ORD-450",
            notes={"order_id": 12},
        )

        mock_client.order.create.assert_called_once_with(
            data={
                "amount": 45000,
                "currency": "INR",
                "receipt": "ORD-450",
                "notes": {"order_id": 12},
                "payment_capture": 1,
            }
        )
        assert result["id"] == "order_EKwxwAgIt4KiUm"
        assert result["amount"] == 45000


def test_provider_api_failure_raises_runtime_error():
    """Verify provider network or API errors are isolated into descriptive RuntimeErrors."""
    mock_client = MagicMock()
    mock_client.order.create.side_effect = Exception("Razorpay API connection timed out")

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"), \
         patch("app.services.razorpay_service.get_razorpay_client", return_value=mock_client):

        with pytest.raises(RuntimeError) as exc_info:
            create_provider_order(amount_paise=30000, receipt="ORD-ERR")
        assert "Payment provider error" in str(exc_info.value)


def test_provider_auth_failure_raises_specific_runtime_error():
    """Verify provider authentication failure produces a clear credential check message."""
    mock_client = MagicMock()
    mock_client.order.create.side_effect = Exception("Authentication failed")

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"), \
         patch("app.services.razorpay_service.get_razorpay_client", return_value=mock_client):

        with pytest.raises(RuntimeError) as exc_info:
            create_provider_order(amount_paise=30000, receipt="ORD-AUTH-ERR")
        assert "Payment provider authentication failed" in str(exc_info.value)
        assert "Invalid Razorpay Key ID or Key Secret" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Signature Verification (HMAC SHA-256)
# ─────────────────────────────────────────────────────────────────────────────

def test_verify_payment_signature_valid():
    """Verify valid signature is confirmed using HMAC-SHA256."""
    secret = "w2bXkRzF8d9qL1sK4mP0vT7y"
    order_id = "order_EKwxwAgIt4KiUm"
    payment_id = "pay_G3bQxZ1k8LmN0v"
    message = f"{order_id}|{payment_id}"
    valid_sig = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    with patch.object(settings, "RAZORPAY_KEY_SECRET", secret):
        assert verify_payment_signature(order_id, payment_id, valid_sig) is True


def test_verify_payment_signature_tampered():
    """Verify fraudulent or tampered signatures are rejected."""
    secret = "w2bXkRzF8d9qL1sK4mP0vT7y"
    order_id = "order_EKwxwAgIt4KiUm"
    payment_id = "pay_G3bQxZ1k8LmN0v"
    tampered_sig = "0000000000000000000000000000000000000000000000000000000000000000"

    with patch.object(settings, "RAZORPAY_KEY_SECRET", secret):
        assert verify_payment_signature(order_id, payment_id, tampered_sig) is False


def test_verify_payment_signature_empty_fields():
    """Verify missing fields return False immediately."""
    assert verify_payment_signature("", "pay_123", "sig") is False
    assert verify_payment_signature("order_123", "", "sig") is False
    assert verify_payment_signature("order_123", "pay_123", "") is False


def test_verify_webhook_signature():
    """Verify webhook payload signature verification."""
    secret = "webhook_secret_xyz123"
    raw_body = b'{"event": "payment.captured", "id": "evt_123"}'
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    with patch.object(settings, "RAZORPAY_WEBHOOK_SECRET", secret):
        assert verify_webhook_signature(raw_body, valid_sig) is True
        assert verify_webhook_signature(raw_body, "tampered_signature") is False
        assert verify_webhook_signature(b"", valid_sig) is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Public Config & API Endpoints Logic
# ─────────────────────────────────────────────────────────────────────────────

def test_public_config_reports_unconfigured_when_placeholder():
    """Verify /api/public/payments/config reports razorpay_configured=False for placeholders."""
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_placeholder"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "placeholder_secret"):
        config = get_public_payment_config()
        assert config.razorpay_configured is False
        assert config.key_id == "rzp_test_placeholder"


def test_public_config_reports_configured_when_real_test_keys():
    """Verify /api/public/payments/config reports razorpay_configured=True for test credentials."""
    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"):
        config = get_public_payment_config()
        assert config.razorpay_configured is True
        assert config.key_id == "rzp_test_1DP5mmOlF5G5ag"


def test_create_guest_payment_order_unconfigured_credentials():
    """Verify create_guest_payment_order returns HTTP 503 if credentials are placeholders."""
    mock_db = MagicMock()
    payload = PaymentOrderCreateRequest(order_number="ORD-TEST-1")

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_placeholder"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "placeholder_secret"):
        with pytest.raises(HTTPException) as exc_info:
            create_guest_payment_order(payload, db=mock_db)
        assert exc_info.value.status_code == 503
        assert "not configured with valid test credentials" in exc_info.value.detail


def test_create_guest_payment_order_takeaway_allowed_without_qr_token():
    """Verify takeaway orders (table_id=None) do NOT require qr_token."""
    mock_db = MagicMock()
    order = Order(
        id=10,
        order_number="ORD-TAKEAWAY-1",
        table_id=None,  # Takeaway
        status="pending",
        payment_status="pending",
        total=Decimal("250.00"),
    )
    # Order query returns this takeaway order
    mock_db.query.return_value.filter.return_value.first.return_value = order
    # Existing payment check returns None
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    mock_client = MagicMock()
    mock_client.order.create.return_value = {"id": "order_TKWY12345678", "amount": 25000}

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"), \
         patch("app.services.razorpay_service.get_razorpay_client", return_value=mock_client):

        payload = PaymentOrderCreateRequest(order_number="ORD-TAKEAWAY-1", qr_token=None)
        res = create_guest_payment_order(payload, db=mock_db)

        assert res.order_number == "ORD-TAKEAWAY-1"
        assert res.amount_paise == 25000
        assert res.razorpay_order_id == "order_TKWY12345678"


def test_create_guest_payment_order_dine_in_requires_valid_qr_token():
    """Verify dine-in orders require a valid matching table QR token."""
    mock_db = MagicMock()
    order = Order(
        id=11,
        order_number="ORD-DINEIN-1",
        table_id=5,  # Dine-in at Table 5
        status="pending",
        payment_status="pending",
        total=Decimal("350.00"),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = order

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"):

        # 1. Missing QR token for dine-in order
        payload_no_token = PaymentOrderCreateRequest(order_number="ORD-DINEIN-1", qr_token=None)
        with pytest.raises(HTTPException) as exc1:
            create_guest_payment_order(payload_no_token, db=mock_db)
        assert exc1.value.status_code == 403

        # 2. Mismatched QR token
        mock_table = RestaurantTable(id=5, table_number="T5", qr_token="correct_token_123")
        # Second call to query (for RestaurantTable) returns mock_table
        def query_mock(model):
            q = MagicMock()
            if model == Order:
                q.filter.return_value.first.return_value = order
            elif model == RestaurantTable:
                q.filter.return_value.first.return_value = mock_table
            return q

        mock_db.query.side_effect = query_mock
        payload_wrong_token = PaymentOrderCreateRequest(order_number="ORD-DINEIN-1", qr_token="wrong_token_456")
        with pytest.raises(HTTPException) as exc2:
            create_guest_payment_order(payload_wrong_token, db=mock_db)
        assert exc2.value.status_code == 403


def test_create_guest_payment_order_already_paid_rejection():
    """Verify already paid orders reject payment creation with 409 Conflict."""
    mock_db = MagicMock()
    paid_order = Order(
        id=12,
        order_number="ORD-PAID-1",
        table_id=None,
        status="pending",
        payment_status="paid",  # Already paid
        total=Decimal("200.00"),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = paid_order

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"):

        payload = PaymentOrderCreateRequest(order_number="ORD-PAID-1")
        with pytest.raises(HTTPException) as exc:
            create_guest_payment_order(payload, db=mock_db)
        assert exc.value.status_code == 409
        assert "already been paid" in exc.value.detail


def test_payment_retry_idempotency():
    """Verify repeating a payment initiation request returns the existing provider order without duplicates."""
    mock_db = MagicMock()
    order = Order(
        id=14,
        order_number="ORD-RETRY-1",
        table_id=None,
        status="pending",
        payment_status="pending",
        total=Decimal("180.00"),
    )
    existing_created_payment = Payment(
        id=99,
        order_id=14,
        payment_reference="pay_ref_abc123",
        provider="razorpay",
        provider_order_id="order_EXISTING_RZP_ID",
        amount=Decimal("180.00"),
        amount_paise=18000,
        currency="INR",
        status="created",
    )

    def query_mock(model):
        q = MagicMock()
        if model == Order:
            q.filter.return_value.first.return_value = order
        elif model == Payment:
            q.filter.return_value.order_by.return_value.first.return_value = existing_created_payment
        return q

    mock_db.query.side_effect = query_mock

    # Mock SDK should NOT be called since existing payment is reused
    mock_client = MagicMock()

    with patch.object(settings, "RAZORPAY_KEY_ID", "rzp_test_1DP5mmOlF5G5ag"), \
         patch.object(settings, "RAZORPAY_KEY_SECRET", "w2bXkRzF8d9qL1sK4mP0vT7y"), \
         patch("app.services.razorpay_service.get_razorpay_client", return_value=mock_client):

        payload = PaymentOrderCreateRequest(order_number="ORD-RETRY-1")
        res = create_guest_payment_order(payload, db=mock_db)

        # Provider order creation must NOT be called again
        mock_client.order.create.assert_not_called()
        assert res.razorpay_order_id == "order_EXISTING_RZP_ID"
        assert res.amount_paise == 18000
        assert res.payment_reference == "pay_ref_abc123"


def test_settings_loads_razorpay_config():
    """Verify Settings class reads RAZORPAY_* variables correctly."""
    from app.core.config import Settings
    s = Settings(
        RAZORPAY_KEY_ID="rzp_test_custom_key_12345",
        RAZORPAY_KEY_SECRET="custom_secret_key_12345",
        RAZORPAY_CURRENCY="INR",
    )
    assert s.RAZORPAY_KEY_ID == "rzp_test_custom_key_12345"
    assert s.RAZORPAY_KEY_SECRET == "custom_secret_key_12345"
    assert s.RAZORPAY_CURRENCY == "INR"

