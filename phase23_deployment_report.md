# Brew & Co. — Phase 23: Production Readiness, Deployment & Launch Report

## 1. Executive Summary & Repository Audit

### A. Repository & Codebase State
- **Application Structure**: Decoupled full-stack architecture with a React 18 / Vite 5 single-page application (`frontend/`) and a Python 3.11+ / FastAPI REST API (`backend/`).
- **Data Persistence**: PostgreSQL database using SQLAlchemy 2.0 (declarative mapping) and psycopg 3 driver. Database schema revisions are managed exclusively via Alembic.
- **Payment Processing**: Razorpay Checkout sandbox integration operating in Test Mode (`rzp_test_TtkIlwY8YFcxOo`). Verified with official Razorpay API server order creation (`order_TtkK7LvePpZDh7`).
- **Git & Secret Cleanliness**:
  - Root `.gitignore` and `backend/.gitignore` properly exclude `**/.env`, `**/.env.*`, `**/*.env`, `__pycache__`, `.venv/`, and `dist/`.
  - No secret keys, passwords, or live credentials exist in Git tracked files.
  - Safe `.env.example` templates exist for both frontend and backend.

### B. Alembic Migration Chain Audit
The database schema migration tree is completely linear with a single, unambiguous head:
```
131b37bd75a0 (create initial restaurant tables)
       ↓
8621498a5c46 (create users table)
       ↓
c1f8a92e4b3d (migrate brew and co menu)
       ↓
d2e9b04f1a23 (create inventory tables)
       ↓
e5f3a21b8c47 (add qr token and idempotency key)
       ↓
f7a8b9c0d1e2 (add request fingerprint to orders)
       ↓
a1b2c3d4e5f6 (add payment tables and order payment status) [HEAD]
```
- **Migration Head**: `a1b2c3d4e5f6`
- **Safety Verification**: Startup does **not** call `Base.metadata.create_all()` or drop tables. Tables are created and evolved strictly through `alembic upgrade head`.

---

## 2. Production Security Audit

### A. Secret Management & Configuration Guardrails
`backend/app/core/config.py` enforces runtime validation inside `model_post_init` when `APP_ENV="production"`:
1. **Debug Mode Lockdown**: `DEBUG` is forced to `False`. FastAPI automatically disables interactive documentation (`/docs`, `/redoc`, and `/openapi.json`) to prevent API reconnaissance.
2. **Cookie Security**: `COOKIE_SECURE` is forced to `True`. Browsers will only transmit session cookies over HTTPS connections.
3. **JWT Secret Strength**: Production rejects default/placeholder secrets and enforces a minimum length of 32 characters.
4. **Database Placeholder Rejection**: Rejects any `DATABASE_URL` containing placeholder text (e.g., `your_password_here`).
5. **CORS Hardening**: Production rejects wildcard `*` origins and empty origin lists. Only explicit frontend domains configured in `ALLOWED_ORIGINS` are permitted.
6. **Error Message Sanitization**: `_sanitize_error_message()` in `backend/app/db/session.py` and `sanitized_database_url` in `config.py` automatically mask passwords in error strings and connection logs (`user:***@host`).

### B. Authentication, RBAC & CSRF Protection
- **Password Storage**: Passwords are hashed using `bcrypt` with a work factor of 12 rounds.
- **Session Tokens**: Signed JWTs using `HS256` with expiration set by `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 minutes / 8-hour shift).
- **Session Transport**: Stored in `HttpOnly`, `SameSite=Lax` (or `SameSite=None` when frontend/backend are on distinct domains), `Secure=True` cookies.
- **Double-Submit CSRF Defense**: State-mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`) using cookie authentication require an `X-CSRF-Token` request header matching the `restaurant_csrf_token` cookie, verified using constant-time comparison (`hmac.compare_digest`).
- **Role-Based Access Control**: Station boundaries are enforced at API dependencies:
  - `Admin`: Full system access, user management, floor plan management.
  - `Manager`: Catalog, floor plan, reports, order management (user management blocked).
  - `Cashier`: POS billing, order creation, counter cash settlement (catalog editing blocked).
  - `Kitchen`: Display view, preparation status transitions (`in_progress`, `served`). Billing and catalog blocked.
- **Administrative Account Safety**:
  - Active admin cannot delete their own user record.
  - Demoting or deactivating the last active administrator is strictly blocked.

### C. Public Customer Storefront & QR Table Safety
- **Public Menu (`GET /api/public/menu`)**: Exposes customer-safe fields only (`id`, `name`, `description`, `price`, `image_url`, `dietary_tags`). Internal margins, audit timestamps, and staff metadata are omitted.
- **QR Dining Scope Protection (`GET /api/public/orders/{order_number}`)**: Dine-in orders strictly require a valid table `qr_token` to inspect status. Customers cannot view orders belonging to other tables.
- **Authoritative Server-Side Pricing**: Order creation (`POST /api/public/orders`) re-computes subtotal, tax (5%), and total strictly from database unit prices. Client-submitted prices and totals are completely ignored.
- **Request Fingerprinting & Idempotency**: Double-clicks and duplicate submissions with the same idempotency key return the original order without creating duplicate orders or double-deducting inventory.
- **Payment Signature Verification**: Razorpay payment confirmations require valid HMAC SHA-256 signatures (`razorpay_order_id|razorpay_payment_id`). Tampered signatures are rejected with HTTP 400.
- **Webhook Ingestion**: Verified against the exact raw request body using `RAZORPAY_WEBHOOK_SECRET`. Duplicate webhook deliveries are deduplicated via `ProcessedWebhookEvent`. Out-of-order `payment.failed` webhooks never downgrade a captured payment.
- **Payment Sandbox vs. Live Isolation**: Razorpay is currently operating in Test Mode (`rzp_test_...`). Live Mode (`rzp_live_...`) is **not** enabled and requires explicit owner authorization.

---

## 3. Database & Migrations

### A. Production PostgreSQL Requirements
- **PostgreSQL Version**: 14, 15, or 16.
- **Connection Driver**: `psycopg 3` synchronous binary (`postgresql+psycopg://`).
- **Connection String Protocol**: Must include `?sslmode=require` for hosted databases (e.g. Neon, AWS RDS, Supabase).
- **Connection Pool Tuning**:
  ```python
  DATABASE_POOL_SIZE = 3        # Steady-state connections kept open
  DATABASE_MAX_OVERFLOW = 2     # Burst connections
  DATABASE_POOL_TIMEOUT = 30    # Connection acquisition timeout in seconds
  DATABASE_POOL_RECYCLE = 1800  # Recycle connections every 30 minutes
  pool_pre_ping = True          # Tests connection viability before executing queries
  ```
  *Total simultaneous connections capped at 5 (`pool_size + max_overflow`), safely within free-tier limits (e.g. Neon free tier max 10).*

### B. Non-Destructive Migration Strategy
1. **Pre-Deployment Check**:
   ```bash
   alembic current
   ```
2. **Apply Migrations**:
   ```bash
   alembic upgrade head
   ```
3. **Verify Head**:
   Ensure `alembic current` matches `a1b2c3d4e5f6`.

### C. Backup & Restore Procedures
- **Database Backup (Run before running any production migration)**:
  ```bash
  # Plain SQL dump
  pg_dump -h <host> -U <user> -d <dbname> -F p -f brew_and_co_backup_$(date +%Y%m%d_%H%M%S).sql

  # Compressed custom-format archive (recommended)
  pg_dump -h <host> -U <user> -d <dbname> -F c -b -v -f brew_and_co_backup_$(date +%Y%m%d_%H%M%S).dump
  ```
- **Database Restore**:
  ```bash
  # Restore custom-format dump to fresh database
  pg_restore -h <host> -U <user> -d <target_dbname> -v --clean --if-exists brew_and_co_backup_YYYYMMDD_HHMMSS.dump
  ```

---

## 4. Production Environment Configuration

### A. Backend Environment Variables (`backend/.env`)

| Variable | Required in Prod | Example / Recommended Value | Description |
| :--- | :---: | :--- | :--- |
| `APP_NAME` | No | `"Brew & Co. Restaurant API"` | Display name for health checks and OpenAPI |
| `APP_ENV` | **Yes** | `"production"` | Activates strict production security checks |
| `DEBUG` | **Yes** | `False` | Disables tracebacks, debug endpoints, and `/docs` |
| `PORT` | Auto | `8000` (or assigned by `$PORT`) | Web server listening port |
| `HOST` | Auto | `"0.0.0.0"` | Bind interface |
| `ALLOWED_ORIGINS` | **Yes** | `"https://brew-and-co.pages.dev,https://pos.brew-and-co.com"` | Explicit comma-separated CORS allowed origins |
| `DATABASE_URL` | **Yes** | `postgresql+psycopg://user:pass@ep-host.neon.tech/neondb?sslmode=require` | Managed PostgreSQL connection string |
| `JWT_SECRET_KEY` | **Yes** | `openssl rand -hex 32` (64 hex chars) | Cryptographic key for signing JWT tokens |
| `JWT_ALGORITHM` | No | `"HS256"` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `480` | Session lifetime (8 hours) |
| `COOKIE_SECURE` | **Yes** | `True` | Forces HTTPS-only cookies |
| `COOKIE_SAMESITE` | **Yes** | `"none"` (if cross-domain) or `"lax"` (if same-domain) | Cookie SameSite policy |
| `DATABASE_POOL_SIZE` | No | `3` | Steady-state DB pool size |
| `DATABASE_MAX_OVERFLOW` | No | `2` | Max burst DB connections |
| `RAZORPAY_KEY_ID` | **Yes** | `"rzp_test_TtkIlwY8YFcxOo"` (Test Mode) | Razorpay Public Key ID |
| `RAZORPAY_KEY_SECRET` | **Yes** | `ATEVe9ewJHRIP2T6pIcNpTwK` (Test Mode) | Razorpay Secret Key (backend-only) |
| `RAZORPAY_WEBHOOK_SECRET` | Optional | Generated webhook secret from Razorpay Dashboard | Webhook HMAC verification secret |
| `RAZORPAY_CURRENCY` | No | `"INR"` | Payment currency code |

### B. Frontend Environment Variables (`frontend/.env`)

| Variable | Required in Prod | Example Value | Description |
| :--- | :---: | :--- | :--- |
| `VITE_API_BASE_URL` | **Yes** | `"https://brew-and-co-api.onrender.com"` | Deployed backend origin. Must not have trailing slash. |

---

## 5. Deployment Architecture Evaluation

### Option 1: Managed Cloud Platform (Recommended for Zero-Maintenance & Low Cost)
- **Frontend**: **Cloudflare Pages** or **Vercel**
  - Cost: Free tier ($0/month).
  - Global edge CDN with automatic HTTPS and DDoS mitigation.
  - SPA rewrite configured via `frontend/public/_redirects` (`/* /index.html 200`) and `frontend/vercel.json`.
- **Backend**: **Render** (Web Service) or **Railway**
  - Cost: Free tier on Render ($0/month with cold starts) or Starter ($7/month without cold starts).
  - Python runtime with native FastAPI/Uvicorn support.
  - Automatic deployment blueprint provided in root [`render.yaml`](file:///c:/Users/VEDANT/Documents/new%20project/render.yaml).
  - Procfile provided in [`backend/Procfile`](file:///c:/Users/VEDANT/Documents/new%20project/backend/Procfile).
- **Database**: **Neon Serverless PostgreSQL**
  - Cost: Free tier ($0/month, 0.5 GiB storage, 10 connection limit).
  - Fully compatible with `psycopg 3` and SSL connection pooling (`sslmode=require`).
  - Total Estimated Cost: **$0.00 / month** (or **$7.00 / month** for dedicated warm backend).

### Option 2: Self-Hosted Single VPS (Hetzner, DigitalOcean, or AWS Lightsail)
- **Host**: 2 GB RAM, 1 vCPU VPS ($4.00 to $6.00 / month).
- **Stack**: Nginx reverse proxy + Gunicorn/Uvicorn systemd service + Local PostgreSQL 15 + Certbot Let's Encrypt SSL.
- **Advantage**: Zero cold starts, lower latency, single server.
- **Trade-off**: Requires manual OS updates, database backup cron jobs, and firewall management.

---

## 6. Build and Start Commands Reference

### Backend (Render / Railway / VPS)
- **Root Directory**: `backend`
- **Build Command**:
  ```bash
  pip install -r requirements.txt && alembic upgrade head
  ```
- **Start Command**:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```
- **Health Check Path**: `/health`

### Frontend (Cloudflare Pages / Vercel / Netlify)
- **Root Directory**: `frontend`
- **Build Command**:
  ```bash
  npm run build
  ```
- **Publish / Output Directory**: `dist`
- **SPA Routing Rule**: Configured in `public/_redirects` (`/* /index.html 200`) and `vercel.json`.

---

## 7. Production Verification & Test Results

### A. Automated Backend Test Suites (28 Tests Passing)
Executed via `pytest` inside `backend/`:
```text
backend/.venv/Scripts/python -m pytest test_production_readiness.py test_razorpay_unit.py -v
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0
rootdir: c:\Users\VEDANT\Documents\new project\backend
collected 28 items

test_production_readiness.py::test_production_enforces_debug_false_and_cookie_secure PASSED
test_production_readiness.py::test_production_rejects_insecure_jwt_secrets PASSED
test_production_readiness.py::test_production_rejects_placeholder_database_url PASSED
test_production_readiness.py::test_production_rejects_wildcard_cors PASSED
test_production_readiness.py::test_production_rejects_empty_cors PASSED
test_production_readiness.py::test_valid_production_configuration_succeeds PASSED
test_production_readiness.py::test_database_url_masking PASSED
test_production_readiness.py::test_payment_config_schema_never_exposes_secret PASSED
test_production_readiness.py::test_constant_time_signature_verification PASSED
test_production_readiness.py::test_fastapi_openapi_gating_in_production PASSED
test_production_readiness.py::test_alembic_single_head_consistency PASSED
test_razorpay_unit.py::test_placeholder_credentials_detection PASSED
test_razorpay_unit.py::test_missing_credentials_raises_runtime_error PASSED
test_razorpay_unit.py::test_genuine_provider_order_creation_calls_sdk PASSED
test_razorpay_unit.py::test_provider_api_failure_raises_runtime_error PASSED
test_razorpay_unit.py::test_provider_auth_failure_raises_specific_runtime_error PASSED
test_razorpay_unit.py::test_verify_payment_signature_valid PASSED
test_razorpay_unit.py::test_verify_payment_signature_tampered PASSED
test_razorpay_unit.py::test_verify_payment_signature_empty_fields PASSED
test_razorpay_unit.py::test_verify_webhook_signature PASSED
test_razorpay_unit.py::test_public_config_reports_unconfigured_when_placeholder PASSED
test_razorpay_unit.py::test_public_config_reports_configured_when_real_test_keys PASSED
test_razorpay_unit.py::test_create_guest_payment_order_unconfigured_credentials PASSED
test_razorpay_unit.py::test_create_guest_payment_order_takeaway_allowed_without_qr_token PASSED
test_razorpay_unit.py::test_create_guest_payment_order_dine_in_requires_valid_qr_token PASSED
test_razorpay_unit.py::test_create_guest_payment_order_already_paid_rejection PASSED
test_razorpay_unit.py::test_payment_retry_idempotency PASSED
test_razorpay_unit.py::test_settings_loads_razorpay_config PASSED

============================= 28 passed in 4.72s ==============================
```

### B. Frontend Production Build
Executed via `npm run build` inside `frontend/`:
```text
> restaurant-management-frontend@0.1.0 build
> vite build

vite v5.4.21 building for production...
transforming...
✓ 62 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.86 kB │ gzip:  0.50 kB
dist/assets/index-CBIWcoPx.css  116.34 kB │ gzip: 19.50 kB
dist/assets/index-BvJzZPTT.js   372.38 kB │ gzip: 95.34 kB
✓ built in 2.01s
```
- Zero errors, zero bundle warnings.
- `_redirects` file automatically copied to `dist/_redirects` for SPA route handling.

---

## 8. Post-Deployment Smoke-Test Checklist

Once deployed to staging or production, execute this verification checklist:

- [ ] **1. API Liveness Probe**: `GET /health` returns HTTP 200 `{"status": "healthy", "version": "0.1.0"}`.
- [ ] **2. Database Connectivity Probe**: `GET /health/db` returns HTTP 200 `{"status": "healthy", "result": 1}` with masked DB URL.
- [ ] **3. OpenAPI Disablement**: `GET /docs` and `GET /openapi.json` return HTTP 404 (docs disabled in production).
- [ ] **4. CORS Verification**: Cross-origin requests from the deployed frontend origin succeed; requests from unauthorized origins are rejected.
- [ ] **5. Customer Storefront**: Load `https://<frontend-domain>/menu`. Catalog displays categories and available products with USD prices.
- [ ] **6. Takeaway Cart Ordering**: Add dishes to cart, click **Place Order**, verify order confirmation ticket renders with order number.
- [ ] **7. Online Payment Checkout**: Click **Pay Online via Razorpay**, verify Razorpay modal loads with correct amount and currency.
- [ ] **8. Staff POS Login**: Log in as `cashier` or `manager` with valid credentials. Verify secure HttpOnly cookie and CSRF token are set.
- [ ] **9. Staff RBAC Gating**: As `cashier`, verify user management (`/api/users`) returns HTTP 403.
- [ ] **10. Floor Plan Management**: Verify tables and QR tokens can be viewed and managed by managers.
- [ ] **11. QR Dine-In Ordering**: Open table QR link `https://<frontend-domain>/table/<token>`, place dine-in order, confirm table number is associated.
- [ ] **12. Kitchen Display System (KDS)**: Verify new orders appear in real-time, transition status to `in_progress` and `served`.
- [ ] **13. Inventory Deduction Boundary**: Confirm inventory is deducted only when kitchen marks order `in_progress` (never on payment creation).
- [ ] **14. Counter Cash Settlement**: Cashier marks order settled with cash at POS terminal.
- [ ] **15. Razorpay Webhook Ingestion**: Submit test webhook payload from Razorpay Dashboard, verify HTTP 200 and duplicate delivery idempotency.

---

## 9. Required Owner Actions & Decision Gate

> [!IMPORTANT]
> **Production Deployment Approval Required**
> 
> Per project guidelines, automated scripts will **not** automatically provision paid cloud resources, expose the application publicly, or switch Razorpay to Live Mode without your explicit authorization.

To proceed with live deployment:
1. **Choose Deployment Platform**:
   - *Option A (Recommended)*: Cloudflare Pages / Vercel (Frontend) + Render / Railway (Backend) + Neon (PostgreSQL).
   - *Option B*: Dedicated VPS with Nginx and Docker.
2. **Provide Target Production Domains**:
   - Frontend domain (e.g., `https://brew-and-co.pages.dev` or custom domain).
   - Backend API domain (e.g., `https://brew-and-co-api.onrender.com`).
3. **Database Setup**:
   - Provision a PostgreSQL database and provide its connection URL for production secret configuration.
4. **Razorpay Live Activation (Optional)**:
   - Keep current verified Test Mode keys (`rzp_test_TtkIlwY8YFcxOo`) for staging/launch verification.
   - When ready for real customer money, complete KYC in Razorpay Dashboard to generate live keys (`rzp_live_...`).
