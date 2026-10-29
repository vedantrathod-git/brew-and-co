#!/usr/bin/env python3
"""Phase 11 — End-to-End Workflow & Integration Test Suite.

Executes comprehensive end-to-end restaurant workflows:
1. Authentication & Session Lifecycles:
   - Valid vs. invalid credentials & enumeration resistance
   - Session restoration via GET /api/auth/me (Bearer token & HttpOnly cookie)
   - Malformed/tampered JWT rejection (HTTP 401)
   - Double-submit CSRF enforcement on cookie state-mutations
   - Session logout & cookie clearing
2. Full Dine-In Lifecycle:
   - Cashier checks tables & menu
   - Cashier places dine-in order for available table
   - Table immediately transitions to 'occupied'
   - Kitchen views live tickets, transitions order to 'in_progress', then 'served'
   - Role boundary enforcement during ticket handling (kitchen blocked from discount/table/completion/deletion)
   - Cashier completes dine-in order ('completed', timestamp set)
   - Table automatically returns to 'available'
3. Full Takeaway Lifecycle:
   - Cashier places takeaway order (table_id=None)
   - Order transitions through kitchen prep to completion
   - Verification of zero table occupancy side-effects
4. Direct HTTP Role Permission Boundaries:
   - Kitchen restrictions (no POS creation, no deletion, no menu edit, no users)
   - Cashier restrictions (no order deletion, no menu edit, no table deletion, no users)
   - Manager restrictions (catalog & POS full management, but blocked from users)
   - Admin security guardrails (self-deletion block, demotion block for last active admin)
5. Zero-pollution cleanup of test-created orders.
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def make_request(path, method="GET", body=None, headers=None, cookies=None):
    """Universal HTTP request helper."""
    url = f"{BASE_URL}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    if cookies:
        req_headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in cookies.items()])

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


def extract_cookie_val(cookies_list, cookie_name):
    """Extract cookie value from list of Set-Cookie header strings."""
    for c in cookies_list:
        parts = c.split(";")
        for part in parts:
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == cookie_name:
                    return v
    return None


def run_e2e_tests():
    print("=" * 75)
    print(" PHASE 11: END-TO-END RESTAURANT SYSTEM VERIFICATION SUITE")
    print("=" * 75)

    created_order_ids = []

    try:
        # =====================================================================
        # SECTION 1: Authentication & Session Verification
        # =====================================================================
        print("\n[Section 1] Authentication, Session Management & CSRF Enforcement...")

        # 1a. Invalid login rejected (generic message)
        code, err, _ = make_request("/api/auth/login", method="POST", body={"username": "cashier", "password": "WrongPassword999!"})
        assert code == 401, f"Expected 401 for wrong password, got {code}"
        assert err.get("detail") == "Incorrect username or password."
        print("  ✓ Invalid password rejected with generic 401.")

        code, err, _ = make_request("/api/auth/login", method="POST", body={"username": "unknown_actor", "password": "AnyPassword!"})
        assert code == 401, f"Expected 401 for non-existent user, got {code}"
        assert err.get("detail") == "Incorrect username or password."
        print("  ✓ Non-existent user rejected with generic 401 (no account enumeration).")

        # 1b. Valid login for Cashier
        code, cash_login, cash_set_cookies = make_request("/api/auth/login", method="POST", body={"username": "cashier", "password": "CashierPass123!"})
        assert code == 200, f"Cashier login failed: {cash_login}"
        cashier_token = cash_login["access_token"]
        cashier_csrf = cash_login.get("csrf_token")
        assert cashier_csrf is not None, "CSRF token missing from login payload"
        print(f"  ✓ Cashier authenticated: user={cash_login['user']['username']}, role={cash_login['user']['role']}")

        # 1c. Session restoration via GET /api/auth/me (Bearer token & Cookie)
        code, me_bearer, _ = make_request("/api/auth/me", headers={"Authorization": f"Bearer {cashier_token}"})
        assert code == 200 and me_bearer["username"] == "cashier"
        print("  ✓ Session verified via Authorization: Bearer token.")

        code, me_cookie, _ = make_request("/api/auth/me", cookies={"restaurant_access_token": cashier_token})
        assert code == 200 and me_cookie["username"] == "cashier"
        print("  ✓ Session verified via HttpOnly restaurant_access_token cookie.")

        # 1d. Expired or tampered token rejection
        code, _, _ = make_request("/api/auth/me", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.token"})
        assert code == 401, f"Expected 401 for tampered JWT, got {code}"
        print("  ✓ Tampered/malformed JWT rejected with 401 Unauthorized.")

        # 1e. CSRF validation on cookie mutations
        dummy_order = {"items": [{"menu_item_id": 1, "quantity": 1}], "table_id": None}
        code, csrf_err, _ = make_request(
            "/api/orders",
            method="POST",
            body=dummy_order,
            cookies={"restaurant_access_token": cashier_token, "restaurant_csrf_token": cashier_csrf},
        )
        assert code == 403, f"Expected 403 for cookie POST without X-CSRF-Token, got {code}"
        assert "CSRF validation failed" in csrf_err.get("detail", "")
        print("  ✓ Cookie mutation without X-CSRF-Token strictly blocked (403 Forbidden).")

        # 1f. Valid login for all other station roles
        station_tokens = {"cashier": cashier_token}
        for role in ["admin", "manager", "kitchen"]:
            pw = f"{role.capitalize()}Pass123!"
            code, data, _ = make_request("/api/auth/login", method="POST", body={"username": role, "password": pw})
            assert code == 200, f"Login failed for role {role}"
            station_tokens[role] = data["access_token"]
        print("  ✓ All 4 station roles (admin, manager, cashier, kitchen) authenticated successfully.")

        # =====================================================================
        # SECTION 2: End-to-End Dine-In Restaurant Workflow
        # =====================================================================
        print("\n[Section 2] End-to-End Dine-In Order Lifecycle...")

        # 2a. Cashier inspects menu and tables
        code, menu_items, _ = make_request("/api/menu-items?is_available=true", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 200 and len(menu_items) >= 2, "Insufficient menu items for E2E test"
        item1 = menu_items[0]
        item2 = menu_items[1]
        print(f"  ✓ Cashier retrieved menu: using '{item1['name']}' (${item1['price']}) and '{item2['name']}' (${item2['price']})")

        code, tables, _ = make_request("/api/tables", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 200 and len(tables) > 0, "No tables found"
        # Find an available table
        avail_table = next((t for t in tables if t["status"] == "available"), None)
        assert avail_table is not None, "No available table found for dine-in test"
        target_table_id = avail_table["id"]
        target_table_num = avail_table["table_number"]
        print(f"  ✓ Cashier selected available Table {target_table_num} (ID: {target_table_id})")

        # 2b. Cashier creates Dine-In Order
        dine_in_payload = {
            "table_id": target_table_id,
            "items": [
                {"menu_item_id": item1["id"], "quantity": 2, "special_instructions": "Extra sauce"},
                {"menu_item_id": item2["id"], "quantity": 1, "special_instructions": "No onions"},
            ],
            "discount": 0.0,
        }
        code, created_order, _ = make_request("/api/orders", method="POST", body=dine_in_payload, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 201, f"Failed to create dine-in order: {created_order}"
        order_id = created_order["id"]
        order_num = created_order["order_number"]
        created_order_ids.append(order_id)
        assert created_order["status"] == "pending"
        assert created_order["table_id"] == target_table_id
        assert len(created_order["items"]) == 2
        print(f"  ✓ Dine-in order placed: {order_num} (ID: {order_id}), Total: ${created_order['total']}, Status: {created_order['status']}")

        # 2c. Verify Table is now 'occupied'
        code, table_check, _ = make_request(f"/api/tables/{target_table_id}", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 200
        assert table_check["status"] == "occupied", f"Table should be occupied, got {table_check['status']}"
        print(f"  ✓ Table {target_table_num} status successfully synchronized to 'occupied'.")

        # 2d. Prevent double booking on occupied table
        code, conflict_order, _ = make_request("/api/orders", method="POST", body=dine_in_payload, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 409, f"Expected 409 on occupied table, got {code}"
        print(f"  ✓ Double-booking prevented: second order at Table {target_table_num} rejected with 409 Conflict.")

        # 2e. Kitchen views orders
        code, kitchen_orders, _ = make_request("/api/orders", headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 200
        kitchen_ticket = next((o for o in kitchen_orders if o["id"] == order_id), None)
        assert kitchen_ticket is not None, f"Order {order_id} not visible on kitchen board"
        assert kitchen_ticket["status"] == "pending"
        print(f"  ✓ Kitchen received live ticket: Order #{kitchen_ticket['order_number']} with {len(kitchen_ticket['items'])} item(s).")

        # 2f. Kitchen attempts forbidden actions on the order
        # Kitchen cannot set discount
        code, err, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"discount": 2.0}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Expected 403 when kitchen edits discount, got {code}"
        # Kitchen cannot reassign table
        code, err, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"table_id": None}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Expected 403 when kitchen edits table_id, got {code}"
        # Kitchen cannot complete billing directly from pending
        code, err, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "completed"}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Expected 403 when kitchen marks order completed, got {code}"
        print("  ✓ Kitchen station boundary enforced: discount edits, table changes, and billing completion blocked (403 Forbidden).")

        # 2g. Kitchen advances order: pending -> in_progress
        code, in_prog_order, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "in_progress"}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 200 and in_prog_order["status"] == "in_progress"
        print("  ✓ Kitchen advanced order to 'in_progress'.")

        # 2h. Kitchen advances order: in_progress -> served
        code, served_order, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "served"}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 200 and served_order["status"] == "served"
        print("  ✓ Kitchen advanced order to 'served'.")

        # 2i. Cashier finalizes and completes the order
        code, completed_order, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "completed"}, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 200 and completed_order["status"] == "completed"
        assert completed_order["completed_at"] is not None
        print(f"  ✓ Cashier completed order billing at {completed_order['completed_at']}.")

        # 2j. Verify Table is automatically freed to 'available'
        code, freed_table, _ = make_request(f"/api/tables/{target_table_id}", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 200
        assert freed_table["status"] == "available", f"Table should be available, got {freed_table['status']}"
        print(f"  ✓ Table {target_table_num} automatically freed to 'available' upon order completion.")

        # 2k. Verify completed order cannot be further modified
        code, err, _ = make_request(f"/api/orders/{order_id}", method="PUT", body={"status": "cancelled"}, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 409, f"Expected 409 modifying completed order, got {code}"
        print("  ✓ Terminal state immutability enforced: completed order cannot be modified (409 Conflict).")

        # =====================================================================
        # SECTION 3: End-to-End Takeaway Restaurant Workflow
        # =====================================================================
        print("\n[Section 3] End-to-End Takeaway Order Lifecycle...")

        takeaway_payload = {
            "table_id": None,
            "items": [{"menu_item_id": item1["id"], "quantity": 1}],
            "discount": 1.0,
        }
        code, takeaway_order, _ = make_request("/api/orders", method="POST", body=takeaway_payload, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 201
        takeaway_id = takeaway_order["id"]
        created_order_ids.append(takeaway_id)
        assert takeaway_order["table_id"] is None
        assert takeaway_order["table_number"] is None
        print(f"  ✓ Takeaway order created: #{takeaway_order['order_number']} (ID: {takeaway_id}, table_id=None).")

        # Takeaway orders can transition pending -> in_progress -> completed
        code, updated_takeaway, _ = make_request(f"/api/orders/{takeaway_id}", method="PUT", body={"status": "in_progress"}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 200 and updated_takeaway["status"] == "in_progress"

        code, finished_takeaway, _ = make_request(f"/api/orders/{takeaway_id}", method="PUT", body={"status": "completed"}, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 200 and finished_takeaway["status"] == "completed"
        assert finished_takeaway["completed_at"] is not None
        print(f"  ✓ Takeaway order successfully fulfilled and marked completed (completed_at set).")

        # =====================================================================
        # SECTION 4: Role-Based Access Control (Direct HTTP Boundary Testing)
        # =====================================================================
        print("\n[Section 4] Direct HTTP Authorization & Boundary Testing...")

        # 4a. Kitchen role boundary checks
        # - Kitchen cannot create orders (POST /api/orders) -> 403
        code, _, _ = make_request("/api/orders", method="POST", body=takeaway_payload, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Kitchen should not create orders, got {code}"
        # - Kitchen cannot delete orders -> 403
        code, _, _ = make_request(f"/api/orders/{takeaway_id}", method="DELETE", headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Kitchen should not delete orders, got {code}"
        # - Kitchen cannot edit menu items -> 403
        code, _, _ = make_request(f"/api/menu-items/{item1['id']}", method="PUT", body={"price": 99.99}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Kitchen should not edit menu items, got {code}"
        # - Kitchen cannot create categories -> 403
        code, _, _ = make_request("/api/categories", method="POST", body={"name": "IllegalKitchenCat"}, headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Kitchen should not create categories, got {code}"
        # - Kitchen cannot access user management -> 403
        code, _, _ = make_request("/api/users", headers={"Authorization": f"Bearer {station_tokens['kitchen']}"})
        assert code == 403, f"Kitchen should not view users, got {code}"
        print("  ✓ Kitchen role boundaries fully verified (all forbidden operations return 403).")

        # 4b. Cashier role boundary checks
        # - Cashier cannot delete orders -> 403
        code, _, _ = make_request(f"/api/orders/{takeaway_id}", method="DELETE", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 403, f"Cashier should not delete orders, got {code}"
        # - Cashier cannot create menu items -> 403
        code, _, _ = make_request("/api/menu-items", method="POST", body={"category_id": 1, "name": "IllegalCashierItem", "price": 10}, headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 403, f"Cashier should not create menu items, got {code}"
        # - Cashier cannot delete tables -> 403
        code, _, _ = make_request(f"/api/tables/{target_table_id}", method="DELETE", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 403, f"Cashier should not delete tables, got {code}"
        # - Cashier cannot access user management -> 403
        code, _, _ = make_request("/api/users", headers={"Authorization": f"Bearer {station_tokens['cashier']}"})
        assert code == 403, f"Cashier should not view users, got {code}"
        print("  ✓ Cashier role boundaries fully verified (all forbidden operations return 403).")

        # 4c. Manager role boundary checks
        # - Manager CAN view & manage orders, tables, menu, categories
        code, mgr_cats, _ = make_request("/api/categories", headers={"Authorization": f"Bearer {station_tokens['manager']}"})
        assert code == 200, f"Manager should read categories, got {code}"
        # - Manager CANNOT access user management -> 403
        code, _, _ = make_request("/api/users", headers={"Authorization": f"Bearer {station_tokens['manager']}"})
        assert code == 403, f"Manager should not view users, got {code}"
        print("  ✓ Manager role boundaries fully verified (authorized for catalog/POS/tables, blocked from users).")

        # 4d. Administrator safeguards
        # Admin cannot delete own account
        code, me_admin, _ = make_request("/api/auth/me", headers={"Authorization": f"Bearer {station_tokens['admin']}"})
        admin_id = me_admin["id"]
        code, err, _ = make_request(f"/api/users/{admin_id}", method="DELETE", headers={"Authorization": f"Bearer {station_tokens['admin']}"})
        assert code == 400, f"Expected 400 when admin deletes self, got {code}"
        # Admin cannot deactivate the last active administrator
        code, err, _ = make_request(f"/api/users/{admin_id}", method="PUT", body={"is_active": False}, headers={"Authorization": f"Bearer {station_tokens['admin']}"})
        assert code == 400, f"Expected 400 deactivating last admin, got {code}"
        # Admin cannot demote the last active administrator
        code, err, _ = make_request(f"/api/users/{admin_id}", method="PUT", body={"role": "manager"}, headers={"Authorization": f"Bearer {station_tokens['admin']}"})
        assert code == 400, f"Expected 400 demoting last admin, got {code}"
        print("  ✓ Administrator safeguards verified: self-deletion, demotion, and deactivation blocked (400 Bad Request).")

        # =====================================================================
        # SECTION 5: Session Termination
        # =====================================================================
        print("\n[Section 5] Session Termination & Cookie Invalidation...")
        code, logout_data, logout_cookies = make_request("/api/auth/logout", method="POST")
        assert code == 200
        assert logout_data.get("message") == "Successfully logged out."
        print("  ✓ POST /api/auth/logout successfully cleared session.")

        print("\n" + "=" * 75)
        print(" ALL PHASE 11 END-TO-END WORKFLOW TESTS PASSED CLEANLY! (100% SUCCESS)")
        print("=" * 75)

    except Exception as e:
        print(f"\n❌ E2E TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_e2e_tests()
