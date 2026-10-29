"""Comprehensive test suite for Categories API using standard urllib.

Tests all CRUD operations, status codes, validations, duplicate conflicts,
and foreign key restriction protections against the live PostgreSQL database.
"""
import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.menu_item import MenuItem

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
    print("=" * 65)
    print(" Categories API - Comprehensive Verification Test Suite")
    print("=" * 65)

    # 1. Verify existing health endpoints
    print("\n[Step 1] Verifying Root and Health Endpoints...")
    s, b = make_request("GET", "/")
    assert s == 200 and b["status"] == "online", f"Failed /: {s}, {b}"
    print("  ✓ GET / returned 200 OK")

    s, b = make_request("GET", "/health")
    assert s == 200 and b["status"] == "healthy", f"Failed /health: {s}, {b}"
    print("  ✓ GET /health returned 200 OK")

    s, b = make_request("GET", "/health/db")
    assert s == 200 and b["status"] == "healthy" and b["result"] == 1, f"Failed /health/db: {s}, {b}"
    print("  ✓ GET /health/db returned 200 OK (PostgreSQL connected)")

    # 2. Test POST /api/categories (Valid creation)
    print("\n[Step 2] Testing POST /api/categories (Create Category)...")
    payload1 = {
        "name": "Phase3_Test_Starters",
        "description": "Crispy starters and appetizers",
    }
    s, b = make_request("POST", "/api/categories", payload1)
    assert s == 201, f"Expected 201, got {s}: {b}"
    assert b["name"] == "Phase3_Test_Starters"
    assert b["description"] == "Crispy starters and appetizers"
    assert "id" in b and "created_at" in b and "updated_at" in b
    cat1_id = b["id"]
    print(f"  ✓ POST /api/categories returned 201 Created (ID: {cat1_id})")

    # 3. Test POST /api/categories with Duplicate Name (409 Conflict)
    print("\n[Step 3] Testing POST /api/categories with Duplicate Name...")
    s, b = make_request("POST", "/api/categories", {"name": "Phase3_Test_Starters"})
    assert s == 409, f"Expected 409 for duplicate name, got {s}: {b}"
    print(f"  ✓ Duplicate name check returned 409 Conflict: {b.get('detail')}")

    # Case-insensitive duplicate check
    s, b = make_request("POST", "/api/categories", {"name": "phase3_test_starters"})
    assert s == 409, f"Expected 409 for case-insensitive duplicate, got {s}: {b}"
    print("  ✓ Case-insensitive duplicate check returned 409 Conflict")

    # 4. Test Validation Errors on POST (422 Unprocessable Entity)
    print("\n[Step 4] Testing Validation Errors (422 Unprocessable Entity)...")
    # Empty name
    s, b = make_request("POST", "/api/categories", {"name": "   "})
    assert s == 422, f"Expected 422 for blank name, got {s}: {b}"
    print("  ✓ Blank name returned 422 Unprocessable Entity")

    # Name too long (> 50 chars)
    s, b = make_request("POST", "/api/categories", {"name": "X" * 51})
    assert s == 422, f"Expected 422 for name > 50 chars, got {s}: {b}"
    print("  ✓ Overlong name (>50 chars) returned 422 Unprocessable Entity")

    # Description too long (> 255 chars)
    s, b = make_request("POST", "/api/categories", {"name": "ValidName", "description": "D" * 256})
    assert s == 422, f"Expected 422 for description > 255 chars, got {s}: {b}"
    print("  ✓ Overlong description (>255 chars) returned 422 Unprocessable Entity")

    # 5. Test GET /api/categories (List all)
    print("\n[Step 5] Testing GET /api/categories (List all)...")
    s, b = make_request("GET", "/api/categories")
    assert s == 200, f"Expected 200, got {s}: {b}"
    assert isinstance(b, list)
    matching = [c for c in b if c["id"] == cat1_id]
    assert len(matching) == 1
    print(f"  ✓ GET /api/categories returned 200 OK (Found {len(b)} categories, including created ID {cat1_id})")

    # 6. Test GET /api/categories/{id}
    print("\n[Step 6] Testing GET /api/categories/{id}...")
    s, b = make_request("GET", f"/api/categories/{cat1_id}")
    assert s == 200 and b["id"] == cat1_id
    print(f"  ✓ GET /api/categories/{cat1_id} returned 200 OK")

    s, b = make_request("GET", "/api/categories/999999")
    assert s == 404, f"Expected 404 for missing ID, got {s}: {b}"
    print(f"  ✓ Missing ID returned 404 Not Found: {b.get('detail')}")

    # 7. Test PUT /api/categories/{id} (Update)
    print("\n[Step 7] Testing PUT /api/categories/{id} (Update)...")
    update_payload = {
        "name": "Phase3_Test_Starters_Renamed",
        "description": "Updated delicious starters description",
    }
    s, b = make_request("PUT", f"/api/categories/{cat1_id}", update_payload)
    assert s == 200, f"Expected 200, got {s}: {b}"
    assert b["name"] == "Phase3_Test_Starters_Renamed"
    assert b["description"] == "Updated delicious starters description"
    print(f"  ✓ PUT /api/categories/{cat1_id} returned 200 OK with updated name")

    # Create a second category for conflict testing
    payload2 = {"name": "Phase3_Test_Desserts", "description": "Sweets"}
    s, b = make_request("POST", "/api/categories", payload2)
    assert s == 201
    cat2_id = b["id"]
    print(f"  ✓ Created second category ID: {cat2_id}")

    # Try updating category 1 to have category 2's name (409 Conflict)
    s, b = make_request("PUT", f"/api/categories/{cat1_id}", {"name": "Phase3_Test_Desserts"})
    assert s == 409, f"Expected 409 for name conflict on PUT, got {s}: {b}"
    print(f"  ✓ PUT name collision returned 409 Conflict: {b.get('detail')}")

    # 8. Test Foreign Key Restriction on DELETE
    print("\n[Step 8] Testing Foreign Key Restriction on DELETE...")
    # Add a menu item directly linked to cat2_id
    db = SessionLocal()
    try:
        test_dish = MenuItem(
            category_id=cat2_id,
            name="Phase3_Test_Lava_Cake",
            price=Decimal("7.50"),
            description="Warm chocolate cake",
        )
        db.add(test_dish)
        db.commit()
        db.refresh(test_dish)
        dish_id = test_dish.id
        print(f"  ✓ Created temporary menu item '{test_dish.name}' (ID: {dish_id}) referencing Category {cat2_id}")
    finally:
        db.close()

    # Attempt to delete Category 2 while referenced by the menu item
    s, b = make_request("DELETE", f"/api/categories/{cat2_id}")
    assert s == 409, f"Expected 409 due to foreign key restriction, got {s}: {b}"
    print(f"  ✓ Foreign key restriction caught cleanly! Returned 409 Conflict: {b.get('detail')}")

    # Now delete the referencing menu item to unblock category deletion
    db = SessionLocal()
    try:
        item_to_delete = db.query(MenuItem).filter(MenuItem.id == dish_id).first()
        if item_to_delete:
            db.delete(item_to_delete)
            db.commit()
            print(f"  ✓ Safely cleaned up temporary menu item (ID: {dish_id})")
    finally:
        db.close()

    # 9. Test DELETE /api/categories/{id} (204 No Content)
    print("\n[Step 9] Testing DELETE /api/categories/{id}...")
    # Delete category 2
    s, b = make_request("DELETE", f"/api/categories/{cat2_id}")
    assert s == 204, f"Expected 204 No Content, got {s}: {b}"
    assert b is None, "204 response body must be empty"
    print(f"  ✓ DELETE /api/categories/{cat2_id} returned 204 No Content (Empty body)")

    # Delete category 1
    s, b = make_request("DELETE", f"/api/categories/{cat1_id}")
    assert s == 204, f"Expected 204 No Content, got {s}: {b}"
    assert b is None, "204 response body must be empty"
    print(f"  ✓ DELETE /api/categories/{cat1_id} returned 204 No Content (Empty body)")

    # Try deleting non-existent / already deleted category (404 Not Found)
    s, b = make_request("DELETE", f"/api/categories/{cat1_id}")
    assert s == 404, f"Expected 404 for deleted category, got {s}: {b}"
    print(f"  ✓ Deleting already-deleted category returned 404 Not Found: {b.get('detail')}")

    print("\n" + "=" * 65)
    print(" ALL CATEGORIES API TESTS PASSED SUCCESSFULLY! ")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
