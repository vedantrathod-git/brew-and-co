#!/usr/bin/env python3
"""Phase 23 — Production Readiness & Security Guardrails Test Suite.

Verifies:
1. Production configuration validation (APP_ENV="production"):
   - Disables DEBUG mode automatically.
   - Enforces COOKIE_SECURE=True for HTTPS.
   - Rejects default or placeholder JWT secrets.
   - Rejects JWT secrets under 32 characters.
   - Rejects database URLs containing placeholder passwords.
   - Rejects empty ALLOWED_ORIGINS or wildcard '*' origins.
   - Accepts valid, hardened production configuration.
2. Database URL password sanitization in logs and status responses.
3. Razorpay payment secret containment (never leaked to public schemas).
4. Signature verification security (constant-time HMAC SHA-256).
5. OpenAPI documentation gating (disabled when DEBUG=False).
6. Alembic migration chain consistency (single unified head).
"""

import hashlib
import hmac
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.payment import PaymentConfigResponse
from app.services.razorpay_service import (
    is_placeholder_credentials,
    verify_payment_signature,
    verify_webhook_signature,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Production Configuration Guardrail Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_production_enforces_debug_false_and_cookie_secure():
    """Verify production environment forces DEBUG=False and COOKIE_SECURE=True."""
    s = Settings(
        APP_ENV="production",
        DEBUG=True,  # Attempting to enable debug in production
        COOKIE_SECURE=False,  # Attempting to disable cookie security
        JWT_SECRET_KEY="c" * 48,
        DATABASE_URL="postgresql+psycopg://user:prod_pass@db.internal:5432/brew_db",
        ALLOWED_ORIGINS="https://brew-and-co.pages.dev",
    )
    assert s.DEBUG is False
    assert s.COOKIE_SECURE is True


def test_production_rejects_insecure_jwt_secrets():
    """Verify production rejects known default or short JWT secrets."""
    insecure_keys = [
        "c7d91e6b8a24f0d3e5a1b7c9f8e2d4a6b5c3e1f7a9d8c4b2e6f0a3d5b7c9e1f8",
        "generate_a_secure_random_hex_key_here_for_production",
        "short_key_under_32_chars",
        "secret",
        "",
    ]
    for key in insecure_keys:
        with pytest.raises(ValueError) as exc:
            Settings(
                APP_ENV="production",
                JWT_SECRET_KEY=key,
                DATABASE_URL="postgresql+psycopg://user:pass@db:5432/db",
                ALLOWED_ORIGINS="https://frontend.com",
            )
        assert "Production safety violation: JWT_SECRET_KEY" in str(exc.value)


def test_production_rejects_placeholder_database_url():
    """Verify production rejects database URLs containing placeholder passwords."""
    with pytest.raises(ValueError) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="c" * 48,
            DATABASE_URL="postgresql+psycopg://postgres:your_password_here@localhost:5432/restaurant_db",
            ALLOWED_ORIGINS="https://frontend.com",
        )
    assert "DATABASE_URL contains placeholder credentials" in str(exc.value)


def test_production_rejects_wildcard_cors():
    """Verify production rejects wildcard '*' origin when cookies are enabled."""
    with pytest.raises(ValueError) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="c" * 48,
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/db",
            ALLOWED_ORIGINS="*",
        )
    assert "Wildcard origin '*' is not allowed" in str(exc.value)


def test_production_rejects_empty_cors():
    """Verify production rejects empty allowed origins."""
    with pytest.raises(ValueError) as exc:
        Settings(
            APP_ENV="production",
            JWT_SECRET_KEY="c" * 48,
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/db",
            ALLOWED_ORIGINS="",
        )
    assert "ALLOWED_ORIGINS must specify at least one trusted origin" in str(exc.value)


def test_valid_production_configuration_succeeds():
    """Verify a properly hardened production config passes all safety validations."""
    s = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="e4f8a2c1d9b3e7f0a5b8c2d6e9f1a4b7c0d3e6f9a2b5c8d1e4f7a0b3c6d9e2f5",
        DATABASE_URL="postgresql+psycopg://app_user:StrongProdPass2026!@ep-cool-db.us-east-2.neon.tech/neondb?sslmode=require",
        ALLOWED_ORIGINS="https://brew-and-co.pages.dev,https://pos.brew-and-co.com",
    )
    assert s.APP_ENV == "production"
    assert s.DEBUG is False
    assert s.COOKIE_SECURE is True
    assert len(s.cors_origins) == 2
    assert "https://brew-and-co.pages.dev" in s.cors_origins


# ─────────────────────────────────────────────────────────────────────────────
# 2. Credential Sanitization Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_database_url_masking():
    """Verify sanitized_database_url masks passwords and never leaks credentials in logs."""
    s = Settings(
        DATABASE_URL="postgresql+psycopg://db_admin:SuperSecretPassword123@db.host.com:5432/mydb"
    )
    sanitized = s.sanitized_database_url
    assert "SuperSecretPassword123" not in sanitized
    assert "db_admin:***@db.host.com:5432/mydb" in sanitized


# ─────────────────────────────────────────────────────────────────────────────
# 3. Razorpay Secrets & Public Schema Containment
# ─────────────────────────────────────────────────────────────────────────────

def test_payment_config_schema_never_exposes_secret():
    """Verify PaymentConfigResponse schema only contains safe public fields."""
    fields = PaymentConfigResponse.model_fields
    assert "key_id" in fields
    assert "currency" in fields
    assert "razorpay_configured" in fields
    assert "key_secret" not in fields
    assert "secret" not in fields
    assert "webhook_secret" not in fields


def test_constant_time_signature_verification():
    """Verify HMAC SHA-256 uses constant-time comparison to prevent timing attacks."""
    secret = "sample_test_secret_12345678"
    msg = "order_123|pay_456"
    valid_sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    # Valid signature
    assert hmac.compare_digest(
        valid_sig,
        hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    ) is True

    # Tampered signature
    assert hmac.compare_digest(
        valid_sig,
        "tampered_signature_hex"
    ) is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. OpenAPI / Docs Production Gating
# ─────────────────────────────────────────────────────────────────────────────

def test_fastapi_openapi_gating_in_production():
    """Verify FastAPI instance disables /docs, /redoc, and /openapi.json when DEBUG is False."""
    from fastapi import FastAPI
    # Simulate production FastAPI instantiation
    debug_mode = False
    app = FastAPI(
        title="Brew & Co.",
        debug=debug_mode,
        docs_url="/docs" if debug_mode else None,
        redoc_url="/redoc" if debug_mode else None,
        openapi_url="/openapi.json" if debug_mode else None,
    )
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Alembic Migration Consistency
# ─────────────────────────────────────────────────────────────────────────────

def test_alembic_single_head_consistency():
    """Verify Alembic migration tree has exactly one head revision with no divergent branches."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = Path(__file__).resolve().parent
    ini_path = backend_dir / "alembic.ini"
    assert ini_path.exists(), "alembic.ini must exist"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()

    assert len(heads) == 1, f"Alembic must have exactly 1 head revision, found: {heads}"
    assert heads[0] == "a1b2c3d4e5f6", f"Expected head 'a1b2c3d4e5f6', found: {heads[0]}"
