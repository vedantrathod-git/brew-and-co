"""Comprehensive test suite for Menu Items API using standard urllib.

Tests all CRUD operations, status codes, validations, duplicate conflicts,
category references, foreign key protections, and regressions against PostgreSQL.
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
    print(" Menu Items API - Comprehensive Verification Test Suite")
    print("=" * 70)

    # 1. Regression check: Health and database endpoints
    print("\n[Step 1] Regression Check: Root and Health Endpoints...")
    s, b = make_request("GET", "/")
    assert s == 200 and b["status"] == "online"
    print("  ✓ GET / returned 200 OK")

    s, b = make_request("GET", "/health")
    assert s == 200 and b["status"] == "healthy"
    print("  ✓ GET /health returned 200 OK")

    s, b = make_request("GET", "/health/db")
    assert s == 200 and b["status"] == "healthy" and b["result"] == 1
    print("  ✓ GET /health/db returned 200 OK (PostgreSQL connected)")

    # 2. Regression check: Categories API
    print("\n[Step 2] Regression Check: Categories API & Test Category Setup...")
    s, b = make_request("GET", "/api/categories")
    assert s == 200 and isinstance(b, list)
    print(f"  ✓ GET /api/categories returned 200 OK ({len(b)} existing categories)")

    # Create primary test category
    cat_payload = {
        "name": "Phase3_MenuTest_Mains",
        "description": "Main courses for testing menu items",
    }
    s, b = make_request("POST", "/api/categories", cat_payload)
    assert s == 201, f"Expected 201, got {s}: {b}"
    cat1_id = b["id"]
    print(f"  ✓ Created primary test category '{b['name']}' (ID: {cat1_id})")

    # Create secondary test category for category reassignment test
    cat_alt_payload = {
        "name": "Phase3_MenuTest_Specials",
        "description": "Chef specials category",
    }
    s, b = make_request("POST", "/api/categories", cat_alt_payload)
    assert s == 201, f"Expected 201, got {s}: {b}"
    cat2_id = b["id"]
    print(f"  ✓ Created secondary test category '{b['name']}' (ID: {cat2_id})")

    # 3. Test POST /api/menu-items (Valid creation)
    print("\n[Step 3] Testing POST /api/menu-items (Create Menu Item)...")
    item_payload = {
        "category_id": cat1_id,
        "name": "Phase3_Classic_Burger",
        "description": "Premium Angus beef patty with cheddar cheese",
        "price": 14.50,
        "is_available": True,
        "prep_time_minutes": 18,
    }
    s, b = make_request("POST", "/api/menu-items", item_payload)
    assert s == 201, f"Expected 201, got {s}: {b}"
    assert b["name"] == "Phase3_Classic_Burger"
    assert b["category_id"] == cat1_id
    assert b["category_name"] == "Phase3_MenuTest_Mains"
    assert float(b["price"]) == 14.50
    assert b["is_available"] is True
    assert b["prep_time_minutes"] == 18
    assert "id" in b and "created_at" in b and "updated_at" in b
    item1_id = b["id"]
    print(f"  ✓ POST /api/menu-items returned 201 Created (ID: {item1_id}, category_name: '{b['category_name']}')")

    # 4. Test Invalid or Missing Category ID (404 Not Found)
    print("\n[Step 4] Testing Invalid Category Reference...")
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": 999999, "name": "Phase3_Ghost_Dish", "price": 9.99},
    )
    assert s == 404, f"Expected 404 for invalid category_id, got {s}: {b}"
    print(f"  ✓ Invalid category_id returned 404 Not Found: {b.get('detail')}")

    # 5. Test Duplicate Menu Item Name (409 Conflict)
    print("\n[Step 5] Testing Duplicate Name Conflict (409 Conflict)...")
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "Phase3_Classic_Burger", "price": 15.00},
    )
    assert s == 409, f"Expected 409 for duplicate name, got {s}: {b}"
    print(f"  ✓ Exact duplicate name returned 409 Conflict: {b.get('detail')}")

    # Case-insensitive duplicate check
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "phase3_classic_burger", "price": 15.00},
    )
    assert s == 409, f"Expected 409 for case-insensitive duplicate, got {s}: {b}"
    print("  ✓ Case-insensitive duplicate name returned 409 Conflict")

    # 6. Test Validation Errors (422 Unprocessable Entity)
    print("\n[Step 6] Testing Validation Errors (422 Unprocessable Entity)...")
    # Negative price
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "Negative_Price_Dish", "price": -5.50},
    )
    assert s == 422, f"Expected 422 for negative price, got {s}: {b}"
    print("  ✓ Negative price returned 422 Unprocessable Entity")

    # Negative prep_time_minutes
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "Negative_Prep_Dish", "price": 10.00, "prep_time_minutes": -15},
    )
    assert s == 422, f"Expected 422 for negative prep_time, got {s}: {b}"
    print("  ✓ Negative prep_time_minutes returned 422 Unprocessable Entity")

    # Blank name
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "   ", "price": 10.00},
    )
    assert s == 422, f"Expected 422 for blank name, got {s}: {b}"
    print("  ✓ Blank name returned 422 Unprocessable Entity")

    # Overlong name (> 100 chars)
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "N" * 101, "price": 10.00},
    )
    assert s == 422, f"Expected 422 for name > 100 chars, got {s}: {b}"
    print("  ✓ Overlong name (>100 chars) returned 422 Unprocessable Entity")

    # 7. Test GET /api/menu-items (List and Query Filters)
    print("\n[Step 7] Testing GET /api/menu-items (List & Filters)...")
    s, b = make_request("GET", "/api/menu-items")
    assert s == 200 and isinstance(b, list)
    matching = [item for item in b if item["id"] == item1_id]
    assert len(matching) == 1
    print(f"  ✓ GET /api/menu-items returned 200 OK (Found {len(b)} total items)")

    # Filter by category_id
    s, b = make_request("GET", f"/api/menu-items?category_id={cat1_id}")
    assert s == 200 and all(item["category_id"] == cat1_id for item in b)
    print(f"  ✓ GET /api/menu-items?category_id={cat1_id} filtered accurately ({len(b)} items)")

    # Filter by availability
    s, b = make_request("GET", "/api/menu-items?is_available=true")
    assert s == 200 and all(item["is_available"] is True for item in b)
    print(f"  ✓ GET /api/menu-items?is_available=true filtered accurately ({len(b)} items)")

    # 8. Test GET /api/menu-items/{id}
    print("\n[Step 8] Testing GET /api/menu-items/{id}...")
    s, b = make_request("GET", f"/api/menu-items/{item1_id}")
    assert s == 200 and b["id"] == item1_id and b["category_name"] == "Phase3_MenuTest_Mains"
    print(f"  ✓ GET /api/menu-items/{item1_id} returned 200 OK with category_name")

    s, b = make_request("GET", "/api/menu-items/999999")
    assert s == 404, f"Expected 404 for missing item, got {s}: {b}"
    print(f"  ✓ Missing item returned 404 Not Found: {b.get('detail')}")

    # 9. Test PUT /api/menu-items/{id} (Update)
    print("\n[Step 9] Testing PUT /api/menu-items/{id} (Update)...")
    update_payload = {
        "category_id": cat2_id,
        "name": "Phase3_Classic_Burger_Deluxe",
        "description": "Double beef patty with truffle aioli",
        "price": 18.95,
        "is_available": False,
        "prep_time_minutes": 22,
    }
    s, b = make_request("PUT", f"/api/menu-items/{item1_id}", update_payload)
    assert s == 200, f"Expected 200 on update, got {s}: {b}"
    assert b["name"] == "Phase3_Classic_Burger_Deluxe"
    assert b["category_id"] == cat2_id
    assert b["category_name"] == "Phase3_MenuTest_Specials"
    assert float(b["price"]) == 18.95
    assert b["is_available"] is False
    assert b["prep_time_minutes"] == 22
    print(f"  ✓ PUT /api/menu-items/{item1_id} returned 200 OK (Updated category, price, and availability)")

    # Update with non-existent category
    s, b = make_request(
        "PUT",
        f"/api/menu-items/{item1_id}",
        {**update_payload, "category_id": 999999},
    )
    assert s == 404, f"Expected 404 for non-existent category on PUT, got {s}: {b}"
    print("  ✓ Non-existent category_id on PUT returned 404 Not Found")

    # Create a second item for name collision on PUT
    s, b = make_request(
        "POST",
        "/api/menu-items",
        {"category_id": cat1_id, "name": "Phase3_Woodfired_Pizza", "price": 16.00},
    )
    assert s == 201
    item2_id = b["id"]
    print(f"  ✓ Created second menu item ID: {item2_id} ('Phase3_Woodfired_Pizza')")

    # Try updating item 1 to have item 2's name (409 Conflict)
    s, b = make_request(
        "PUT",
        f"/api/menu-items/{item1_id}",
        {**update_payload, "name": "Phase3_Woodfired_Pizza"},
    )
    assert s == 409, f"Expected 409 for name collision on PUT, got {s}: {b}"
    print(f"  ✓ Name collision on PUT returned 409 Conflict: {b.get('detail')}")

    # 10. Test Deletion Behavior when Referenced by an OrderItem (409 Conflict)
    print("\n[Step 10] Testing Foreign Key Restriction on DELETE...")
    db = SessionLocal()
    order_id = None
    order_item_id = None
    try:
        # Create a test order session
        test_order = Order(
            order_number="ORD-TEST-PHASE3-ITEM",
            status="pending",
            subtotal=Decimal("18.95"),
            tax=Decimal("1.56"),
            discount=Decimal("0.00"),
            total=Decimal("20.51"),
        )
        db.add(test_order)
        db.commit()
        db.refresh(test_order)
        order_id = test_order.id

        # Create an order line item referencing item1_id
        test_oi = OrderItem(
            order_id=order_id,
            menu_item_id=item1_id,
            quantity=1,
            unit_price=Decimal("18.95"),
            special_instructions="No pickles",
        )
        db.add(test_oi)
        db.commit()
        db.refresh(test_oi)
        order_item_id = test_oi.id
        print(f"  ✓ Created test order '{test_order.order_number}' (ID: {order_id}) with OrderItem (ID: {order_item_id}) referencing Menu Item {item1_id}")
    finally:
        db.close()

    # Attempt to delete menu item while referenced by OrderItem
    s, b = make_request("DELETE", f"/api/menu-items/{item1_id}")
    assert s == 409, f"Expected 409 Conflict due to historical order reference, got {s}: {b}"
    print(f"  ✓ Historical order integrity enforced! Returned 409 Conflict: {b.get('detail')}")

    # Clean up test order item and test order
    db = SessionLocal()
    try:
        oi = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
        if oi:
            db.delete(oi)
        ord_rec = db.query(Order).filter(Order.id == order_id).first()
        if ord_rec:
            db.delete(ord_rec)
        db.commit()
        print(f"  ✓ Safely cleaned up test order and line item records")
    finally:
        db.close()

    # 11. Test DELETE /api/menu-items/{id} (Successful Deletion - 204 No Content)
    print("\n[Step 11] Testing DELETE /api/menu-items/{id} (Permitted Deletion)...")
    s, b = make_request("DELETE", f"/api/menu-items/{item1_id}")
    assert s == 204, f"Expected 204 No Content, got {s}: {b}"
    assert b is None, "204 response body must be empty"
    print(f"  ✓ DELETE /api/menu-items/{item1_id} returned 204 No Content (Empty body)")

    # Verify item is gone
    s, b = make_request("GET", f"/api/menu-items/{item1_id}")
    assert s == 404
    print(f"  ✓ GET on deleted menu item returned 404 Not Found")

    # Delete second test item
    s, b = make_request("DELETE", f"/api/menu-items/{item2_id}")
    assert s == 204
    print(f"  ✓ DELETE /api/menu-items/{item2_id} returned 204 No Content")

    # Deleting already-deleted item
    s, b = make_request("DELETE", f"/api/menu-items/{item1_id}")
    assert s == 404
    print(f"  ✓ Deleting already-deleted item returned 404 Not Found")

    # 12. Cleanup test categories
    print("\n[Step 12] Cleaning Up Test Categories...")
    s, b = make_request("DELETE", f"/api/categories/{cat1_id}")
    assert s == 204
    s, b = make_request("DELETE", f"/api/categories/{cat2_id}")
    assert s == 204
    print("  ✓ Cleaned up test categories successfully")

    print("\n" + "=" * 70)
    print(" ALL MENU ITEMS API TESTS PASSED SUCCESSFULLY! ")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
