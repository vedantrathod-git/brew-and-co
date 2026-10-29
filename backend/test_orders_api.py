"""Comprehensive test suite for the Orders API.

Tests creation, listing, retrieval, updates, deletion, price snapshots,
transaction safety, table occupancy rules, and regressions for all existing APIs.
"""
import json
import urllib.error
import urllib.request
from decimal import Decimal

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.menu_item import MenuItem
from app.models.order import Order, OrderItem
from app.models.table import RestaurantTable

BASE_URL = "http://127.0.0.1:8000"
ADMIN_TOKEN = create_access_token({"sub": "1", "username": "admin", "role": "admin"})


def make_request(method: str, path: str, data: dict = None):
    url = f"{BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    if data:
        headers["Content-Type"] = "application/json"
    body_raw = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body_raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            code = resp.getcode()
            raw = resp.read()
            return code, json.loads(raw.decode()) if raw else None
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read()
        try:
            return code, json.loads(raw.decode()) if raw else None
        except Exception:
            return code, raw.decode()


# ─────────────────────────────────────────────────────────────────────────
def run_tests():
    print("=" * 70)
    print(" Orders API - Comprehensive Verification Test Suite")
    print("=" * 70)

    # ── Step 1: Regression & health ─────────────────────────────────────
    print("\n[Step 1] Regression Check: Health & Existing APIs...")
    for ep in ["/", "/health", "/health/db"]:
        s, b = make_request("GET", ep)
        assert s == 200, f"FAIL {ep}: {s}"
    print("  ✓ GET /, /health, /health/db all 200 OK")

    for ep in ["/api/categories", "/api/menu-items", "/api/tables"]:
        s, b = make_request("GET", ep)
        assert s == 200 and isinstance(b, list)
    print("  ✓ GET /api/categories, /api/menu-items, /api/tables all 200 OK")

    # ── Step 2: Setup test fixtures ─────────────────────────────────────
    print("\n[Step 2] Creating Test Fixtures (Category, Menu Items, Tables)...")
    s, cat = make_request("POST", "/api/categories", {"name": "OrdTest_Cat", "description": "Test"})
    assert s == 201
    cat_id = cat["id"]

    s, item1 = make_request("POST", "/api/menu-items", {
        "category_id": cat_id, "name": "OrdTest_Burger", "price": 12.50,
        "is_available": True, "prep_time_minutes": 15,
    })
    assert s == 201
    item1_id = item1["id"]

    s, item2 = make_request("POST", "/api/menu-items", {
        "category_id": cat_id, "name": "OrdTest_Salad", "price": 8.00,
        "is_available": True,
    })
    assert s == 201
    item2_id = item2["id"]

    s, item_unavail = make_request("POST", "/api/menu-items", {
        "category_id": cat_id, "name": "OrdTest_OutOfStock", "price": 20.00,
        "is_available": False,
    })
    assert s == 201
    item_unavail_id = item_unavail["id"]

    s, tbl1 = make_request("POST", "/api/tables", {"table_number": "OrdTest_T1", "capacity": 4})
    assert s == 201
    tbl1_id = tbl1["id"]

    s, tbl2 = make_request("POST", "/api/tables", {"table_number": "OrdTest_T2", "capacity": 2})
    assert s == 201
    tbl2_id = tbl2["id"]
    print(f"  ✓ Created: Cat {cat_id}, Items [{item1_id},{item2_id},{item_unavail_id}], Tables [{tbl1_id},{tbl2_id}]")

    # ── Step 3: Create dine-in order with multiple items ────────────────
    print("\n[Step 3] POST /api/orders — Valid Dine-In Order (Multiple Items)...")
    order_payload = {
        "table_id": tbl1_id,
        "items": [
            {"menu_item_id": item1_id, "quantity": 2, "special_instructions": "No pickles"},
            {"menu_item_id": item2_id, "quantity": 1},
        ],
        "discount": 0.00,
    }
    s, ord1 = make_request("POST", "/api/orders", order_payload)
    assert s == 201, f"Expected 201, got {s}: {ord1}"
    ord1_id = ord1["id"]
    assert ord1["status"] == "pending"
    assert ord1["table_id"] == tbl1_id
    assert ord1["table_number"] == "OrdTest_T1"
    assert len(ord1["items"]) == 2
    # Verify server-side price calculation: 2*12.50 + 1*8.00 = 33.00
    expected_subtotal = Decimal("33.00")
    assert Decimal(str(ord1["subtotal"])) == expected_subtotal
    assert Decimal(str(ord1["tax"])) == Decimal("0.00")  # Default 0% tax
    assert Decimal(str(ord1["total"])) == expected_subtotal
    assert ord1["order_number"].startswith("ORD-")
    # Verify price snapshots
    burger_items = [i for i in ord1["items"] if i["menu_item_id"] == item1_id]
    assert len(burger_items) == 1
    assert Decimal(str(burger_items[0]["unit_price"])) == Decimal("12.50")
    assert burger_items[0]["special_instructions"] == "No pickles"
    assert burger_items[0]["menu_item_name"] == "OrdTest_Burger"
    print(f"  ✓ Created dine-in order {ord1['order_number']} (ID: {ord1_id})")
    print(f"    subtotal={ord1['subtotal']}, tax={ord1['tax']}, total={ord1['total']}")

    # Verify table is marked occupied
    s, tbl_check = make_request("GET", f"/api/tables/{tbl1_id}")
    assert tbl_check["status"] == "occupied"
    print(f"  ✓ Table OrdTest_T1 automatically marked 'occupied'")

    # ── Step 4: Create takeaway order (no table) ────────────────────────
    print("\n[Step 4] POST /api/orders — Takeaway Order (No Table)...")
    takeaway = {
        "items": [{"menu_item_id": item1_id, "quantity": 1}],
    }
    s, ord2 = make_request("POST", "/api/orders", takeaway)
    assert s == 201
    ord2_id = ord2["id"]
    assert ord2["table_id"] is None
    assert ord2["table_number"] is None
    assert Decimal(str(ord2["subtotal"])) == Decimal("12.50")
    print(f"  ✓ Created takeaway order {ord2['order_number']} (ID: {ord2_id}), table_id=null")

    # ── Step 5: Price snapshot independence ─────────────────────────────
    print("\n[Step 5] Verifying Price Snapshot Independence...")
    # Change the burger price
    s, _ = make_request("PUT", f"/api/menu-items/{item1_id}", {
        "category_id": cat_id, "name": "OrdTest_Burger", "price": 99.99,
        "is_available": True,
    })
    assert s == 200
    print(f"  ✓ Changed OrdTest_Burger price to 99.99")

    # Re-fetch original order — stored unit_price must still be 12.50
    s, ord1_refetched = make_request("GET", f"/api/orders/{ord1_id}")
    assert s == 200
    burger_snap = [i for i in ord1_refetched["items"] if i["menu_item_id"] == item1_id]
    assert Decimal(str(burger_snap[0]["unit_price"])) == Decimal("12.50")
    print(f"  ✓ Historical order item unit_price still 12.50 (menu now 99.99)")

    # Restore price for subsequent tests
    s, _ = make_request("PUT", f"/api/menu-items/{item1_id}", {
        "category_id": cat_id, "name": "OrdTest_Burger", "price": 12.50,
        "is_available": True,
    })
    assert s == 200

    # ── Step 6: Validation errors ───────────────────────────────────────
    print("\n[Step 6] Testing Validation Errors...")

    # No items
    s, b = make_request("POST", "/api/orders", {"items": []})
    assert s == 422
    print("  ✓ Empty items list → 422")

    # Missing menu item
    s, b = make_request("POST", "/api/orders", {"items": [{"menu_item_id": 999999, "quantity": 1}]})
    assert s == 404
    print(f"  ✓ Non-existent menu_item_id → 404: {b.get('detail')}")

    # Invalid table
    s, b = make_request("POST", "/api/orders", {"table_id": 999999, "items": [{"menu_item_id": item1_id, "quantity": 1}]})
    assert s == 404
    print(f"  ✓ Non-existent table_id → 404: {b.get('detail')}")

    # Unavailable dish
    s, b = make_request("POST", "/api/orders", {"items": [{"menu_item_id": item_unavail_id, "quantity": 1}]})
    assert s == 409
    print(f"  ✓ Unavailable menu item → 409: {b.get('detail')}")

    # Invalid quantity (0)
    s, b = make_request("POST", "/api/orders", {"items": [{"menu_item_id": item1_id, "quantity": 0}]})
    assert s == 422
    print("  ✓ quantity=0 → 422")

    # Negative discount
    s, b = make_request("POST", "/api/orders", {
        "items": [{"menu_item_id": item1_id, "quantity": 1}],
        "discount": -5.00,
    })
    assert s == 422
    print("  ✓ Negative discount → 422")

    # Discount > subtotal+tax
    s, b = make_request("POST", "/api/orders", {
        "items": [{"menu_item_id": item2_id, "quantity": 1}],
        "discount": 100.00,
    })
    assert s == 422
    print(f"  ✓ Excessive discount → 422: {b.get('detail')}")

    # ── Step 7: Conflicting table (already has active order) ────────────
    print("\n[Step 7] Testing Table Conflict (Active Order at Table)...")
    s, b = make_request("POST", "/api/orders", {
        "table_id": tbl1_id,
        "items": [{"menu_item_id": item2_id, "quantity": 1}],
    })
    assert s == 409
    print(f"  ✓ Second order at occupied table → 409: {b.get('detail')}")

    # ── Step 8: List & retrieve orders ──────────────────────────────────
    print("\n[Step 8] Testing GET /api/orders (List & Filters)...")
    s, b = make_request("GET", "/api/orders")
    assert s == 200
    order_ids = {o["id"] for o in b}
    assert ord1_id in order_ids and ord2_id in order_ids
    print(f"  ✓ GET /api/orders → 200 OK ({len(b)} orders)")

    # Filter by status
    s, b = make_request("GET", "/api/orders?status=pending")
    assert s == 200 and all(o["status"] == "pending" for o in b)
    print(f"  ✓ GET /api/orders?status=pending filtered ({len(b)} orders)")

    # Filter by table_id
    s, b = make_request("GET", f"/api/orders?table_id={tbl1_id}")
    assert s == 200 and all(o["table_id"] == tbl1_id for o in b)
    print(f"  ✓ GET /api/orders?table_id={tbl1_id} filtered ({len(b)} orders)")

    # Single order retrieval
    s, b = make_request("GET", f"/api/orders/{ord1_id}")
    assert s == 200 and b["id"] == ord1_id
    print(f"  ✓ GET /api/orders/{ord1_id} → 200 OK")

    s, b = make_request("GET", "/api/orders/999999")
    assert s == 404
    print(f"  ✓ Missing order → 404")

    # ── Step 9: Update order — status transitions ───────────────────────
    print("\n[Step 9] Testing PUT /api/orders/{id} — Status Updates...")

    # pending → in_progress
    s, b = make_request("PUT", f"/api/orders/{ord1_id}", {"status": "in_progress"})
    assert s == 200 and b["status"] == "in_progress"
    assert b["completed_at"] is None
    print(f"  ✓ pending → in_progress: OK, completed_at=null")

    # in_progress → served
    s, b = make_request("PUT", f"/api/orders/{ord1_id}", {"status": "served"})
    assert s == 200 and b["status"] == "served"
    print(f"  ✓ in_progress → served: OK")

    # served → completed (should set completed_at, free table)
    s, b = make_request("PUT", f"/api/orders/{ord1_id}", {"status": "completed"})
    assert s == 200 and b["status"] == "completed"
    assert b["completed_at"] is not None
    print(f"  ✓ served → completed: OK, completed_at={b['completed_at']}")

    # Verify table freed
    s, tbl_check = make_request("GET", f"/api/tables/{tbl1_id}")
    assert tbl_check["status"] == "available"
    print(f"  ✓ Table OrdTest_T1 freed to 'available' after completion")

    # Cannot modify completed order
    s, b = make_request("PUT", f"/api/orders/{ord1_id}", {"status": "pending"})
    assert s == 409
    print(f"  ✓ Modifying completed order → 409: {b.get('detail')}")

    # ── Step 10: Update order — discount adjustment ─────────────────────
    print("\n[Step 10] Testing PUT — Discount Adjustment...")
    # Use takeaway order (still pending)
    s, b = make_request("PUT", f"/api/orders/{ord2_id}", {"discount": 2.50})
    assert s == 200
    assert Decimal(str(b["discount"])) == Decimal("2.50")
    assert Decimal(str(b["total"])) == Decimal("10.00")  # 12.50 - 2.50
    print(f"  ✓ Discount updated to 2.50, total = {b['total']}")

    # Excessive discount on update
    s, b = make_request("PUT", f"/api/orders/{ord2_id}", {"discount": 999.00})
    assert s == 422
    print(f"  ✓ Excessive discount on PUT → 422: {b.get('detail')}")

    # ── Step 11: Update order — table reassignment ──────────────────────
    print("\n[Step 11] Testing PUT — Table Reassignment...")
    s, b = make_request("PUT", f"/api/orders/{ord2_id}", {"table_id": tbl2_id})
    assert s == 200 and b["table_id"] == tbl2_id
    assert b["table_number"] == "OrdTest_T2"
    print(f"  ✓ Takeaway order reassigned to table OrdTest_T2")

    s, tbl_check = make_request("GET", f"/api/tables/{tbl2_id}")
    assert tbl_check["status"] == "occupied"
    print(f"  ✓ Table OrdTest_T2 marked 'occupied'")

    # ── Step 12: Cancel order (frees table, sets completed_at) ──────────
    print("\n[Step 12] Testing Cancellation...")
    s, b = make_request("PUT", f"/api/orders/{ord2_id}", {"status": "cancelled"})
    assert s == 200 and b["status"] == "cancelled"
    assert b["completed_at"] is not None
    print(f"  ✓ Order cancelled: completed_at set")

    s, tbl_check = make_request("GET", f"/api/tables/{tbl2_id}")
    assert tbl_check["status"] == "available"
    print(f"  ✓ Table OrdTest_T2 freed after cancellation")

    # Cannot modify cancelled order
    s, b = make_request("PUT", f"/api/orders/{ord2_id}", {"status": "pending"})
    assert s == 409
    print(f"  ✓ Modifying cancelled order → 409")

    # ── Step 13: DELETE — only pending orders ───────────────────────────
    print("\n[Step 13] Testing DELETE /api/orders...")

    # Cannot delete completed order
    s, b = make_request("DELETE", f"/api/orders/{ord1_id}")
    assert s == 409
    print(f"  ✓ Deleting completed order → 409: {b.get('detail')}")

    # Cannot delete cancelled order
    s, b = make_request("DELETE", f"/api/orders/{ord2_id}")
    assert s == 409
    print(f"  ✓ Deleting cancelled order → 409")

    # Create a pending order to test successful deletion
    s, ord3 = make_request("POST", "/api/orders", {
        "table_id": tbl1_id,
        "items": [{"menu_item_id": item2_id, "quantity": 1}],
    })
    assert s == 201
    ord3_id = ord3["id"]
    print(f"  ✓ Created pending order for deletion test (ID: {ord3_id})")

    # Table should be occupied
    s, tbl_check = make_request("GET", f"/api/tables/{tbl1_id}")
    assert tbl_check["status"] == "occupied"

    # Delete pending order
    s, b = make_request("DELETE", f"/api/orders/{ord3_id}")
    assert s == 204 and b is None
    print(f"  ✓ DELETE pending order → 204 No Content (empty body)")

    # Table freed
    s, tbl_check = make_request("GET", f"/api/tables/{tbl1_id}")
    assert tbl_check["status"] == "available"
    print(f"  ✓ Table freed after pending order deletion")

    # Verify order is gone
    s, b = make_request("GET", f"/api/orders/{ord3_id}")
    assert s == 404
    print(f"  ✓ Deleted order confirmed gone (404)")

    # Verify order items cascade-deleted
    db = SessionLocal()
    try:
        oi_count = db.query(OrderItem).filter(OrderItem.order_id == ord3_id).count()
        assert oi_count == 0, f"Order items not cascade-deleted: {oi_count}"
        print(f"  ✓ Order items cascade-deleted with order")
    finally:
        db.close()

    # Delete non-existent
    s, b = make_request("DELETE", "/api/orders/999999")
    assert s == 404
    print(f"  ✓ Deleting non-existent order → 404")

    # ── Step 14: Transaction rollback on failure ────────────────────────
    print("\n[Step 14] Testing Transaction Rollback...")
    db = SessionLocal()
    orders_before = db.query(Order).count()
    items_before = db.query(OrderItem).count()
    db.close()

    # Attempt to create order with one valid item + one invalid (non-existent) item
    s, b = make_request("POST", "/api/orders", {
        "items": [
            {"menu_item_id": item1_id, "quantity": 1},
            {"menu_item_id": 999999, "quantity": 1},
        ],
    })
    assert s == 404

    db = SessionLocal()
    orders_after = db.query(Order).count()
    items_after = db.query(OrderItem).count()
    db.close()
    assert orders_before == orders_after, "Partial order leaked into DB!"
    assert items_before == items_after, "Partial items leaked into DB!"
    print(f"  ✓ Failed creation left no partial records (orders: {orders_after}, items: {items_after})")

    # ── Step 15: Cleanup ────────────────────────────────────────────────
    print("\n[Step 15] Cleaning Up...")
    db = SessionLocal()
    try:
        # Delete order items for remaining orders
        for oid in [ord1_id, ord2_id]:
            db.query(OrderItem).filter(OrderItem.order_id == oid).delete()
        # Delete remaining orders
        db.query(Order).filter(Order.id.in_([ord1_id, ord2_id])).delete()
        db.commit()
        print(f"  ✓ Cleaned up test orders and order items")
    finally:
        db.close()

    # Delete test fixtures via API
    for iid in [item1_id, item2_id, item_unavail_id]:
        s, _ = make_request("DELETE", f"/api/menu-items/{iid}")
        assert s == 204
    s, _ = make_request("DELETE", f"/api/categories/{cat_id}")
    assert s == 204
    for tid in [tbl1_id, tbl2_id]:
        s, _ = make_request("DELETE", f"/api/tables/{tid}")
        assert s == 204
    print(f"  ✓ Cleaned up test menu items, category, and tables")

    # Verify clean DB
    db = SessionLocal()
    try:
        assert db.query(Order).filter(Order.order_number.like("ORD-%")).filter(Order.id.in_([ord1_id, ord2_id, ord3_id])).count() == 0
        assert db.query(RestaurantTable).filter(RestaurantTable.table_number.like("OrdTest_%")).count() == 0
        assert db.query(MenuItem).filter(MenuItem.name.like("OrdTest_%")).count() == 0
        assert db.query(Category).filter(Category.name.like("OrdTest_%")).count() == 0
        print("  ✓ No test artifacts remaining in database")
    finally:
        db.close()

    # ── Step 16: Final regression ───────────────────────────────────────
    print("\n[Step 16] Final Regression Check...")
    for ep in ["/", "/health", "/health/db", "/api/categories", "/api/menu-items", "/api/tables", "/api/orders"]:
        s, _ = make_request("GET", ep)
        assert s == 200
    print("  ✓ All endpoints healthy after tests")

    print("\n" + "=" * 70)
    print(" ALL ORDERS API TESTS PASSED SUCCESSFULLY! ")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
