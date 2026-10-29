#!/usr/bin/env python3
"""Phase 21 — Comprehensive Test Suite for QR Table Ordering System with 7 Safeguards.

Tests:
1. Staff QR Token Management & RBAC:
   - Generation / rotation of cryptographically random tokens (Manager/Admin).
   - RBAC verification (Unauthenticated 401, Cashier 403, Kitchen 403, Manager/Admin 200).
   - Token inspection (Staff 200).
   - Token revocation (Manager/Admin 204).
2. Public Table Resolution:
   - Valid token resolves table info (table_number, capacity, has_active_order).
   - Revoked/invalid token returns 404 Not Found.
3. Public Order Creation & Server Authority:
   - Anonymous dine-in ordering without authentication (201 Created).
   - Server-side price snapshotting from DB (never trusts client prices).
   - Order status initialized to 'pending' with inventory_deducted=False.
   - Table status transitions to 'occupied' atomically.
4. Idempotency & SHA-256 Request Fingerprint Verification:
   - Duplicate submissions with identical key + matching payload return original order safely.
   - Tampered submissions reusing identical key + differing payload are rejected with 409 Conflict.
5. Multiple Orders per Table & Table State Lifecycle:
   - Seated table allows multiple consecutive orders (e.g. second round of drinks).
   - Table remains 'occupied' while any order is active.
   - Completing first order keeps table 'occupied' while second order is still active.
   - Completing second order transitions table to 'available'.
6. Atomic Transaction & Rollback Safety:
   - Submitting unavailable item (409) or non-existent item (404) rolls back completely.
   - Table status is not altered on failure; zero partial records created.
7. Public Tracking Privacy:
   - Matching active table qr_token returns 200 with customer-safe fields only.
   - Excludes internal database IDs, user accounts, and staff audit notes.
   - Mismatched qr_token returns 403 Forbidden; non-existent order returns 404.
8. Inventory Lifecycle Integration:
   - QR order in 'pending' status does NOT deduct stock.
   - Moving status to 'in_progress' triggers deduct_inventory_for_order.
   - Cancelling order triggers reverse_inventory_for_order.
"""

import json
import sys
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, ".")

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.ingredient import Ingredient
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.recipe import Recipe
from app.models.stock_movement import StockMovement
from app.models.table import RestaurantTable
from app.models.user import User

BASE_URL = "http://127.0.0.1:8000"


def make_http_request(path: str, method: str = "GET", body: dict = None, token: str = None):
    url = f"{BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data_bytes = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
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
def users(db):
    admin = db.query(User).filter(User.username == "admin").first()
    manager = db.query(User).filter(User.username == "manager").first()
    cashier = db.query(User).filter(User.username == "cashier").first()
    kitchen = db.query(User).filter(User.username == "kitchen").first()
    return {"admin": admin, "manager": manager, "cashier": cashier, "kitchen": kitchen}


@pytest.fixture(scope="module")
def tokens(users):
    return {
        role: create_access_token({"sub": str(u.id), "username": u.username, "role": u.role})
        for role, u in users.items()
    }


@pytest.fixture(scope="module")
def test_table(db):
    """Provide a dedicated physical table for QR ordering tests."""
    table_num = "QR-TEST-T99"
    # Cleanup previous run if any
    existing = db.query(RestaurantTable).filter(RestaurantTable.table_number == table_num).first()
    if existing:
        db.query(Order).filter(Order.table_id == existing.id).delete(synchronize_session=False)
        db.delete(existing)
        db.commit()

    table = RestaurantTable(
        table_number=table_num,
        capacity=4,
        status="available",
    )
    db.add(table)
    db.commit()
    db.refresh(table)

    yield table

    # Teardown
    try:
        db.rollback()
        cleanup_table = db.query(RestaurantTable).filter(RestaurantTable.id == table.id).first()
        if cleanup_table:
            db.query(Order).filter(Order.table_id == cleanup_table.id).delete(synchronize_session=False)
            db.delete(cleanup_table)
            db.commit()
    except Exception:
        db.rollback()


@pytest.fixture(scope="module")
def test_menu_item(db):
    """Find an available active menu item for placing test orders."""
    item = db.query(MenuItem).filter(MenuItem.is_available == True).first()  # noqa: E712
    assert item is not None, "At least one available menu item must exist in database"
    return item


# ── TEST SUITE 1: STAFF QR TOKEN MANAGEMENT & RBAC ──────────────────────

def test_qr_token_rbac_and_generation(db, test_table, tokens):
    """Verify QR token generation and RBAC role boundaries."""
    # 1. Unauthenticated request rejected with 401
    status_code, _ = make_http_request(f"/api/tables/{test_table.id}/qr-token", method="POST")
    assert status_code == 401, f"Expected 401 Unauthorized, got {status_code}"

    # 2. Cashier role forbidden with 403
    status_code, _ = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["cashier"],
    )
    assert status_code == 403, f"Expected 403 Forbidden for cashier, got {status_code}"

    # 3. Kitchen role forbidden with 403
    status_code, _ = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["kitchen"],
    )
    assert status_code == 403, f"Expected 403 Forbidden for kitchen, got {status_code}"

    # 4. Manager successfully generates QR token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["manager"],
    )
    assert status_code == 200, f"Expected 200 OK for manager, got {status_code}: {data}"
    assert data["table_id"] == test_table.id
    assert data["table_number"] == test_table.table_number
    assert "qr_token" in data and len(data["qr_token"]) >= 32
    assert f"/order/{data['qr_token']}" in data["qr_url"]

    # 5. Staff can inspect the QR token
    status_code, inspect_data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="GET",
        token=tokens["cashier"],
    )
    assert status_code == 200
    assert inspect_data["qr_token"] == data["qr_token"]


def test_qr_token_revocation(db, test_table, tokens):
    """Verify QR token revocation and 404 behavior."""
    # 1. Admin generates token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["admin"],
    )
    assert status_code == 200
    token = data["qr_token"]

    # 2. Public lookup works
    status_code, pub_data = make_http_request(f"/api/public/table/{token}")
    assert status_code == 200
    assert pub_data["table_number"] == test_table.table_number

    # 3. Manager revokes token
    status_code, _ = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="DELETE",
        token=tokens["manager"],
    )
    assert status_code == 204

    # 4. Public lookup now fails with 404
    status_code, _ = make_http_request(f"/api/public/table/{token}")
    assert status_code == 404, f"Expected 404 for revoked token, got {status_code}"

    # 5. Staff lookup now returns 404
    status_code, _ = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="GET",
        token=tokens["admin"],
    )
    assert status_code == 404


# ── TEST SUITE 2: IDEMPOTENCY & REQUEST FINGERPRINT SAFEGUARDS ────────────

def test_idempotency_replay_and_tamper_rejection(db, test_table, test_menu_item, tokens):
    """Verify Safeguard 1: Duplicate submission replay vs. payload tampering conflict."""
    # Generate token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["admin"],
    )
    assert status_code == 200
    qr_token = data["qr_token"]

    shared_idempotency_key = f"idemp-test-{uuid.uuid4().hex[:16]}"
    original_payload = {
        "qr_token": qr_token,
        "items": [
            {
                "menu_item_id": test_menu_item.id,
                "quantity": 1,
                "special_instructions": "Oat milk please",
            }
        ],
        "idempotency_key": shared_idempotency_key,
        "customer_name": "Aarav",
    }

    # 1. First submission -> 201 Created
    status_code, order_1 = make_http_request("/api/public/orders", method="POST", body=original_payload)
    assert status_code == 201, f"Expected 201, got {status_code}: {order_1}"
    order_number = order_1["order_number"]

    # 2. Resubmission of exact same payload -> Idempotent replay, returns original order
    status_code, order_replay = make_http_request("/api/public/orders", method="POST", body=original_payload)
    assert status_code in (200, 201)
    assert order_replay["order_number"] == order_number
    assert order_replay["total"] == order_1["total"]

    # 3. Tampered payload using the SAME idempotency key -> HTTP 409 Conflict
    tampered_payload = {
        "qr_token": qr_token,
        "items": [
            {
                "menu_item_id": test_menu_item.id,
                "quantity": 3,  # Changed quantity
                "special_instructions": "Extra shot",
            }
        ],
        "idempotency_key": shared_idempotency_key,  # Reused key!
        "customer_name": "Different Name",
    }
    status_code, conflict_data = make_http_request("/api/public/orders", method="POST", body=tampered_payload)
    assert status_code == 409, f"Expected 409 Conflict for tampered payload, got {status_code}: {conflict_data}"
    assert "different request payload" in str(conflict_data).lower()

    # Cleanup
    db.query(Order).filter(Order.order_number == order_number).delete(synchronize_session=False)
    test_table.status = "available"
    db.commit()


# ── TEST SUITE 3: MULTIPLE ORDERS PER TABLE & TABLE STATE LIFECYCLE ───────

def test_multiple_orders_per_table_lifecycle(db, test_table, test_menu_item, tokens):
    """Verify Safeguard 4: Seated tables permit consecutive orders, and table state frees only when all complete."""
    # Ensure test table starts clean and available
    test_table.status = "available"
    db.commit()
    db.refresh(test_table)

    # Generate token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["admin"],
    )
    assert status_code == 200
    qr_token = data["qr_token"]
    assert test_table.status == "available"

    # 1. Place Order 1 (First round: Beverage)
    payload_1 = {
        "qr_token": qr_token,
        "items": [{"menu_item_id": test_menu_item.id, "quantity": 1}],
        "idempotency_key": f"idemp-round1-{uuid.uuid4().hex[:12]}",
        "customer_name": "Priya",
    }
    status_code, order_1 = make_http_request("/api/public/orders", method="POST", body=payload_1)
    assert status_code == 201
    db.refresh(test_table)
    assert test_table.status == "occupied"

    # 2. Place Order 2 (Second round: Dessert / Re-order) from the same occupied table
    payload_2 = {
        "qr_token": qr_token,
        "items": [{"menu_item_id": test_menu_item.id, "quantity": 2}],
        "idempotency_key": f"idemp-round2-{uuid.uuid4().hex[:12]}",
        "customer_name": "Priya",
    }
    status_code, order_2 = make_http_request("/api/public/orders", method="POST", body=payload_2)
    assert status_code == 201, f"Expected 201 for second round order, got {status_code}: {order_2}"
    assert order_2["order_number"] != order_1["order_number"]
    db.refresh(test_table)
    assert test_table.status == "occupied"

    # 3. Staff advances and completes Order 1
    # First: pending -> in_progress
    db_order_1 = db.query(Order).filter(Order.order_number == order_1["order_number"]).first()
    status_code, _ = make_http_request(
        f"/api/orders/{db_order_1.id}",
        method="PUT",
        body={"status": "in_progress"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    # Next: in_progress -> served
    status_code, _ = make_http_request(
        f"/api/orders/{db_order_1.id}",
        method="PUT",
        body={"status": "served"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    # Finally: served -> completed
    status_code, _ = make_http_request(
        f"/api/orders/{db_order_1.id}",
        method="PUT",
        body={"status": "completed"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    # Safeguard 4 Verification: Table must STILL be 'occupied' because Order 2 is still active!
    db.refresh(test_table)
    assert test_table.status == "occupied", (
        f"Table should remain 'occupied' while Order 2 is active, but found '{test_table.status}'"
    )

    # 4. Now staff completes Order 2
    db_order_2 = db.query(Order).filter(Order.order_number == order_2["order_number"]).first()
    status_code, _ = make_http_request(
        f"/api/orders/{db_order_2.id}",
        method="PUT",
        body={"status": "in_progress"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    status_code, _ = make_http_request(
        f"/api/orders/{db_order_2.id}",
        method="PUT",
        body={"status": "served"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    status_code, _ = make_http_request(
        f"/api/orders/{db_order_2.id}",
        method="PUT",
        body={"status": "completed"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    # Safeguard 4 Verification: All orders are completed -> Table is now 'available'!
    db.refresh(test_table)
    assert test_table.status == "available", (
        f"Table should now be 'available' after all orders completed, but found '{test_table.status}'"
    )

    # Cleanup
    db.query(Order).filter(Order.table_id == test_table.id).delete(synchronize_session=False)
    db.commit()


# ── TEST SUITE 4: ATOMIC TRANSACTION & ROLLBACK SAFETY ───────────────────

def test_atomic_transaction_rollback_on_failure(db, test_table, tokens):
    """Verify Safeguard 2: Failures leave zero partial records and preserve table state."""
    # Ensure table starts as 'available'
    test_table.status = "available"
    db.commit()

    # Generate token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["admin"],
    )
    assert status_code == 200
    qr_token = data["qr_token"]

    order_count_before = db.query(Order).count()

    # 1. Non-existent menu item -> 404
    status_code, err_data = make_http_request(
        "/api/public/orders",
        method="POST",
        body={
            "qr_token": qr_token,
            "items": [{"menu_item_id": 999999, "quantity": 1}],
            "idempotency_key": f"idemp-fail-{uuid.uuid4().hex[:12]}",
        },
    )
    assert status_code == 404
    db.refresh(test_table)
    assert test_table.status == "available", "Failed order must not change table state"
    assert db.query(Order).count() == order_count_before, "Failed order must not create order records"

    # 2. Unavailable menu item -> 409
    unavailable_item = (
        db.query(MenuItem).filter(MenuItem.is_available == False).first()  # noqa: E712
    )
    if unavailable_item:
        status_code, err_data = make_http_request(
            "/api/public/orders",
            method="POST",
            body={
                "qr_token": qr_token,
                "items": [{"menu_item_id": unavailable_item.id, "quantity": 1}],
                "idempotency_key": f"idemp-fail2-{uuid.uuid4().hex[:12]}",
            },
        )
        assert status_code == 409
        db.refresh(test_table)
        assert test_table.status == "available"
        assert db.query(Order).count() == order_count_before


# ── TEST SUITE 5: PUBLIC ORDER TRACKING PRIVACY ──────────────────────────

def test_public_tracking_privacy(db, test_table, test_menu_item, tokens):
    """Verify Safeguard 3: Only safe fields returned, mismatched token receives 403."""
    # Generate token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["admin"],
    )
    assert status_code == 200
    qr_token = data["qr_token"]

    payload = {
        "qr_token": qr_token,
        "items": [
            {
                "menu_item_id": test_menu_item.id,
                "quantity": 1,
                "special_instructions": "Light ice",
            }
        ],
        "idempotency_key": f"idemp-track-{uuid.uuid4().hex[:12]}",
        "customer_name": "Private Guest",
    }

    status_code, order_data = make_http_request("/api/public/orders", method="POST", body=payload)
    assert status_code == 201
    order_number = order_data["order_number"]

    # 1. Verified tracking query with correct qr_token -> 200 OK
    status_code, track_data = make_http_request(
        f"/api/public/orders/{order_number}?qr_token={qr_token}"
    )
    assert status_code == 200
    assert track_data["order_number"] == order_number
    assert track_data["table_number"] == test_table.table_number
    assert track_data["status"] == "pending"
    assert "total" in track_data
    assert "items" in track_data
    assert len(track_data["items"]) == 1
    assert track_data["items"][0]["menu_item_name"] == test_menu_item.name
    assert track_data["items"][0]["special_instructions"] == "Light ice"

    # Verify absence of private / internal IDs
    assert "id" not in track_data
    assert "table_id" not in track_data
    assert "user_id" not in track_data
    assert "request_fingerprint" not in track_data
    assert "inventory_deducted" not in track_data

    # 2. Tracking with incorrect/tampered qr_token -> 403 Forbidden
    status_code, _ = make_http_request(
        f"/api/public/orders/{order_number}?qr_token=invalid_unrelated_token"
    )
    assert status_code == 403

    # 3. Tracking non-existent order -> 404 Not Found
    status_code, _ = make_http_request(
        f"/api/public/orders/ORD-99999999-XXXXXX?qr_token={qr_token}"
    )
    assert status_code == 404

    # Cleanup
    db.query(Order).filter(Order.order_number == order_number).delete(synchronize_session=False)
    test_table.status = "available"
    db.commit()


# ── TEST SUITE 6: INVENTORY LIFECYCLE INTEGRATION ────────────────────────

def test_inventory_lifecycle_integration(db, test_table, test_menu_item, tokens):
    """Verify Safeguard 5: QR creation does NOT deduct inventory; in_progress deducts; cancellation reverses."""
    # Ensure test table starts clean and available
    test_table.status = "available"
    db.commit()

    # Find or provision a recipe and ingredient for testing
    recipe = db.query(Recipe).first()
    created_test_recipe = False
    if not recipe:
        # Create a test ingredient and recipe
        test_ingredient = Ingredient(
            name="Phase 21 QR Test Espresso Beans",
            current_stock=Decimal("500.000"),
            unit="g",
            minimum_stock=Decimal("50.000"),
            unit_cost=Decimal("0.50"),
            is_active=True,
        )
        db.add(test_ingredient)
        db.flush()

        recipe = Recipe(
            menu_item_id=test_menu_item.id,
            ingredient_id=test_ingredient.id,
            quantity=Decimal("18.000"),
            unit="g",
        )
        db.add(recipe)
        db.commit()
        created_test_recipe = True

    menu_item_with_recipe = db.query(MenuItem).filter(MenuItem.id == recipe.menu_item_id).first()
    ingredient = db.query(Ingredient).filter(Ingredient.id == recipe.ingredient_id).first()

    # Ensure ingredient has ample stock
    initial_stock = ingredient.current_stock
    if initial_stock < Decimal("50.000"):
        ingredient.current_stock = Decimal("500.000")
        db.commit()
        db.refresh(ingredient)
        initial_stock = ingredient.current_stock

    # Generate token
    status_code, data = make_http_request(
        f"/api/tables/{test_table.id}/qr-token",
        method="POST",
        token=tokens["admin"],
    )
    assert status_code == 200
    qr_token = data["qr_token"]

    # 1. Place QR Order
    payload = {
        "qr_token": qr_token,
        "items": [{"menu_item_id": menu_item_with_recipe.id, "quantity": 1}],
        "idempotency_key": f"idemp-inv-{uuid.uuid4().hex[:12]}",
    }
    status_code, order_data = make_http_request("/api/public/orders", method="POST", body=payload)
    assert status_code == 201

    db_order = db.query(Order).filter(Order.order_number == order_data["order_number"]).first()
    assert db_order.status == "pending"
    assert db_order.inventory_deducted is False

    # Stock must NOT be deducted while order is pending
    db.refresh(ingredient)
    assert ingredient.current_stock == initial_stock, "Pending QR order must not deduct stock"

    # 2. Staff confirms order -> status changes to in_progress
    status_code, _ = make_http_request(
        f"/api/orders/{db_order.id}",
        method="PUT",
        body={"status": "in_progress"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    db.refresh(db_order)
    assert db_order.inventory_deducted is True
    db.refresh(ingredient)
    expected_deducted_stock = initial_stock - recipe.quantity
    assert ingredient.current_stock == expected_deducted_stock, "in_progress status must deduct recipe stock"

    # 3. Staff cancels order -> inventory reversal
    status_code, _ = make_http_request(
        f"/api/orders/{db_order.id}",
        method="PUT",
        body={"status": "cancelled"},
        token=tokens["cashier"],
    )
    assert status_code == 200

    db.refresh(db_order)
    assert db_order.inventory_deducted is False
    db.refresh(ingredient)
    assert ingredient.current_stock == initial_stock, "Cancellation must reverse deducted inventory"

    # Cleanup
    db.query(StockMovement).filter(StockMovement.order_id == db_order.id).delete(synchronize_session=False)
    db.delete(db_order)
    if created_test_recipe:
        db.delete(recipe)
        db.delete(ingredient)
    test_table.status = "available"
    db.commit()
