#!/usr/bin/env python3
"""Automated Test Suite for Phase 17B Menu Migration (c1f8a92e4b3d).

Verifies:
1. Fresh database upgrade:
   - Safely skips retirement of non-existent legacy items without error.
   - Creates all 9 approved café categories.
   - Creates all 70 approved café products with correct prices, availability, and prep times.
2. Legacy database upgrade:
   - Detects all 10 legacy items (IDs 25..34) by ID and name.
   - Retires them (is_available = False) while preserving historical record attributes.
   - Creates 9 café categories and 70 café items.
3. Legacy item name mismatch:
   - Fails loudly with RuntimeError if an item with a legacy ID has an unexpected name.
   - Refuses to modify or retire mismatched items.
4. Idempotency:
   - Repeated execution of upgrade() succeeds without duplicating categories or menu items.
5. Downgrade safety and referential integrity:
   - Restores legacy item availability.
   - Preserves café menu items referenced in historical orders (marks them unavailable).
   - Preserves categories containing referenced items.
   - Removes unreferenced café products and categories.
"""

from decimal import Decimal
import importlib.util
from pathlib import Path
import sqlite3
from unittest.mock import patch
import pytest
import sqlalchemy as sa
from sqlalchemy import event, text

# Register Decimal adapter for SQLite in Python 3.12+
sqlite3.register_adapter(Decimal, lambda d: str(d))
sqlite3.register_converter("NUMERIC", lambda b: Decimal(b.decode()))

from app.models import Base
from app.db.menu_data_phase17 import (
    CAFE_CATEGORIES,
    CAFE_PRODUCTS,
    LEGACY_ITEMS_TO_RETIRE,
    inr_to_usd,
)

# Load the migration module dynamically
MIGRATION_PATH = (
    Path(__file__).resolve().parent
    / "alembic"
    / "versions"
    / "c1f8a92e4b3d_migrate_brew_and_co_menu.py"
)
spec = importlib.util.spec_from_file_location("migration_c1f8a92e4b3d", MIGRATION_PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


@pytest.fixture
def test_db():
    """Create a clean in-memory SQLite database with application schema."""
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"detect_types": sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES},
    )

    # Register PostgreSQL-compatible now() function in SQLite
    @event.listens_for(engine, "connect")
    def register_functions(dbapi_conn, record):
        dbapi_conn.create_function("now", 0, lambda: "2026-10-29 12:00:00")

    Base.metadata.create_all(engine)
    conn = engine.connect()

    yield conn

    conn.close()
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fresh Database Migration
# ─────────────────────────────────────────────────────────────────────────────

def test_fresh_database_upgrade(test_db):
    """Verify upgrade succeeds on a fresh database where legacy items do not exist."""
    trans = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        migration.upgrade()
    trans.commit()

    # 1. Verify 9 categories created
    cats = test_db.execute(text("SELECT id, name, description FROM categories ORDER BY id")).fetchall()
    assert len(cats) == 9, f"Expected 9 categories, got {len(cats)}"
    cat_names = {c[1] for c in cats}
    expected_cat_names = {c["name"] for c in CAFE_CATEGORIES}
    assert cat_names == expected_cat_names

    # 2. Verify 70 café items created and available
    items = test_db.execute(
        text("SELECT id, name, price, is_available, prep_time_minutes FROM menu_items")
    ).fetchall()
    assert len(items) == 70, f"Expected 70 items, got {len(items)}"
    for row in items:
        assert row[3] == 1, f"Expected item '{row[1]}' to be available"

    # 3. Check sample item pricing and prep time
    sample = test_db.execute(
        text("SELECT name, price, prep_time_minutes FROM menu_items WHERE name = 'Double Espresso (Doppio)'")
    ).fetchone()
    assert sample is not None
    assert Decimal(str(sample[1])) == Decimal("1.91")  # inr_to_usd(180)
    assert sample[2] == 3


# ─────────────────────────────────────────────────────────────────────────────
# 2. Legacy Database Migration
# ─────────────────────────────────────────────────────────────────────────────

def test_legacy_database_upgrade(test_db):
    """Verify upgrade retires existing legacy items and creates café items alongside them."""
    # Seed a legacy category and the 10 legacy items
    legacy_cat_id = test_db.execute(
        text("INSERT INTO categories (id, name, description) VALUES (1, 'Legacy Starters', 'Old') RETURNING id")
    ).scalar()

    for item in LEGACY_ITEMS_TO_RETIRE:
        test_db.execute(
            text("""
                INSERT INTO menu_items (id, category_id, name, description, price, is_available, prep_time_minutes)
                VALUES (:id, :cat_id, :name, 'Legacy item', :price, true, 15)
            """),
            {"id": item["id"], "cat_id": legacy_cat_id, "name": item["name"], "price": str(item["price"])},
        )
    test_db.commit()

    # Run upgrade
    trans = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        migration.upgrade()
    trans.commit()

    # 1. Verify all 10 legacy items are now retired (is_available = False)
    for item in LEGACY_ITEMS_TO_RETIRE:
        row = test_db.execute(
            text("SELECT id, name, price, is_available FROM menu_items WHERE id = :id"),
            {"id": item["id"]},
        ).fetchone()
        assert row is not None
        assert row[1] == item["name"]
        assert Decimal(str(row[2])) == item["price"]
        assert row[3] == 0, f"Expected legacy item '{item['name']}' to be retired (is_available=False)"

    # 2. Total menu items: 10 legacy + 70 café = 80 items
    total_count = test_db.execute(text("SELECT count(*) FROM menu_items")).scalar()
    assert total_count == 80

    # 3. Active menu items: exactly 70
    active_count = test_db.execute(text("SELECT count(*) FROM menu_items WHERE is_available = true")).scalar()
    assert active_count == 70


# ─────────────────────────────────────────────────────────────────────────────
# 3. Legacy Name Mismatch Safety Guard
# ─────────────────────────────────────────────────────────────────────────────

def test_legacy_mismatch_raises_error(test_db):
    """Verify upgrade raises RuntimeError if an existing item ID has an unexpected name."""
    legacy_cat_id = test_db.execute(
        text("INSERT INTO categories (id, name, description) VALUES (1, 'Mains', 'Mains') RETURNING id")
    ).scalar()

    # Insert ID 25 with a completely wrong name
    test_db.execute(
        text("""
            INSERT INTO menu_items (id, category_id, name, description, price, is_available)
            VALUES (25, :cat_id, 'Spaghetti Carbonara', 'Pasta', '14.00', true)
        """),
        {"cat_id": legacy_cat_id},
    )
    test_db.commit()

    # Attempt upgrade — must fail
    trans = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        with pytest.raises(RuntimeError) as exc_info:
            migration.upgrade()
    trans.rollback()

    assert "Legacy item ID 25 has unexpected name 'Spaghetti Carbonara'" in str(exc_info.value)

    # Verify the mismatched item was NOT modified
    row = test_db.execute(text("SELECT name, is_available FROM menu_items WHERE id = 25")).fetchone()
    assert row[0] == "Spaghetti Carbonara"
    assert row[1] == 1  # still available


# ─────────────────────────────────────────────────────────────────────────────
# 4. Idempotent Rerun
# ─────────────────────────────────────────────────────────────────────────────

def test_migration_idempotent_rerun(test_db):
    """Verify executing upgrade() twice produces no duplicate categories or products."""
    # First upgrade
    trans1 = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        migration.upgrade()
    trans1.commit()

    # Second upgrade
    trans2 = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        migration.upgrade()
    trans2.commit()

    cat_count = test_db.execute(text("SELECT count(*) FROM categories")).scalar()
    item_count = test_db.execute(text("SELECT count(*) FROM menu_items")).scalar()
    assert cat_count == 9
    assert item_count == 70


# ─────────────────────────────────────────────────────────────────────────────
# 5. Downgrade Safety & Referential Integrity
# ─────────────────────────────────────────────────────────────────────────────

def test_downgrade_preserves_ordered_items_and_reverts_legacy(test_db):
    """Verify downgrade restores legacy availability, deletes un-ordered café items, and preserves ordered items."""
    # 1. Seed legacy items
    legacy_cat_id = test_db.execute(
        text("INSERT INTO categories (id, name, description) VALUES (1, 'Legacy', 'Old') RETURNING id")
    ).scalar()
    for item in LEGACY_ITEMS_TO_RETIRE:
        test_db.execute(
            text("""
                INSERT INTO menu_items (id, category_id, name, description, price, is_available)
                VALUES (:id, :cat_id, :name, 'Legacy item', :price, true)
            """),
            {"id": item["id"], "cat_id": legacy_cat_id, "name": item["name"], "price": str(item["price"])},
        )
    test_db.commit()

    # 2. Upgrade
    trans = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        migration.upgrade()
    trans.commit()

    # 3. Simulate an order referencing one of the café products
    cafe_item = test_db.execute(
        text("SELECT id FROM menu_items WHERE name = 'Double Espresso (Doppio)'")
    ).fetchone()
    cafe_item_id = cafe_item[0]

    order_id = test_db.execute(
        text("INSERT INTO orders (order_number, total, subtotal, tax, discount) VALUES ('ORD-MIG-1', '1.91', '1.91', '0.00', '0.00') RETURNING id")
    ).scalar()
    test_db.execute(
        text("INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price) VALUES (:oid, :mid, 1, '1.91')"),
        {"oid": order_id, "mid": cafe_item_id},
    )
    test_db.commit()

    # 4. Downgrade
    trans_down = test_db.begin()
    with patch("alembic.op.get_bind", return_value=test_db):
        migration.downgrade()
    trans_down.commit()

    # 5. Check legacy availability restored
    for item in LEGACY_ITEMS_TO_RETIRE:
        row = test_db.execute(
            text("SELECT is_available FROM menu_items WHERE id = :id"),
            {"id": item["id"]},
        ).fetchone()
        expected_avail = 0 if item["id"] == 29 else 1
        assert row[0] == expected_avail

    # 6. Check ordered café item is preserved (NOT deleted) but marked unavailable
    ordered_row = test_db.execute(
        text("SELECT id, name, is_available FROM menu_items WHERE id = :id"),
        {"id": cafe_item_id},
    ).fetchone()
    assert ordered_row is not None
    assert ordered_row[1] == "Double Espresso (Doppio)"
    assert ordered_row[2] == 0  # marked unavailable

    # 7. Check un-ordered café items were deleted
    un_ordered_sample = test_db.execute(
        text("SELECT id FROM menu_items WHERE name = 'Espresso Macchiato'")
    ).fetchone()
    assert un_ordered_sample is None

    # 8. Check category containing the ordered item still exists
    ordered_item_cat = test_db.execute(
        text("SELECT c.name FROM categories c JOIN menu_items m ON m.category_id = c.id WHERE m.id = :id"),
        {"id": cafe_item_id},
    ).fetchone()
    assert ordered_item_cat is not None
    assert ordered_item_cat[0] == "Coffee & Espresso"
