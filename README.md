# Restaurant Management & POS Suite

A robust, full-stack Restaurant Management System built with **React 18 + Vite** on the frontend and **FastAPI + SQLAlchemy 2.0 + PostgreSQL** on the backend. Designed for high concurrency, strict state-machine compliance, transactional table management, comprehensive Role-Based Access Control (RBAC), and USD food photography displays.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite 5, Vanilla CSS Design System (Warm Ivory / Navy Blue / Terracotta) |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2 |
| **ORM & Migrations** | SQLAlchemy 2.0 (Declarative), Alembic |
| **Database** | PostgreSQL 14+ with `psycopg 3` driver |
| **Security** | bcrypt password hashing, JWT session cookies (HttpOnly, SameSite=Lax), Double-Submit CSRF protection |
| **Pricing & Images** | Centralized USD formatter (`formatUSD`), CDN-hosted food photography with graceful SVG fallbacks |

---

## Station Roles & RBAC Matrix

The system enforces strict station boundaries at both frontend navigation and backend API endpoints:

| Feature / Endpoint | Admin | Manager | Cashier | Kitchen |
|---|:---:|:---:|:---:|:---:|
| **User Management** (`/api/users`) | Full CRUD | Blocked (403) | Blocked (403) | Blocked (403) |
| **Menu Catalog** (`/api/categories`, `/api/menu-items`) | Full CRUD | Full CRUD | Read-Only | Read-Only |
| **Floor Plan** (`/api/tables`) | Full CRUD | Full CRUD | Read-Only | Read-Only |
| **POS Terminal** (`POST /api/orders`) | Create Orders | Create Orders | Create Orders | Blocked (403) |
| **Order History & Audit** (`GET /api/orders`) | Full Access | Full Access | Full Access | Full Access |
| **Kitchen Display** (`PUT /api/orders/{id}`) | Full Access | Full Access | Cashier Actions | Prep Transitions Only (`in_progress`, `served`) |
| **Order Billing Completion** (`PUT status='completed'`) | Yes | Yes | Yes | Blocked (403) |
| **Order Deletion** (`DELETE /api/orders/{id}`) | Pending Only | Pending Only | Blocked (403) | Blocked (403) |
| **Executive Dashboard** (`/api/dashboard`) | View Metrics | View Metrics | Blocked (Nav) | Blocked (Nav) |

---

## Local Development Setup

### 1. Prerequisites
- **Python**: 3.11 or later
- **Node.js**: 18.0 or later with `npm`
- **PostgreSQL**: 14 or later running locally

### 2. Backend Setup
1. Navigate to the `backend` directory:
   ```powershell
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   Copy `.env.example` to `.env` and set local PostgreSQL credentials:
   ```powershell
   Copy-Item .env.example .env
   ```
5. Run Alembic database migrations:
   ```powershell
   alembic upgrade head
   ```
6. Provision the initial Administrator account:
   ```powershell
   python create_admin.py --username admin --email admin@restaurant.pos --role admin
   ```
   *(Prompts securely for a password meeting minimum complexity rules).*
7. Start the FastAPI development server:
   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   API interactive documentation is available at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
1. Open a new terminal and navigate to the `frontend` directory:
   ```powershell
   cd frontend
   ```
2. Install npm dependencies:
   ```powershell
   npm install
   ```
3. Start the Vite development server:
   ```powershell
   npm run dev
   ```
4. Access the web application in your browser at `http://localhost:5173`.

---

## Production Deployment Checklist & Architecture

Follow this step-by-step checklist when preparing for production deployment.

### 1. Environment Variables Reference

#### Backend Variables (`backend/.env`)
| Variable | Type | Production Requirement | Example / Purpose |
|---|:---:|---|---|
| `APP_ENV` | `string` | **Must be `"production"`** | Activates production security guardrails. |
| `DEBUG` | `bool` | **Must be `False`** | Disables debug stack traces & hides public `/docs`. |
| `HOST` | `string` | `"0.0.0.0"` or internal IP | Binds to all network interfaces. |
| `PORT` | `int` | `8000` (or platform port) | Port for Uvicorn / Gunicorn. |
| `ALLOWED_ORIGINS` | `string` | **Explicit domains only** (No `*`) | `https://pos.yourrestaurant.com` |
| `DATABASE_URL` | `string` | **Production PostgreSQL URL** | `postgresql+psycopg://user:pass@prod-db.internal:5432/restaurant_db` |
| `JWT_SECRET_KEY` | `string` | **Min 32 random characters** | Generate via `openssl rand -hex 32`. |
| `JWT_ALGORITHM` | `string` | `"HS256"` | Standard JWT algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `480` | Shift session length (8 hours). |
| `COOKIE_SECURE` | `bool` | **Enforced `True` in production** | Requires HTTPS for session cookie transmission. |
| `COOKIE_SAMESITE` | `string` | `"lax"` | CSRF defense & cross-site request policy. |

#### Frontend Variables (`frontend/.env` or build-time env)
| Variable | Production Requirement | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | Set to API domain (or empty if reverse proxy routes `/api`) | Configures base URL for API requests. |
| `VITE_ENABLE_DEMO_LOGIN` | **Leave unset or `false`** | Strictly disabled in production builds. |

---

### 2. Production Database Provisioning & Migrations
1. Ensure the PostgreSQL 14+ database instance is provisioned with SSL enabled (`sslmode=require`).
2. Run database migrations to bring the schema to `head`:
   ```bash
   alembic upgrade head
   ```
   *Note: Never drop or truncate existing tables during deployment. All migrations are fully non-destructive.*
3. Verify connection health:
   ```bash
   python -c "from app.db.session import check_db_connection; print(check_db_connection())"
   ```

---

### 3. Initial Administrator Provisioning
Create the production system administrator account interactively (passwords are masked in terminal and hashed with bcrypt):
```bash
python create_admin.py --username admin --email admin@yourrestaurant.com --role admin
```
Additional staff accounts (Managers, Cashiers, Kitchen Line Cooks) can then be provisioned securely via the **User Accounts & Roles** station in the web UI.

---

### 4. Backend Production Process (Gunicorn + Uvicorn)
For high-concurrency production deployments on Linux, run Uvicorn workers managed by Gunicorn:
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --access-logfile - --error-logfile -
```
For single-container or Windows deployments:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

### 5. Frontend Production Build & Static Serving
Compile the React frontend into optimized static assets:
```bash
cd frontend
npm ci
npm run build
```
- Assets are generated in `frontend/dist/`.
- Serve the `dist/` folder via a high-performance web server (Cloudflare Pages, Vercel, Netlify, or Nginx).
- Ensure the server serves `index.html` for single-page app (SPA) fallback routes (configured via `public/_redirects` and `vercel.json`).

#### Option A: Managed Cloud Deployment (Render + Cloudflare Pages / Vercel + Neon)
1. **Database (Neon Serverless PostgreSQL):**
   - Create a free project on [neon.tech](https://neon.tech).
   - Copy connection string with `sslmode=require` (psycopg 3 format: `postgresql+psycopg://user:pass@ep-xyz.region.neon.tech/neondb?sslmode=require`).
2. **Backend (Render Web Service):**
   - Connect Git repository on [render.com](https://render.com).
   - Set Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt && alembic upgrade head`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/health`
   - Add production environment variables (see `backend/.env.example`).
3. **Frontend (Cloudflare Pages / Vercel):**
   - Connect Git repository.
   - Build Command: `npm run build`
   - Build Output Directory: `dist`
   - Root Directory: `frontend`
   - Environment Variable: `VITE_API_BASE_URL=https://your-backend-api.onrender.com`

#### Option B: Self-Hosted Nginx Reverse Proxy Configuration:
```nginx
server {
    listen 443 ssl http2;
    server_name pos.yourrestaurant.com;

    ssl_certificate /etc/letsencrypt/live/pos.yourrestaurant.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pos.yourrestaurant.com/privkey.pem;

    # Static Frontend Assets
    location / {
        root /var/www/restaurant-frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API Proxy to FastAPI Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Health Checks
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
```

---

### 6. Production Health Check & Monitoring
- **Liveness Probe**: `GET /health` $\rightarrow$ returns `{"status": "healthy", "version": "0.1.0"}` (HTTP 200).
- **Readiness / DB Probe**: `GET /health/db` $\rightarrow$ verifies active database connection via `SELECT 1` without exposing raw credentials.

---

## Automated Verification & Test Suites

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# 1. Complete End-to-End Workflow Verification
python test_e2e_workflow.py

# 2. RBAC, JWT, CSRF & Security Matrix Suite
python test_auth_rbac.py

# 3. Reliability, Row-Locking & State Machine Suite
python test_phase4_reliability.py

# 4. Orders API Tests
python test_orders_api.py

# 5. Catalog & Floor Plan Tests
python test_categories_api.py
python test_menu_items_api.py
python test_tables_api.py
```

### Frontend Test & Build Verification
```powershell
cd frontend

# Run USD Formatter & Dish Image Resolution Test
node test_phase12_usd_images.js

# Run Production Build
npm run build
```

---

## Security Architecture Highlights

1. **Double-Submit CSRF**: Any state-mutating HTTP request (`POST`, `PUT`, `DELETE`, `PATCH`) authenticated via cookies must present a matching `X-CSRF-Token` header corresponding to the `restaurant_csrf_token` cookie.
2. **HttpOnly Session Cookies**: Session tokens are stored in HttpOnly cookies inaccessible to browser JavaScript.
3. **Production Safety Guardrails**: Startup fails immediately if `APP_ENV="production"` is used with default/placeholder JWT secrets, keys under 32 characters, wildcard CORS origins, or placeholder database credentials.
4. **Admin Self-Deletion Safeguard**: An administrator cannot delete their own active account.
5. **Last Active Admin Protection**: The system prevents deactivating or demoting the last active administrator in the database.
6. **No Credential Leakage**: `hashed_password` fields are strictly omitted from all Pydantic response models, and database error messages automatically mask credentials.
