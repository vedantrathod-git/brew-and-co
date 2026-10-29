"""Comprehensive test suite for Restaurant Tables API.

Tests all CRUD operations, status codes, validations, duplicate conflicts,
foreign key protections (ON DELETE SET NULL for orders), and regressions.
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
    req_body = json.dumps(data).encode("utf-8") if data else None

    req = urllib.request.Request(url, data=req_body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            body_bytes = response.read()
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
            return status_code, body
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        body_bytes = exc.read()
        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
        except Exception:
            body = body_bytes.decode("utf-8")
        return status_code, body


def run_tests():
    print("=" * 70)
    print(" Restaurant Tables API - Comprehensive Verification Test Suite")
    print("=" * 70)

    # ── Step 1: Regression check ─────────────────────────────────────────
    print("\n[Step 1] Regression Check: Root, Health, and Existing APIs...")
    s, b = make_request("GET", "/")
    assert s == 200 and b["status"] == "online"
    print("  ✓ GET / returned 200 OK")

    s, b = make_request("GET", "/health")
    assert s == 200 and b["status"] == "healthy"
    print("  ✓ GET /health returned 200 OK")

    s, b = make_request("GET", "/health/db")
    assert s == 200 and b["status"] == "healthy" and b["result"] == 1
    print("  ✓ GET /health/db returned 200 OK (PostgreSQL connected)")

    s, b = make_request("GET", "/api/categories")
    assert s == 200 and isinstance(b, list)
    print(f"  ✓ GET /api/categories returned 200 OK ({len(b)} categories)")

    s, b = make_request("GET", "/api/menu-items")
    assert s == 200 and isinstance(b, list)
    print(f"  ✓ GET /api/menu-items returned 200 OK ({len(b)} menu items)")

    # ── Step 2: POST /api/tables (Create) ────────────────────────────────
    print("\n[Step 2] Testing POST /api/tables (Create Table)...")
    payload1 = {
        "table_number": "Phase3_T1",
        "capacity": 4,
        "status": "available",
    }
    s, b = make_request("POST", "/api/tables", payload1)
    assert s == 201, f"Expected 201, got {s}: {b}"
    assert b["table_number"] == "Phase3_T1"
    assert b["capacity"] == 4
    assert b["status"] == "available"
    assert "id" in b and "created_at" in b and "updated_at" in b
    t1_id = b["id"]
    print(f"  ✓ POST /api/tables returned 201 Created (ID: {t1_id})")

    # Create with reserved status
    payload2 = {
        "table_number": "Phase3_T2",
        "capacity": 6,
        "status": "reserved",
    }
    s, b = make_request("POST", "/api/tables", payload2)
    assert s == 201
    t2_id = b["id"]
    assert b["status"] == "reserved"
    print(f"  ✓ Created second table with status 'reserved' (ID: {t2_id})")

    # Create with default capacity and status
    payload3 = {"table_number": "Phase3_T3"}
    s, b = make_request("POST", "/api/tables", payload3)
    assert s == 201
    t3_id = b["id"]
    assert b["capacity"] == 4
    assert b["status"] == "available"
    print(f"  ✓ Created table with defaults (ID: {t3_id}, capacity=4, status=available)")

    # ── Step 3: Duplicate table number (409) ─────────────────────────────
    print("\n[Step 3] Testing Duplicate Table Number (409 Conflict)...")
    s, b = make_request("POST", "/api/tables", {"table_number": "Phase3_T1"})
    assert s == 409, f"Expected 409 for duplicate, got {s}: {b}"
    print(f"  ✓ Exact duplicate returned 409 Conflict: {b.get('detail')}")

    # Case-insensitive duplicate
    s, b = make_request("POST", "/api/tables", {"table_number": "phase3_t1"})
    assert s == 409, f"Expected 409 for case-insensitive dup, got {s}: {b}"
    print("  ✓ Case-insensitive duplicate returned 409 Conflict")

    # ── Step 4: Validation errors (422) ──────────────────────────────────
    print("\n[Step 4] Testing Validation Errors (422 Unprocessable Entity)...")

    # Blank table number
    s, b = make_request("POST", "/api/tables", {"table_number": "   "})
    assert s == 422, f"Expected 422 for blank table_number, got {s}: {b}"
    print("  ✓ Blank table_number returned 422")

    # Overlong table number (> 20 chars)
    s, b = make_request("POST", "/api/tables", {"table_number": "T" * 21})
    assert s == 422, f"Expected 422 for overlong table_number, got {s}: {b}"
    print("  ✓ Overlong table_number (>20 chars) returned 422")

    # Invalid capacity: 0
    s, b = make_request("POST", "/api/tables", {"table_number": "Temp", "capacity": 0})
    assert s == 422, f"Expected 422 for capacity=0, got {s}: {b}"
    print("  ✓ capacity=0 returned 422")

    # Invalid capacity: negative
    s, b = make_request("POST", "/api/tables", {"table_number": "Temp", "capacity": -3})
    assert s == 422, f"Expected 422 for capacity=-3, got {s}: {b}"
    print("  ✓ Negative capacity returned 422")

    # Invalid status value
    s, b = make_request("POST", "/api/tables", {"table_number": "Temp", "status": "dirty"})
    assert s == 422, f"Expected 422 for invalid status, got {s}: {b}"
    print("  ✓ Invalid status 'dirty' returned 422")

    # ── Step 5: GET /api/tables (List & Filter) ──────────────────────────
    print("\n[Step 5] Testing GET /api/tables (List & Filter)...")
    s, b = make_request("GET", "/api/tables")
    assert s == 200 and isinstance(b, list)
    ids_found = {t["id"] for t in b}
    assert t1_id in ids_found and t2_id in ids_found
    print(f"  ✓ GET /api/tables returned 200 OK ({len(b)} tables)")

    # Filter by status=reserved
    s, b = make_request("GET", "/api/tables?status=reserved")
    assert s == 200 and all(t["status"] == "reserved" for t in b)
    print(f"  ✓ GET /api/tables?status=reserved filtered accurately ({len(b)} tables)")

    # ── Step 6: GET /api/tables/{id} ─────────────────────────────────────
    print("\n[Step 6] Testing GET /api/tables/{id}...")
    s, b = make_request("GET", f"/api/tables/{t1_id}")
    assert s == 200 and b["id"] == t1_id
    print(f"  ✓ GET /api/tables/{t1_id} returned 200 OK")

    s, b = make_request("GET", "/api/tables/999999")
    assert s == 404, f"Expected 404, got {s}: {b}"
    print(f"  ✓ Missing ID returned 404 Not Found: {b.get('detail')}")

    # ── Step 7: PUT /api/tables/{id} (Update) ────────────────────────────
    print("\n[Step 7] Testing PUT /api/tables/{id} (Update)...")
    update_payload = {
        "table_number": "Phase3_T1_Renamed",
        "capacity": 8,
        "status": "occupied",
    }
    s, b = make_request("PUT", f"/api/tables/{t1_id}", update_payload)
    assert s == 200, f"Expected 200, got {s}: {b}"
    assert b["table_number"] == "Phase3_T1_Renamed"
    assert b["capacity"] == 8
    assert b["status"] == "occupied"
    print(f"  ✓ PUT /api/tables/{t1_id} returned 200 OK (updated number, capacity, status)")

    # Update non-existent table
    s, b = make_request("PUT", "/api/tables/999999", update_payload)
    assert s == 404
    print("  ✓ Non-existent table on PUT returned 404")

    # Name collision on PUT
    s, b = make_request("PUT", f"/api/tables/{t2_id}", {"table_number": "Phase3_T1_Renamed", "capacity": 6, "status": "reserved"})
    assert s == 409, f"Expected 409 for name collision on PUT, got {s}: {b}"
    print(f"  ✓ Name collision on PUT returned 409 Conflict: {b.get('detail')}")

    # ── Step 8: DELETE occupied table (409 Conflict) ─────────────────────
    print("\n[Step 8] Testing DELETE of Occupied Table (409 Conflict)...")
    s, b = make_request("DELETE", f"/api/tables/{t1_id}")
    assert s == 409, f"Expected 409 for occupied table deletion, got {s}: {b}"
    print(f"  ✓ Occupied table deletion returned 409 Conflict: {b.get('detail')}")

    # Reset table to available for further tests
    s, b = make_request("PUT", f"/api/tables/{t1_id}", {"table_number": "Phase3_T1_Renamed", "capacity": 8, "status": "available"})
    assert s == 200
    print(f"  ✓ Reset table status to 'available'")

    # ── Step 9: DELETE table with active order (409 Conflict) ────────────
    print("\n[Step 9] Testing DELETE with Active Orders (409 Conflict)...")
    # Create a test category + menu item + order referencing t1_id
    db = SessionLocal()
    test_cat_id = None
    test_item_id = None
    test_order_id = None
    try:
        cat = Category(name="Phase3_TableTest_Cat", description="Test category")
        db.add(cat)
        db.commit()
        db.refresh(cat)
        test_cat_id = cat.id

        item = MenuItem(category_id=test_cat_id, name="Phase3_TableTest_Dish", price=Decimal("10.00"))
        db.add(item)
        db.commit()
        db.refresh(item)
        test_item_id = item.id

        order = Order(
            order_number="ORD-TABLE-TEST-ACTIVE",
            table_id=t1_id,
            status="in_progress",
            subtotal=Decimal("10.00"),
            tax=Decimal("0.83"),
            total=Decimal("10.83"),
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        test_order_id = order.id

        oi = OrderItem(order_id=test_order_id, menu_item_id=test_item_id, quantity=1, unit_price=Decimal("10.00"))
        db.add(oi)
        db.commit()
        print(f"  ✓ Created active order '{order.order_number}' (ID: {test_order_id}) at table {t1_id}")
    finally:
        db.close()

    # Attempt to delete table with active in_progress order
    s, b = make_request("DELETE", f"/api/tables/{t1_id}")
    assert s == 409, f"Expected 409 for table with active orders, got {s}: {b}"
    print(f"  ✓ Active order guard returned 409 Conflict: {b.get('detail')}")

    # ── Step 10: DELETE table with completed order (SET NULL behavior) ───
    print("\n[Step 10] Testing DELETE with Completed Order (ON DELETE SET NULL)...")
    # Complete the order so it is no longer active
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == test_order_id).first()
        order.status = "completed"
        db.commit()
        db.refresh(order)
        print(f"  ✓ Marked order '{order.order_number}' as 'completed'")
    finally:
        db.close()

    # Now deletion should succeed: PostgreSQL SET NULL will detach orders.table_id
    s, b = make_request("DELETE", f"/api/tables/{t1_id}")
    assert s == 204, f"Expected 204 after completing order, got {s}: {b}"
    assert b is None
    print(f"  ✓ DELETE /api/tables/{t1_id} returned 204 No Content")

    # Verify the completed order still exists with table_id = NULL
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == test_order_id).first()
        assert order is not None, "Order must NOT be deleted!"
        assert order.table_id is None, f"Expected table_id=None after SET NULL, got {order.table_id}"
        print(f"  ✓ Order '{order.order_number}' preserved with table_id=NULL (historical data intact)")

        # Verify order items also still exist
        oi_count = db.query(OrderItem).filter(OrderItem.order_id == test_order_id).count()
        assert oi_count > 0, "Order items must NOT be deleted!"
        print(f"  ✓ Order items still intact ({oi_count} item(s) preserved)")
    finally:
        db.close()

    # ── Step 11: Clean up test data ──────────────────────────────────────
    print("\n[Step 11] Cleaning Up Test Data...")
    db = SessionLocal()
    try:
        # Delete order items, order, menu item, category
        db.query(OrderItem).filter(OrderItem.order_id == test_order_id).delete()
        db.query(Order).filter(Order.id == test_order_id).delete()
        db.query(MenuItem).filter(MenuItem.id == test_item_id).delete()
        db.query(Category).filter(Category.id == test_cat_id).delete()
        db.commit()
        print("  ✓ Cleaned up test order, order items, menu item, and category")
    finally:
        db.close()

    # Delete remaining test tables via API
    s, b = make_request("DELETE", f"/api/tables/{t2_id}")
    assert s == 204
    s, b = make_request("DELETE", f"/api/tables/{t3_id}")
    assert s == 204
    print("  ✓ Deleted remaining test tables via API")

    # Verify: deleting already-deleted table returns 404
    s, b = make_request("DELETE", f"/api/tables/{t1_id}")
    assert s == 404
    print(f"  ✓ Already-deleted table returned 404 Not Found")

    # ── Step 12: Final regression check ──────────────────────────────────
    print("\n[Step 12] Final Regression Check...")
    s, b = make_request("GET", "/")
    assert s == 200
    s, b = make_request("GET", "/health")
    assert s == 200
    s, b = make_request("GET", "/health/db")
    assert s == 200 and b["result"] == 1
    s, b = make_request("GET", "/api/categories")
    assert s == 200
    s, b = make_request("GET", "/api/menu-items")
    assert s == 200
    s, b = make_request("GET", "/api/tables")
    assert s == 200
    print("  ✓ All endpoints healthy after tests")

    # Verify DB is clean
    db = SessionLocal()
    try:
        tc = db.query(RestaurantTable).filter(RestaurantTable.table_number.like("Phase3_%")).count()
        assert tc == 0, f"Test tables not cleaned up: {tc} remaining"
        print("  ✓ No test table artifacts remaining in database")
    finally:
        db.close()

    print("\n" + "=" * 70)
    print(" ALL RESTAURANT TABLES API TESTS PASSED SUCCESSFULLY! ")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
