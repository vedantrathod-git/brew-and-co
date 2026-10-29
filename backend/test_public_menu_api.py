"""Comprehensive Automated Test Suite for Public Menu API.

Verifies:
1. Anonymous access without authentication.
2. Complete inclusion of all 70 active café items.
3. Complete exclusion of all 10 retired legacy products.
4. Correct inclusion of the 9 active café categories.
5. Exclusion of empty legacy categories (IDs 26-30).
6. Category ID filtering.
7. Case-insensitive text search.
8. Customer-safe response fields.
9. Continued strict protection of internal staff endpoints (401 on unauthenticated calls).
"""

import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def make_request(path: str, headers: dict = None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:
            body = None
        return exc.code, body


def test_public_menu():
    print("=" * 70)
    print(" Running Public Menu API Automated Test Suite")
    print("=" * 70)

    # 1. Anonymous access to GET /api/public/menu
    status_code, data = make_request("/api/public/menu")
    assert status_code == 200, f"Expected 200 OK, got {status_code}"
    print(" [PASS] Anonymous GET /api/public/menu returned 200 OK")

    # 2. Verify total active items and categories
    assert data["total_items"] == 70, f"Expected 70 items, got {data['total_items']}"
    assert len(data["items"]) == 70, f"Expected 70 items in list, got {len(data['items'])}"
    assert data["total_categories"] == 9, f"Expected 9 categories, got {data['total_categories']}"
    assert len(data["categories"]) == 9, f"Expected 9 categories in list, got {len(data['categories'])}"
    print(f" [PASS] Total items verified: {data['total_items']} items across {data['total_categories']} categories")

    # 3. Verify retired legacy products (IDs 25-34) are completely excluded
    legacy_ids = {25, 26, 27, 28, 29, 30, 31, 32, 33, 34}
    returned_ids = {item["id"] for item in data["items"]}
    leaked_legacy = legacy_ids.intersection(returned_ids)
    assert not leaked_legacy, f"Retired legacy items leaked in public menu: {leaked_legacy}"
    print(" [PASS] All 10 retired legacy items strictly excluded")

    # 4. Verify empty legacy categories (IDs 26-30) are excluded
    legacy_cat_ids = {26, 27, 28, 29, 30}
    returned_cat_ids = {c["id"] for c in data["categories"]}
    leaked_cats = legacy_cat_ids.intersection(returned_cat_ids)
    assert not leaked_cats, f"Empty legacy categories leaked in public menu: {leaked_cats}"
    print(" [PASS] All 5 empty legacy categories strictly excluded")

    # 5. Verify every category has positive item_count matching returned items
    for cat in data["categories"]:
        assert cat["item_count"] > 0, f"Category '{cat['name']}' has zero items"
        items_for_cat = [i for i in data["items"] if i["category_id"] == cat["id"]]
        assert len(items_for_cat) == cat["item_count"], (
            f"Item count mismatch for '{cat['name']}': reported {cat['item_count']}, found {len(items_for_cat)}"
        )
    print(" [PASS] Category item counts verified and consistent")

    # 6. Verify customer-safe schema fields
    for item in data["items"]:
        assert item["is_available"] is True, f"Unavailable item leaked: {item['name']}"
        assert float(item["price"]) > 0, f"Non-positive price for item: {item['name']}"
        assert item["name"], "Item missing name"
        assert item["category_name"], "Item missing category_name"
        assert "created_at" not in item, "Internal timestamp 'created_at' exposed"
        assert "updated_at" not in item, "Internal timestamp 'updated_at' exposed"
    print(" [PASS] Customer-safe field structure verified (no internal timestamps or flags)")

    # 7. Category filter testing
    status_code, cat_filtered = make_request("/api/public/menu?category_id=98")
    assert status_code == 200
    assert cat_filtered["total_items"] == 12, f"Expected 12 Coffee items, got {cat_filtered['total_items']}"
    assert all(i["category_id"] == 98 for i in cat_filtered["items"])
    print(f" [PASS] Category filtering (/api/public/menu?category_id=98) returned {cat_filtered['total_items']} items")

    # 8. Search query testing
    status_code, search_filtered = make_request("/api/public/menu?search=croissant")
    assert status_code == 200
    assert search_filtered["total_items"] >= 2, f"Expected at least 2 croissant items, got {search_filtered['total_items']}"
    print(f" [PASS] Search filtering (/api/public/menu?search=croissant) returned {search_filtered['total_items']} items")

    # 9. Granular endpoints verification
    c_status, cats = make_request("/api/public/categories")
    assert c_status == 200 and len(cats) == 9
    i_status, items = make_request("/api/public/menu-items")
    assert i_status == 200 and len(items) == 70
    print(" [PASS] Granular endpoints (/api/public/categories and /api/public/menu-items) verified")

    # 10. Continued strict protection of staff endpoints
    protected_endpoints = [
        "/api/menu-items",
        "/api/categories",
        "/api/tables",
        "/api/orders",
        "/api/users",
        "/api/auth/me",
    ]
    for ep in protected_endpoints:
        status, _ = make_request(ep)
        assert status == 401, f"Expected 401 Unauthorized for unauthenticated {ep}, got {status}"
        print(f" [PASS] Staff endpoint {ep} strictly returns 401 Unauthorized when unauthenticated")

    print("\n" + "=" * 70)
    print(" ALL 10 TEST SUITES IN test_public_menu_api.py PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_public_menu()
