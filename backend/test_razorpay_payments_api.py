#!/usr/bin/env python3
"""Phase 22 — Comprehensive Test Suite for Razorpay Sandbox Payment Integration.

Tests:
1. Public payment configuration endpoint.
2. Payment order creation with server-side authoritative amounts in paise.
3. Cross-table and unauthorized order scope protection (403 Forbidden).
4. Signature verification success and order association (HMAC SHA-256).
5. Signature verification failure and rejection on tampered signatures (400 Bad Request).
6. Rejection of payment initiation for already paid or completed orders (409 Conflict).
7. Webhook signature verification, capture, and idempotency protection against duplicate deliveries.
8. Webhook out-of-order safety: never downgrading a captured payment to failed.
9. Staff POS cash settlement and counter billing workflow.
10. Inventory lifecycle boundary: payments never prematurely consume stock.
"""

import hashlib
import hmac
import json
import secrets
import sys
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
import pytest

# Ensure backend directory is in python path
sys.path.insert(0, ".")

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem
from app.models.payment import Payment, ProcessedWebhookEvent
from app.models.table import RestaurantTable
from app.models.user import User

BASE_URL = "http://127.0.0.1:8000"


def make_http_request(
    path: str,
    method: str = "GET",
    body: dict = None,
    raw_body: bytes = None,
    headers: dict = None,
    token: str = None,
):
    url = f"{BASE_URL}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if token:
        req_headers["Authorization"] = f"Bearer {token}"

    data_bytes = None
    if raw_body is not None:
        data_bytes = raw_body
    elif body is not None:
        req_headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw and "application/json" in resp.headers.get("content-type", "") else None
            return status_code, data
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw
        return e.code, data


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def staff_tokens(db):
    cashier = db.query(User).filter(User.username == "cashier").first()
    manager = db.query(User).filter(User.username == "manager").first()
    return {
        "cashier": create_access_token({"sub": str(cashier.id), "username": cashier.username, "role": cashier.role}),
        "manager": create_access_token({"sub": str(manager.id), "username": manager.username, "role": manager.role}),
    }


@pytest.fixture(scope="module")
def test_setup(db):
    """Setup an active dining table with a known QR token and available menu item."""
    table = db.query(RestaurantTable).filter(RestaurantTable.table_number == "T-PAY-1").first()
    if not table:
        table = RestaurantTable(
            table_number="T-PAY-1",
            capacity=4,
            status="available",
            qr_token=secrets.token_urlsafe(32),
        )
        db.add(table)
        db.commit()
        db.refresh(table)
    else:
        table.status = "available"
        if not table.qr_token:
            table.qr_token = secrets.token_urlsafe(32)
        db.commit()

    menu_item = db.query(MenuItem).filter(MenuItem.is_available == True).first()
    assert menu_item is not None, "Need at least one active menu item"

    return {"table": table, "menu_item": menu_item}


def create_test_order(db, table, menu_item, total_decimal=Decimal("250.00")):
    """Helper to provision a fresh dine-in order in DB."""
    order_num = f"PAY-{secrets.token_hex(4).upper()}"
    order = Order(
        order_number=order_num,
        table_id=table.id,
        status="pending",
        payment_status="pending",
        subtotal=total_decimal,
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=total_decimal,
        inventory_deducted=False,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        menu_item_id=menu_item.id,
        quantity=1,
        unit_price=total_decimal,
    )
    db.add(item)
    db.commit()
    db.refresh(order)
    return order


# ─────────────────────────────────────────────────────────────────────────────
# 1. Configuration & Public Parameters
# ─────────────────────────────────────────────────────────────────────────────

def test_public_payment_config():
    """Verify frontend can retrieve public key ID and currency without authentication."""
    code, data = make_http_request("/api/public/payments/config")
    assert code == 200
    assert "key_id" in data
    assert data["currency"] == "INR"
    assert data["key_id"] == settings.RAZORPAY_KEY_ID


# ─────────────────────────────────────────────────────────────────────────────
# 2. Payment Order Creation & Server Authority
# ─────────────────────────────────────────────────────────────────────────────

def test_create_payment_order_authoritative_amount(db, test_setup):
    """Verify backend derives paise amount strictly from authoritative DB order."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("380.00"))

    payload = {
        "order_number": order.order_number,
        "qr_token": table.qr_token,
        "idempotency_key": str(uuid.uuid4()),
    }
    code, data = make_http_request("/api/public/payments/create-order", method="POST", body=payload)
    assert code == 200
    assert data["order_number"] == order.order_number
    assert data["amount_paise"] == 38000  # 380.00 * 100
    assert Decimal(str(data["amount"])) == Decimal("380.00")
    assert data["currency"] == "INR"
    assert data["razorpay_order_id"].startswith("order_")
    assert data["payment_reference"].startswith("pay_ref_")

    # Verify durable DB record created
    db_payment = db.query(Payment).filter(Payment.payment_reference == data["payment_reference"]).first()
    assert db_payment is not None
    assert db_payment.status == "created"
    assert db_payment.order_id == order.id
    assert db_payment.amount_paise == 38000


def test_payment_order_cross_table_and_invalid_scope_rejection(db, test_setup):
    """Verify unauthorized or mismatched QR tokens are rejected with 403 Forbidden."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("150.00"))

    # Case 1: Wrong QR token
    payload_bad_token = {
        "order_number": order.order_number,
        "qr_token": "wrong_mismatched_token_xyz",
    }
    code1, _ = make_http_request("/api/public/payments/create-order", method="POST", body=payload_bad_token)
    assert code1 == 403

    # Case 2: Missing QR token for dine-in order
    payload_no_token = {
        "order_number": order.order_number,
        "qr_token": None,
    }
    code2, _ = make_http_request("/api/public/payments/create-order", method="POST", body=payload_no_token)
    assert code2 == 403

    # Case 3: Non-existent order
    payload_missing_order = {
        "order_number": "NON_EXISTENT_ORDER_999",
        "qr_token": table.qr_token,
    }
    code3, _ = make_http_request("/api/public/payments/create-order", method="POST", body=payload_missing_order)
    assert code3 == 404


# ─────────────────────────────────────────────────────────────────────────────
# 3. Signature Verification & Order Settlement
# ─────────────────────────────────────────────────────────────────────────────

def test_signature_verification_success_and_order_settlement(db, test_setup):
    """Verify official HMAC SHA-256 signature confirms payment and marks order paid."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("450.00"))

    # 1. Create payment order
    create_payload = {
        "order_number": order.order_number,
        "qr_token": table.qr_token,
    }
    code, order_res = make_http_request("/api/public/payments/create-order", method="POST", body=create_payload)
    assert code == 200
    rzp_order_id = order_res["razorpay_order_id"]
    rzp_payment_id = f"pay_{secrets.token_hex(8)}"

    # 2. Compute valid signature using official formula: HMAC-SHA256(order_id + "|" + payment_id, secret)
    message = f"{rzp_order_id}|{rzp_payment_id}"
    secret = settings.RAZORPAY_KEY_SECRET or ""
    valid_sig = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    # 3. Submit verification request
    verify_payload = {
        "order_number": order.order_number,
        "qr_token": table.qr_token,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": rzp_payment_id,
        "razorpay_signature": valid_sig,
    }
    v_code, v_data = make_http_request("/api/public/payments/verify", method="POST", body=verify_payload)
    assert v_code == 200
    assert v_data["success"] is True
    assert v_data["payment_status"] == "paid"

    # 4. Check DB status
    db.refresh(order)
    assert order.payment_status == "paid"
    assert order.payment_method == "razorpay"

    payment = db.query(Payment).filter(Payment.provider_order_id == rzp_order_id).first()
    assert payment.status == "captured"
    assert payment.provider_payment_id == rzp_payment_id
    assert payment.verified_at is not None


def test_signature_verification_failure_tampered_payload(db, test_setup):
    """Verify fraudulent or tampered signatures are rejected and payment marked failed."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("300.00"))

    # 1. Create payment order
    create_payload = {
        "order_number": order.order_number,
        "qr_token": table.qr_token,
    }
    code, order_res = make_http_request("/api/public/payments/create-order", method="POST", body=create_payload)
    assert code == 200
    rzp_order_id = order_res["razorpay_order_id"]
    rzp_payment_id = f"pay_{secrets.token_hex(8)}"

    # 2. Forge invalid signature
    tampered_sig = "tampered_bogus_signature_abc123"

    # 3. Submit verification request
    verify_payload = {
        "order_number": order.order_number,
        "qr_token": table.qr_token,
        "razorpay_order_id": rzp_order_id,
        "razorpay_payment_id": rzp_payment_id,
        "razorpay_signature": tampered_sig,
    }
    v_code, v_data = make_http_request("/api/public/payments/verify", method="POST", body=verify_payload)
    assert v_code == 400

    # 4. Check DB status: order NOT paid, payment marked failed
    db.refresh(order)
    assert order.payment_status == "pending"

    payment = db.query(Payment).filter(Payment.provider_order_id == rzp_order_id).first()
    assert payment.status == "failed"
    assert payment.error_code == "BAD_SIGNATURE"


def test_prevent_payment_for_already_paid_or_completed_order(db, test_setup):
    """Verify already-paid orders reject subsequent payment initiation with 409 Conflict."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("200.00"))
    order.payment_status = "paid"
    order.payment_method = "razorpay"
    db.commit()

    payload = {
        "order_number": order.order_number,
        "qr_token": table.qr_token,
    }
    code, _ = make_http_request("/api/public/payments/create-order", method="POST", body=payload)
    assert code == 409


# ─────────────────────────────────────────────────────────────────────────────
# 4. Webhook Signature Verification & Idempotency
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_signature_verification_and_idempotency(db, test_setup):
    """Verify webhook captures payment, checks signature against raw body, and handles retries idempotently."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("500.00"))

    # Create associated payment record in DB
    rzp_order_id = f"order_{secrets.token_hex(8)}"
    rzp_payment_id = f"pay_{secrets.token_hex(8)}"
    payment = Payment(
        order_id=order.id,
        payment_reference=f"pay_ref_{secrets.token_hex(6)}",
        provider="razorpay",
        provider_order_id=rzp_order_id,
        amount=order.total,
        amount_paise=50000,
        currency="INR",
        status="created",
    )
    db.add(payment)
    db.commit()

    # Construct webhook event
    event_id = f"evt_{secrets.token_hex(8)}"
    event_payload = {
        "entity": "event",
        "account_id": "acc_123",
        "event": "payment.captured",
        "id": event_id,
        "payload": {
            "payment": {
                "entity": {
                    "id": rzp_payment_id,
                    "order_id": rzp_order_id,
                    "amount": 50000,
                    "currency": "INR",
                    "status": "captured",
                    "method": "upi",
                }
            }
        },
    }
    raw_body = json.dumps(event_payload).encode("utf-8")

    # Compute webhook signature: HMAC-SHA256(raw_body, webhook_secret)
    secret = settings.RAZORPAY_WEBHOOK_SECRET or ""
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    # 1. Invalid signature rejection
    bad_headers = {"X-Razorpay-Signature": "invalid_sig_xyz", "Content-Type": "application/json"}
    code_bad, _ = make_http_request("/api/payments/webhook", method="POST", raw_body=raw_body, headers=bad_headers)
    assert code_bad == 400

    # 2. First delivery: Valid signature processed successfully
    good_headers = {"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"}
    code1, data1 = make_http_request("/api/payments/webhook", method="POST", raw_body=raw_body, headers=good_headers)
    assert code1 == 200
    assert data1["status"] == "processed"

    # Verify DB update
    db.refresh(order)
    db.refresh(payment)
    assert order.payment_status == "paid"
    assert payment.status == "captured"
    assert payment.method == "upi"

    # 3. Duplicate delivery (retry): Returns 200 without duplicate execution
    code2, data2 = make_http_request("/api/payments/webhook", method="POST", raw_body=raw_body, headers=good_headers)
    assert code2 == 200
    assert data2["status"] == "already_processed"


def test_webhook_out_of_order_preservation(db, test_setup):
    """Verify a captured payment is never downgraded by an out-of-order payment.failed webhook."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("600.00"))
    order.payment_status = "paid"

    rzp_order_id = f"order_{secrets.token_hex(8)}"
    rzp_payment_id = f"pay_{secrets.token_hex(8)}"
    payment = Payment(
        order_id=order.id,
        payment_reference=f"pay_ref_{secrets.token_hex(6)}",
        provider="razorpay",
        provider_order_id=rzp_order_id,
        provider_payment_id=rzp_payment_id,
        amount=order.total,
        amount_paise=60000,
        currency="INR",
        status="captured",
    )
    db.add(payment)
    db.commit()

    # Delayed payment.failed webhook event
    event_id = f"evt_{secrets.token_hex(8)}"
    event_payload = {
        "entity": "event",
        "event": "payment.failed",
        "id": event_id,
        "payload": {
            "payment": {
                "entity": {
                    "id": rzp_payment_id,
                    "order_id": rzp_order_id,
                    "error_code": "GATEWAY_TIMEOUT",
                    "error_description": "Network timeout occurred",
                }
            }
        },
    }
    raw_body = json.dumps(event_payload).encode("utf-8")
    secret = settings.RAZORPAY_WEBHOOK_SECRET or ""
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    headers = {"X-Razorpay-Signature": valid_sig, "Content-Type": "application/json"}
    code, _ = make_http_request("/api/payments/webhook", method="POST", raw_body=raw_body, headers=headers)
    assert code == 200

    # Ensure status was NOT downgraded to failed
    db.refresh(payment)
    assert payment.status == "captured"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Staff POS Cash Settlement & Billing
# ─────────────────────────────────────────────────────────────────────────────

def test_staff_pos_cash_settlement(db, test_setup, staff_tokens):
    """Verify cashier can settle order with cash at POS counter."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("220.00"))

    # Cashier marks order settled with cash
    code, data = make_http_request(
        f"/api/orders/{order.id}/settle-cash",
        method="POST",
        token=staff_tokens["cashier"],
    )
    assert code == 200
    assert data["payment_status"] == "paid"
    assert data["payment_method"] == "cash"

    db.refresh(order)
    assert order.payment_status == "paid"
    assert order.payment_method == "cash"

    # Cannot re-settle already paid order
    code2, _ = make_http_request(
        f"/api/orders/{order.id}/settle-cash",
        method="POST",
        token=staff_tokens["cashier"],
    )
    assert code2 == 409


# ─────────────────────────────────────────────────────────────────────────────
# 6. Inventory Lifecycle Regression Guard
# ─────────────────────────────────────────────────────────────────────────────

def test_inventory_lifecycle_preserved_during_payment(db, test_setup):
    """Verify payment creation or settlement does NOT trigger premature inventory deduction."""
    table = test_setup["table"]
    item = test_setup["menu_item"]
    order = create_test_order(db, table, item, total_decimal=Decimal("350.00"))

    # Initial state
    assert order.inventory_deducted is False

    # 1. Create Razorpay order
    payload = {"order_number": order.order_number, "qr_token": table.qr_token}
    code, _ = make_http_request("/api/public/payments/create-order", method="POST", body=payload)
    assert code == 200
    db.refresh(order)
    assert order.inventory_deducted is False

    # 2. Mark paid
    order.payment_status = "paid"
    order.payment_method = "razorpay"
    db.commit()
    db.refresh(order)
    assert order.inventory_deducted is False
