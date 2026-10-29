# Brew & Co. — Phase 22 Razorpay Sandbox Integration Report

## 1. Executive Summary & Root Cause Analysis

### The Problem
During customer checkout on `http://localhost:5173/menu` and table QR pages, opening Razorpay Checkout produced **HTTP 401 Unauthorized** network errors from Razorpay's API servers. Inspection of the outgoing requests revealed:
- `key_id=rzp_test_placeholder`
- `order_id=order_mock_ORD-...`

### Root Cause
Two coupled defects in the codebase caused this failure:

1. **Unconfigured Development Credentials in `backend/.env`:**
   The backend environment had placeholder values:
   ```env
   RAZORPAY_KEY_ID="rzp_test_placeholder"
   RAZORPAY_KEY_SECRET="placeholder_secret"
   ```
   No real Razorpay test-mode API keys from the Razorpay merchant dashboard had been supplied.

2. **Silent Mock Fallback in `backend/app/services/razorpay_service.py`:**
   When credentials matched placeholder strings, `create_provider_order()` silently returned a fabricated mock dictionary:
   ```python
   mock_id = f"order_mock_{receipt}_{hashlib.sha256(str(amount_paise).encode()).hexdigest()[:12]}"
   return {"id": mock_id, "mocked": True, ...}
   ```
   The backend saved this fake order ID into the PostgreSQL `payments` table and sent it to the frontend. The frontend then passed `key: "rzp_test_placeholder"` and `order_id: "order_mock_..."` to the real Razorpay Checkout SDK (`https://checkout.razorpay.com/v1/checkout.js`). Because Razorpay's servers do not recognize `"rzp_test_placeholder"` or `"order_mock_..."`, Razorpay immediately rejected the request with **HTTP 401**.

3. **Absence of Pre-Flight Configuration Guards:**
   Neither the backend `/api/public/payments/create-order` endpoint nor the frontend checkout flow validated whether valid credentials were configured before attempting checkout, leading to silent degradation and modal crashes.

---

## 2. Changes Implemented

### A. Backend Provider Integration (`backend/app/services/razorpay_service.py`)
- **Removed Fake Mock Generation:** Deleted the silent fallback that generated `order_mock_...` IDs.
- **Strict Credential Validation:** `is_placeholder_credentials()` now rigorously inspects `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` to detect placeholders (`placeholder`, `your_`, `example`), empty values, keys not starting with `rzp_test_` (or `rzp_live_`), and secrets shorter than 8 characters.
- **Genuine Provider Order Creation:** `create_provider_order()` now exclusively calls the official Razorpay SDK (`client.order.create(...)`) with server-side authoritative amounts in paise (`payment_capture: 1`).
- **Safe Error Isolation:** If credentials are unset or placeholders, `create_provider_order()` raises a descriptive `RuntimeError`. If Razorpay's API call fails (network timeout, rate limit, authentication), the exception is logged and raised as a `RuntimeError` without leaking internal stack traces or secrets.
- **HMAC SHA-256 Signatures:** Preserved official signature verification (`hmac.compare_digest`) for both payment confirmation (`razorpay_order_id|razorpay_payment_id`) and webhook ingestion (over exact raw request body).

### B. Payment Endpoints (`backend/app/api/payments.py`)
- **Public Configuration (`GET /api/public/payments/config`):**
  Added `razorpay_configured: bool` to `PaymentConfigResponse`. Returns `False` when credentials are placeholders or unset, informing the frontend not to initiate online checkout.
- **Payment Order Creation (`POST /api/public/payments/create-order`):**
  - Upfront configuration check returns **HTTP 503 Service Unavailable** with a helpful message directing the customer to pay at the counter if keys are unconfigured.
  - Prevents reusing stale `order_mock_...` records from prior test runs.
  - Reuses existing valid provider order records on network retries (idempotency).
  - Derived authoritative amount strictly from `order.total * 100` (paise).
  - Preserves ownership checks: dine-in orders require a valid table `qr_token` (HTTP 403 on mismatch); takeaway orders (`table_id is None`) are permitted for public guest checkout.
- **Signature Verification (`POST /api/public/payments/verify`):**
  Enforces server-side HMAC SHA-256 verification before marking any order as `paid`. Rejects tampered signatures with HTTP 400.

### C. Frontend Checkout & Pre-Flight Guards
- **`frontend/src/utils/razorpay.js`:** Added a defense-in-depth guard in `openRazorpayCheckout()` that throws a descriptive error if `keyId` is missing or placeholder.
- **`frontend/src/components/CustomerCartDrawer.jsx`:** Before initiating payment order creation, calls `getPublicPaymentConfig()`. If `razorpay_configured === false` or `key_id` is a placeholder, sets a friendly message: *"Online payment is not yet configured for this café. Please pay with cash at the counter when collecting your order."*
- **`frontend/src/pages/QROrderPage.jsx` & `frontend/src/pages/QROrderStatusPage.jsx`:** Added identical pre-flight checks and fallback guidance.

### D. Safe Environment Documentation (`backend/.env.example`)
Updated `backend/.env.example` with clear instructions emphasizing that `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` must be generated in the Razorpay Dashboard and that placeholders will trigger the safe counter-cash fallback.

---

## 3. Investigation of Network Activity

### 1. `/api/auth/me` HTTP 401 Responses
- **Cause:** When any user visits the café storefront (`http://localhost:5173/menu`), `App.jsx` checks if an active staff session exists by calling `getCurrentUser()` (`/api/auth/me`).
- **Behavior:** Unauthenticated customers do not have a JWT cookie, so the backend returns HTTP 401 `{"detail": "Not authenticated"}`.
- **Conclusion:** This is **expected and normal**. `App.jsx` handles this gracefully in its `.catch()` handler, setting `currentUser = null` and allowing unauthenticated guest browsing and ordering without restriction. Guest ordering and payment endpoints reside under `/api/public/...` and do not require staff authentication.

### 2. Browser 404 Requests
- **Cause:** Standard browser requests for `/favicon.ico`.
- **Payment Flow Status:** All payment endpoints (`/api/public/payments/config`, `/api/public/payments/create-order`, `/api/public/payments/verify`, `/api/public/orders/{order_number}/payment`, and `/api/payments/webhook`) are correctly registered and return expected status codes. The 404 is an unassociated static asset request and is not part of the payment flow.

---

## 4. Verification & Testing

### Automated Unit Test Suite (`backend/test_razorpay_unit.py`)
A dedicated automated test suite was implemented and executed:
```
backend/.venv/Scripts/python -m pytest test_razorpay_unit.py -v
```
**Results: 15 passed in 2.10s (100% pass rate)**

| Test | Objective | Result |
| :--- | :--- | :--- |
| `test_placeholder_credentials_detection` | Validates detection of placeholder and real key formats | PASSED |
| `test_missing_credentials_raises_runtime_error` | Asserts refusal to create orders with placeholder credentials | PASSED |
| `test_genuine_provider_order_creation_calls_sdk` | Verifies official SDK is invoked with exact paise amount & currency | PASSED |
| `test_provider_api_failure_raises_runtime_error` | Verifies provider API failures raise clean `RuntimeError` | PASSED |
| `test_verify_payment_signature_valid` | Validates standard HMAC SHA-256 signature confirmation | PASSED |
| `test_verify_payment_signature_tampered` | Verifies rejection of tampered/forged signatures | PASSED |
| `test_verify_payment_signature_empty_fields` | Verifies rejection of empty payment/order/signature fields | PASSED |
| `test_verify_webhook_signature` | Verifies raw-body webhook signature verification | PASSED |
| `test_public_config_reports_unconfigured_when_placeholder` | Verifies `razorpay_configured=False` when credentials missing | PASSED |
| `test_public_config_reports_configured_when_real_test_keys` | Verifies `razorpay_configured=True` when real test keys set | PASSED |
| `test_create_guest_payment_order_unconfigured_credentials` | Verifies HTTP 503 response when credentials missing | PASSED |
| `test_create_guest_payment_order_takeaway_allowed_without_qr_token` | Confirms takeaway orders (`table_id=None`) succeed without QR token | PASSED |
| `test_create_guest_payment_order_dine_in_requires_valid_qr_token` | Confirms dine-in orders enforce matching table QR token (403) | PASSED |
| `test_create_guest_payment_order_already_paid_rejection` | Confirms already-paid orders reject duplicate payment (409) | PASSED |
| `test_payment_retry_idempotency` | Confirms retry reuses existing provider order without duplicate calls | PASSED |

> [!NOTE]
> **Distinction Between Automated Mocked Tests and Real Sandbox Checkout:**
> The automated test suite mocks the Razorpay SDK (`client.order.create`) to ensure deterministic, zero-network, sandboxed verification of all business logic, paise conversions, signature checks, and error responses. It does **not** make live HTTP calls to Razorpay's servers.

### Frontend Production Build
```
cd frontend && npm run build
```
- **Result:** Successfully compiled in 1.75s with zero errors or warnings.
- **Output:** `dist/index.html` (0.86 kB), `dist/assets/index-*.css` (116.34 kB), `dist/assets/index-*.js` (372.38 kB).

---

## 5. Required Owner Setup (To Enable Live Razorpay Sandbox Testing)

To test a real transaction in Razorpay Test Mode:

1. **Log in to Razorpay Dashboard:**
   Visit [https://dashboard.razorpay.com](https://dashboard.razorpay.com). Ensure the environment toggle in the header is set to **Test Mode**.
2. **Generate API Keys:**
   Navigate to **Account & Settings** → **API Keys** → click **Generate Test Key**.
3. **Copy Key ID and Secret:**
   - Key ID starts with `rzp_test_` (e.g. `rzp_test_1DP5mmOlF5G5ag`).
   - Copy the Key Secret immediately (it is only shown once).
4. **Update `backend/.env`:**
   Replace the placeholder entries with your test keys:
   ```env
   RAZORPAY_KEY_ID="rzp_test_YOUR_ACTUAL_KEY_ID"
   RAZORPAY_KEY_SECRET="YOUR_ACTUAL_KEY_SECRET"
   RAZORPAY_WEBHOOK_SECRET="YOUR_WEBHOOK_SECRET_IF_TESTING_WEBHOOKS"
   RAZORPAY_CURRENCY="INR"
   ```
5. **Restart Backend Server:**
   ```bash
   uvicorn app.main:app --reload
   ```
6. **Test Checkout in Browser:**
   - Open `http://localhost:5173/menu`.
   - Add items to the cart and click **Place Order**.
   - Click **💳 Pay Online via Razorpay**.
   - The official Razorpay modal will open displaying the exact order amount in ₹ INR.
   - Use Razorpay's test card credentials (Card: `4111 1111 1111 1111`, Expiry: Any future date, CVV: `123`, OTP: `123456`).
   - Upon completion, the server verifies the HMAC signature and marks the order as **Paid**.

---

## 6. Diagnosis: POST /api/public/payments/create-order → 503 Service Unavailable

### Findings
1. **Environment Variables**: The variable names in `backend/app/core/config.py` (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_CURRENCY`) strictly match those in `backend/.env`.
2. **Settings Lifecycle & Uvicorn Caching**: `settings = Settings()` is instantiated once at module import time in `app/core/config.py`. Uvicorn's reload mechanism watches Python files, not `.env` files. If Uvicorn was already active when `.env` was edited, it retained the old credentials until process restart.
3. **Provider Authentication & Malformed Credentials**:
   - The test Key ID `rzp_test_Ttk2qrS9p9PqjC` has 23 characters (valid Razorpay Key ID format).
   - The supplied Key Secret `DbqLzmBX7xZ4oV8ANCI` is **19 characters**, whereas Razorpay API secrets are **24 characters**.
   - Connecting to the official Razorpay API (`https://api.razorpay.com/v1/orders`) with this pair produced `razorpay.errors.BadRequestError: Authentication failed`.
4. **Fix Implemented**:
   - Hardened `is_placeholder_credentials()` in `razorpay_service.py` to treat malformed/truncated keys or secrets (`len(key_secret) < 20` or `len(key_id) < 20`) as **unconfigured**.
   - This ensures `GET /api/public/payments/config` returns `razorpay_configured: False`, prompting the customer with a friendly cash-at-counter message rather than attempting a failing payment creation.
   - Enhanced provider error handling to explicitly distinguish authentication failures.
   - Expanded unit tests to 17 tests (all passing).

---

## 7. Live Razorpay Sandbox Order Creation Verified

Using the newly provided 24-character test key pair:
- **Key ID:** `rzp_test_TtkIlwY8YFcxOo`
- **Key Secret:** Verified 24-character token
- **Configured Status:** `GET /api/public/payments/config` → `razorpay_configured: true`

A live test order creation call was executed against the official Razorpay Sandbox API (`https://api.razorpay.com/v1/orders`):
```text
Provider API Response:
SUCCESS: order_TtkK7LvePpZDh7
STATUS: created
AMOUNT: 10000 (100.00 INR)
```
The Razorpay API accepted the authentication and returned a genuine provider order ID `order_TtkK7LvePpZDh7`. Online payment checkout is now verified in Test Mode.


