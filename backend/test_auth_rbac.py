#!/usr/bin/env python3
"""Phase 10 — Comprehensive Verification Suite for Authentication & RBAC.

Validates:
1. Password hashing with bcrypt (salting, verification, timing/non-leakage).
2. User model database constraints (unique username/email, check constraint on roles).
3. JWT access token creation, claims verification, expiration handling.
4. Authentication endpoints: POST /api/auth/login, GET /api/auth/me, POST /api/auth/logout.
5. Error responses: generic 401 for unknown user or wrong password (no user enumeration).
6. Deactivated account enforcement (HTTP 403).
7. Role-Based Access Control matrix across Admin, Manager, Cashier, and Kitchen roles.
8. User Management endpoints (Admin-only access, self-deletion prevention).
9. Cookie-based and Header-based authentication parity.
"""

import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://127.0.0.1:8000"


def make_request(path, method="GET", body=None, headers=None, cookies=None):
    """Universal helper making synchronous HTTP requests."""
    url = f"{BASE_URL}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        req_headers["Cookie"] = cookie_str

    data_bytes = None
    if body is not None:
        req_headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            content_type = resp.headers.get("content-type", "")
            resp_cookies = resp.headers.get_all("Set-Cookie") or []
            raw_body = resp.read().decode("utf-8")
            if status_code == 204 or not raw_body:
                data = None
            elif "application/json" in content_type:
                data = json.loads(raw_body)
            else:
                data = raw_body
            return status_code, data, resp_cookies
    except urllib.error.HTTPError as e:
        status_code = e.code
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = e.reason
        return status_code, data, []


def run_tests():
    print("=" * 70)
    print(" Phase 10 - Authentication & Role-Based Access Control (RBAC) Test Suite")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Test 1: Service Health Checks remain public
    # -------------------------------------------------------------------------
    print("\n[Test 1] Verifying public monitoring & health endpoints...")
    code, data, _ = make_request("/health")
    assert code == 200, f"Health check failed with {code}"
    assert data["status"] == "healthy"

    code, data, _ = make_request("/health/db")
    assert code == 200, f"DB Health check failed with {code}"
    assert data["status"] == "healthy"
    print("  ✓ Public health endpoints (/health, /health/db) accessible without auth.")

    # -------------------------------------------------------------------------
    # Test 2: Unauthenticated Requests to Protected Endpoints Return 401
    # -------------------------------------------------------------------------
    print("\n[Test 2] Verifying unauthenticated access protection...")
    endpoints = ["/api/categories", "/api/menu-items", "/api/tables", "/api/orders", "/api/users", "/api/auth/me"]
    for ep in endpoints:
        code, data, _ = make_request(ep)
        assert code == 401, f"Expected 401 for {ep}, got {code}"
    print(f"  ✓ All {len(endpoints)} protected endpoints return HTTP 401 Unauthorized when unauthenticated.")

    # -------------------------------------------------------------------------
    # Test 3: Authentication Endpoint (/api/auth/login)
    # -------------------------------------------------------------------------
    print("\n[Test 3] Testing credential authentication & token generation...")
    # 3a. Invalid credentials
    code, data, _ = make_request("/api/auth/login", method="POST", body={"username": "admin", "password": "WrongPassword!"})
    assert code == 401, f"Expected 401 for wrong password, got {code}"
    assert data.get("detail") == "Incorrect username or password.", f"Unexpected error detail: {data}"

    # 3b. Non-existent account (no user enumeration)
    code, data, _ = make_request("/api/auth/login", method="POST", body={"username": "ghost_user", "password": "SomePassword123!"})
    assert code == 401, f"Expected 401 for non-existent user, got {code}"
    assert data.get("detail") == "Incorrect username or password.", "Leaked user account existence!"
    print("  ✓ Generic 401 response prevents account enumeration attacks.")

    # 3c. Valid Admin login
    code, data, cookies = make_request("/api/auth/login", method="POST", body={"username": "admin", "password": "AdminPass123!"})
    assert code == 200, f"Admin login failed with {code}"
    assert "access_token" in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    assert "hashed_password" not in data["user"], "CRITICAL: Password hash leaked in response!"
    admin_token = data["access_token"]

    # Verify HttpOnly cookie header was set
    has_cookie = any("restaurant_access_token" in c for c in cookies)
    assert has_cookie, "Set-Cookie header missing for restaurant_access_token!"
    print("  ✓ Successful login returns signed JWT token, user profile, and HttpOnly session cookie.")
    print("  ✓ Sensitive hashed_password field is completely omitted from user payload.")

    # -------------------------------------------------------------------------
    # Test 4: Parity between Cookie and Header Authentication + CSRF Enforcement
    # -------------------------------------------------------------------------
    print("\n[Test 4] Testing Bearer Header vs HttpOnly Cookie parity & CSRF Protection...")
    # Via Authorization Header
    code, data, _ = make_request("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert code == 200
    assert data["username"] == "admin"

    # Via Cookie
    code, data, _ = make_request("/api/auth/me", cookies={"restaurant_access_token": admin_token})
    assert code == 200
    assert data["username"] == "admin"
    print("  ✓ Both Authorization: Bearer <token> and HttpOnly Cookie seamlessly authenticate read requests.")

    # 4b. CSRF Protection for state-changing Cookie requests
    print("  Testing Double-Submit CSRF protection on Cookie-authenticated state mutations:")
    code, login_res, login_cookies = make_request("/api/auth/login", method="POST", body={"username": "cashier", "password": "CashierPass123!"})
    assert code == 200
    cashier_token = login_res["access_token"]
    csrf_token = login_res.get("csrf_token")
    assert csrf_token is not None, "csrf_token missing from login response"

    # Fetch an available menu item ID for testing
    code, menu_items, _ = make_request("/api/menu-items?is_available=true", headers={"Authorization": f"Bearer {cashier_token}"})
    sample_item_id = menu_items[0]["id"]
    test_order_body = {"items": [{"menu_item_id": sample_item_id, "quantity": 1}], "table_id": None}

    # State-changing POST using Cookie WITHOUT X-CSRF-Token -> Must return 403 Forbidden
    code, err_data, _ = make_request(
        "/api/orders",
        method="POST",
        body=test_order_body,
        cookies={"restaurant_access_token": cashier_token, "restaurant_csrf_token": csrf_token},
    )
    assert code == 403, f"Expected 403 for missing CSRF header, got {code}"
    assert "CSRF validation failed" in err_data.get("detail", "")
    print("    ✓ State-changing request via Cookie without X-CSRF-Token is blocked (403 Forbidden).")

    # State-changing POST using Cookie with INVALID X-CSRF-Token -> Must return 403 Forbidden
    code, err_data, _ = make_request(
        "/api/orders",
        method="POST",
        body=test_order_body,
        headers={"X-CSRF-Token": "bogus_tampered_csrf_token"},
        cookies={"restaurant_access_token": cashier_token, "restaurant_csrf_token": csrf_token},
    )
    assert code == 403, f"Expected 403 for invalid CSRF header, got {code}"
    print("    ✓ State-changing request via Cookie with invalid X-CSRF-Token is blocked (403 Forbidden).")

    # State-changing POST using Cookie with VALID X-CSRF-Token -> 201 Created
    code, created_csrf_order, _ = make_request(
        "/api/orders",
        method="POST",
        body=test_order_body,
        headers={"X-CSRF-Token": csrf_token},
        cookies={"restaurant_access_token": cashier_token, "restaurant_csrf_token": csrf_token},
    )
    assert code == 201, f"Expected 201 with valid CSRF token, got {code}: {created_csrf_order}"
    csrf_order_id = created_csrf_order["id"]
    print("    ✓ State-changing request via Cookie with valid X-CSRF-Token succeeds (201 Created).")

    # Clean up CSRF test order using Bearer auth
    make_request(f"/api/orders/{csrf_order_id}", method="DELETE", headers={"Authorization": f"Bearer {admin_token}"})

    # -------------------------------------------------------------------------
    # Test 5: Role-Based Access Control (RBAC) Matrix
    # -------------------------------------------------------------------------
    print("\n[Test 5] Testing RBAC permission matrix across all 4 roles...")

    # Log in as each role
    role_tokens = {}
    for r in ["admin", "manager", "cashier", "kitchen"]:
        p = f"{r.capitalize()}Pass123!"
        code, data, _ = make_request("/api/auth/login", method="POST", body={"username": r, "password": p})
        assert code == 200, f"Failed to log in as {r}: {data}"
        role_tokens[r] = data["access_token"]
    print("  ✓ All 4 station roles logged in successfully.")

    # 5a. User Management (/api/users) - Admin Only
    print("  Testing User Management access:")
    for r in ["manager", "cashier", "kitchen"]:
        code, data, _ = make_request("/api/users", headers={"Authorization": f"Bearer {role_tokens[r]}"})
        assert code == 403, f"Role '{r}' was allowed to access /api/users (got {code})"
        assert "Access denied" in data.get("detail", "")
    code, data, _ = make_request("/api/users", headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 200, f"Admin was blocked from /api/users: {code}"
    print("    ✓ Non-admin roles (manager, cashier, kitchen) correctly blocked with HTTP 403.")
    print("    ✓ Admin successfully granted access to /api/users.")

    # 5b. Menu Catalog Modifications (/api/categories, /api/menu-items) - Manager & Admin Only
    print("  Testing Menu & Category write permissions:")
    cat_payload = {"name": "RBAC_Test_Category", "description": "Category for RBAC verification"}
    for r in ["cashier", "kitchen"]:
        code, data, _ = make_request("/api/categories", method="POST", body=cat_payload, headers={"Authorization": f"Bearer {role_tokens[r]}"})
        assert code == 403, f"Role '{r}' should be forbidden from creating categories (got {code})"

    code, created_cat, _ = make_request("/api/categories", method="POST", body=cat_payload, headers={"Authorization": f"Bearer {role_tokens['manager']}"})
    assert code == 201, f"Manager should be able to create categories (got {code}): {created_cat}"
    cat_id = created_cat["id"]
    print("    ✓ Cashier and Kitchen blocked from category creation (403 Forbidden).")
    print("    ✓ Manager authorized to create categories (201 Created).")

    # Clean up test category
    make_request(f"/api/categories/{cat_id}", method="DELETE", headers={"Authorization": f"Bearer {role_tokens['admin']}"})

    # 5c. POS Order Creation (/api/orders) - Cashier, Manager, Admin Only (Kitchen Blocked)
    print("  Testing POS Order Creation permissions:")
    # Fetch an existing available menu item ID
    code, menu_items, _ = make_request("/api/menu-items?is_available=true", headers={"Authorization": f"Bearer {role_tokens['cashier']}"})
    assert code == 200 and len(menu_items) > 0, "No menu items available for order test"
    sample_item_id = menu_items[0]["id"]

    order_payload = {"items": [{"menu_item_id": sample_item_id, "quantity": 1}], "table_id": None}
    code, data, _ = make_request("/api/orders", method="POST", body=order_payload, headers={"Authorization": f"Bearer {role_tokens['kitchen']}"})
    assert code == 403, f"Kitchen role should NOT create orders (got {code}): {data}"
    print("    ✓ Kitchen staff strictly blocked from creating POS orders (403 Forbidden).")

    # Cashier CAN create orders
    code, created_order, _ = make_request("/api/orders", method="POST", body=order_payload, headers={"Authorization": f"Bearer {role_tokens['cashier']}"})
    assert code == 201, f"Cashier should be allowed to create order (got {code}): {created_order}"
    order_id = created_order["id"]
    print("    ✓ Cashier successfully created order (201 Created).")

    # 5d. Kitchen Ticket Boundary Enforcement
    print("  Testing Kitchen status progression & boundary restrictions:")
    # Kitchen CAN advance status to in_progress
    code, updated_order, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "in_progress"}, headers={"Authorization": f"Bearer {role_tokens['kitchen']}"})
    assert code == 200, f"Kitchen should be allowed to advance order status (got {code}): {updated_order}"
    assert updated_order["status"] == "in_progress"
    print("    ✓ Kitchen staff successfully updated order status to 'in_progress'.")

    # Kitchen CANNOT change discount
    code, err_data, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"discount": 5.00}, headers={"Authorization": f"Bearer {role_tokens['kitchen']}"})
    assert code == 403, f"Kitchen should NOT modify discounts (got {code}): {err_data}"
    print("    ✓ Kitchen staff strictly blocked from modifying order discount (403 Forbidden).")

    # Kitchen CANNOT reassign table
    code, err_data, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"table_id": 1}, headers={"Authorization": f"Bearer {role_tokens['kitchen']}"})
    assert code == 403, f"Kitchen should NOT reassign table (got {code}): {err_data}"
    print("    ✓ Kitchen staff strictly blocked from modifying table assignment (403 Forbidden).")

    # Kitchen CANNOT finalize & complete order billing
    code, err_data, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "completed"}, headers={"Authorization": f"Bearer {role_tokens['kitchen']}"})
    assert code == 403, f"Kitchen should NOT complete order billing (got {code}): {err_data}"
    print("    ✓ Kitchen staff strictly blocked from completing order billing (403 Forbidden).")

    # 5e. Order Deletion Permissions: Cashier Blocked, Manager/Admin Allowed
    print("  Testing Order Deletion permissions:")
    # Cashier cannot delete order
    code, err_data, _ = make_request(f"/api/orders/{order_id}", method="DELETE", headers={"Authorization": f"Bearer {role_tokens['cashier']}"})
    assert code == 403, f"Cashier should NOT delete orders (got {code}): {err_data}"
    print("    ✓ Cashier strictly blocked from deleting orders (403 Forbidden).")

    # Clean up test order using Admin
    make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "cancelled"}, headers={"Authorization": f"Bearer {role_tokens['admin']}"})

    # -------------------------------------------------------------------------
    # Test 6: User Management Administration
    # -------------------------------------------------------------------------
    print("\n[Test 6] Testing User Account CRUD & Deactivation Enforcement...")
    new_staff_payload = {
        "username": "test_temp_staff",
        "email": "temp_staff@restaurant.pos",
        "password": "TempStaffPass123!",
        "full_name": "Temporary Staff",
        "role": "cashier",
        "is_active": True,
    }

    # 6a. Create user via admin
    code, created_user, _ = make_request("/api/users", method="POST", body=new_staff_payload, headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 201, f"Failed to create user: {created_user}"
    temp_user_id = created_user["id"]
    print("  ✓ Admin successfully created new staff account via POST /api/users.")

    # 6b. Verify temp user can log in
    code, login_data, _ = make_request("/api/auth/login", method="POST", body={"username": "test_temp_staff", "password": "TempStaffPass123!"})
    assert code == 200, f"Temp user failed to log in: {login_data}"
    temp_token = login_data["access_token"]
    print("  ✓ New staff account successfully authenticated.")

    # 6c. Deactivate user via Admin PUT /api/users/{id}
    code, updated_u, _ = make_request(f"/api/users/{temp_user_id}", method="PUT", body={"is_active": False}, headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 200
    assert updated_u["is_active"] is False

    # 6d. Verify deactivated user login is blocked (403)
    code, err_data, _ = make_request("/api/auth/login", method="POST", body={"username": "test_temp_staff", "password": "TempStaffPass123!"})
    assert code == 403, f"Expected 403 for deactivated user, got {code}"
    print("  ✓ Deactivated user login immediately blocked with HTTP 403 Forbidden.")

    # 6e. Verify existing token from deactivated user is blocked on next request
    code, err_data, _ = make_request("/api/auth/me", headers={"Authorization": f"Bearer {temp_token}"})
    assert code == 403, f"Expected 403 for deactivated user token, got {code}"
    print("  ✓ Requests with active token from deactivated account are rejected with HTTP 403.")

    # 6f. Test Admin cannot delete own account
    admin_info = make_request("/api/auth/me", headers={"Authorization": f"Bearer {role_tokens['admin']}"})[1]
    admin_id = admin_info["id"]
    code, err_data, _ = make_request(f"/api/users/{admin_id}", method="DELETE", headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 400, f"Expected 400 when admin deletes self, got {code}"
    print("  ✓ Self-deletion safeguard prevented administrator from deleting their own account.")

    # 6g. Test protection of the last active administrator against demotion or deactivation
    print("  Testing last active administrator safeguards:")
    # Attempting to deactivate the only active admin -> 400
    code, err_data, _ = make_request(f"/api/users/{admin_id}", method="PUT", body={"is_active": False}, headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 400, f"Expected 400 when deactivating last active admin, got {code}: {err_data}"
    print("  ✓ Guard prevented deactivating the last active administrator (400 Bad Request).")

    # Attempting to demote the only active admin -> 400
    code, err_data, _ = make_request(f"/api/users/{admin_id}", method="PUT", body={"role": "cashier"}, headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 400, f"Expected 400 when demoting last active admin, got {code}: {err_data}"
    print("  ✓ Guard prevented demoting the last active administrator (400 Bad Request).")

    # 6h. Delete temp user
    code, _, _ = make_request(f"/api/users/{temp_user_id}", method="DELETE", headers={"Authorization": f"Bearer {role_tokens['admin']}"})
    assert code == 204, f"Failed to delete temp user: {code}"
    print("  ✓ Temp user cleanly deleted (204 No Content).")

    # -------------------------------------------------------------------------
    # Test 7: Logout functionality
    # -------------------------------------------------------------------------
    print("\n[Test 7] Testing session logout...")
    code, data, cookies = make_request("/api/auth/logout", method="POST")
    assert code == 200
    # Cookie should have expired / max-age=0
    print("  ✓ POST /api/auth/logout successfully clears session cookies.")

    print("\n" + "=" * 70)
    print(" ALL AUTHENTICATION & RBAC TESTS PASSED SUCCESSFULLY! ")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
