#!/usr/bin/env python3
"""Phase 20 — HTTP End-to-End Verification for Inventory REST Endpoints."""

import json
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def make_request(path, method="GET", body=None, token=None):
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


def login(username, password):
    status_code, data = make_request("/api/auth/login", method="POST", body={"username": username, "password": password})
    assert status_code == 200, f"Login failed for {username}: {data}"
    return data["access_token"]


def main():
    print("=" * 70)
    print(" Phase 20 - Inventory REST Endpoints HTTP Verification")
    print("=" * 70)

    # 1. Unauthenticated rejection
    status_code, _ = make_request("/api/inventory/ingredients")
    assert status_code == 401, f"Expected 401 unauthenticated, got {status_code}"
    print("  ✓ Unauthenticated access strictly blocked (HTTP 401)")

    # 2. Authenticate tokens for cashier and manager
    cashier_token = login("cashier", "CashierPass123!")
    manager_token = login("manager", "ManagerPass123!")
    print("  ✓ Authenticated cashier and manager sessions")

    # 3. RBAC checks: Cashier forbidden from creating ingredients
    status_code, _ = make_request(
        "/api/inventory/ingredients",
        method="POST",
        body={"name": "Cashier Attempt Beans", "unit": "g", "minimum_stock": "100.000", "initial_stock": "500.000"},
        token=cashier_token,
    )
    assert status_code == 403, f"Expected 403 for cashier, got {status_code}"
    print("  ✓ Cashier role strictly blocked from creating ingredients (HTTP 403)")

    # 4. Manager can create ingredient
    test_ing_name = "Phase20 HTTP Single-Origin Beans"
    status_code, ing_data = make_request(
        "/api/inventory/ingredients",
        method="POST",
        body={"name": test_ing_name, "unit": "g", "minimum_stock": "150.000", "initial_stock": "600.000"},
        token=manager_token,
    )
    assert status_code == 201, f"Expected 201 for manager, got {status_code}: {ing_data}"
    ing_id = ing_data["id"]
    print(f"  ✓ Manager created ingredient '{test_ing_name}' (ID {ing_id})")

    # 5. Cashier can list ingredients (read access)
    status_code, list_data = make_request("/api/inventory/ingredients", token=cashier_token)
    assert status_code == 200
    assert any(i["id"] == ing_id for i in list_data)
    print("  ✓ Cashier granted read-only access to ingredient catalog (HTTP 200)")

    # 6. Dashboard summary
    status_code, summary_data = make_request("/api/inventory/dashboard-summary", token=cashier_token)
    assert status_code == 200
    assert "total_active_ingredients" in summary_data
    assert "low_stock_count" in summary_data
    print(f"  ✓ Dashboard summary loaded: {summary_data['total_active_ingredients']} active ingredients")

    # 7. Restock adjustment
    status_code, adj_data = make_request(
        f"/api/inventory/ingredients/{ing_id}/adjust",
        method="POST",
        body={"adjustment_type": "restock", "quantity": "400.000", "reason": "Vendor restock test"},
        token=manager_token,
    )
    assert status_code == 201, f"Expected 201 on adjust, got {status_code}: {adj_data}"
    assert float(adj_data["quantity_delta"]) == 400.0
    print("  ✓ Restock adjustment recorded in audit ledger (HTTP 201)")

    # 8. Check movement ledger
    status_code, movements = make_request(f"/api/inventory/movements?ingredient_id={ing_id}", token=manager_token)
    assert status_code == 200
    assert len(movements) >= 2  # initial + restock
    print(f"  ✓ Movement ledger retrieved {len(movements)} records for ingredient")

    # 9. Clean up test ingredient
    status_code, _ = make_request(f"/api/inventory/ingredients/{ing_id}", method="DELETE", token=manager_token)
    assert status_code == 204
    print("  ✓ Test ingredient safely deactivated / cleaned up (HTTP 204)")

    print("\n======================================================================")
    print(" ALL INVENTORY HTTP INTEGRATION TESTS PASSED CLEANLY! (100% SUCCESS)")
    print("======================================================================")


if __name__ == "__main__":
    main()
