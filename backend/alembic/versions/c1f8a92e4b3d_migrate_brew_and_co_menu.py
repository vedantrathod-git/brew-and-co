"""migrate_brew_and_co_menu

Revision ID: c1f8a92e4b3d
Revises: 8621498a5c46
Create Date: 2026-10-22 14:55:00.000000

Phase 17B: Brew & Co. Café Menu Data Migration:
- Safely retires 10 legacy menu items by setting is_available = false
- Preserves all historical order records and price snapshots
- Creates 9 approved café categories
- Populates 70 approved café products with USD prices converted at 1 USD = 94.47 INR
"""

from typing import Sequence, Union
from alembic import op
from sqlalchemy.sql import text

from app.db.menu_data_phase17 import (
    CAFE_CATEGORIES,
    CAFE_PRODUCTS,
    LEGACY_ITEMS_TO_RETIRE,
    inr_to_usd,
)

# revision identifiers, used by Alembic.
revision: str = 'c1f8a92e4b3d'
down_revision: Union[str, Sequence[str], None] = '8621498a5c46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely retire legacy products, create 9 café categories, and insert 70 café items."""
    conn = op.get_bind()

    # Step 1: Verify and retire legacy items if they exist (safe on fresh or legacy DB)
    cafe_product_names = {p["name"] for p in CAFE_PRODUCTS}
    legacy_ids = []
    for item in LEGACY_ITEMS_TO_RETIRE:
        row = conn.execute(
            text("SELECT id, name FROM menu_items WHERE id = :id"),
            {"id": item["id"]},
        ).fetchone()
        if not row:
            # On a fresh database, legacy items do not exist — safely skip retirement
            continue
        if row[1] == item["name"]:
            # Validated: ID and name match expected legacy item
            legacy_ids.append(item["id"])
        elif row[1] in cafe_product_names:
            # On a fresh database or rerun, auto-increment assigned this ID to an approved café product
            continue
        else:
            # Unexpected item exists with this ID — reject to prevent retiring the wrong product
            raise RuntimeError(
                f"Legacy item ID {item['id']} has unexpected name '{row[1]}', expected '{item['name']}'."
            )

    if legacy_ids:
        if conn.dialect.name == "postgresql":
            conn.execute(
                text("UPDATE menu_items SET is_available = false WHERE id = ANY(:ids)"),
                {"ids": legacy_ids},
            )
        else:
            for lid in legacy_ids:
                conn.execute(
                    text("UPDATE menu_items SET is_available = false WHERE id = :id"),
                    {"id": lid},
                )

    # Step 2: Idempotently upsert 9 café categories
    category_id_map = {}
    for cat in CAFE_CATEGORIES:
        existing = conn.execute(
            text("SELECT id FROM categories WHERE name = :name"),
            {"name": cat["name"]},
        ).fetchone()
        if existing:
            category_id_map[cat["name"]] = existing[0]
            conn.execute(
                text("""
                    UPDATE categories
                    SET description = :desc, updated_at = now()
                    WHERE id = :id
                """),
                {"desc": cat["description"], "id": existing[0]},
            )
        else:
            new_id = conn.execute(
                text("""
                    INSERT INTO categories (name, description, created_at, updated_at)
                    VALUES (:name, :desc, now(), now())
                    RETURNING id
                """),
                {"name": cat["name"], "desc": cat["description"]},
            ).scalar()
            category_id_map[cat["name"]] = new_id

    # Step 3: Idempotently upsert 70 café products
    for prod in CAFE_PRODUCTS:
        cat_id = category_id_map[prod["category"]]
        usd_price = inr_to_usd(prod["inr_price"])

        existing_item = conn.execute(
            text("SELECT id, category_id, price FROM menu_items WHERE name = :name"),
            {"name": prod["name"]},
        ).fetchone()

        if existing_item:
            if existing_item[1] != cat_id:
                raise RuntimeError(
                    f"Product '{prod['name']}' already exists under conflicting category ID {existing_item[1]}, expected {cat_id}."
                )
            conn.execute(
                text("""
                    UPDATE menu_items
                    SET description = :desc,
                        price = :price,
                        prep_time_minutes = :prep,
                        is_available = true,
                        updated_at = now()
                    WHERE id = :id
                """),
                {
                    "desc": prod["description"],
                    "price": usd_price,
                    "prep": prod["prep_time_minutes"],
                    "id": existing_item[0],
                },
            )
        else:
            conn.execute(
                text("""
                    INSERT INTO menu_items (category_id, name, description, price, is_available, prep_time_minutes, created_at, updated_at)
                    VALUES (:cat_id, :name, :desc, :price, true, :prep, now(), now())
                """),
                {
                    "cat_id": cat_id,
                    "name": prod["name"],
                    "desc": prod["description"],
                    "price": usd_price,
                    "prep": prod["prep_time_minutes"],
                },
            )


def downgrade() -> None:
    """Revert café migration: restore legacy availability and remove café products."""
    conn = op.get_bind()

    # Revert legacy items availability only if they exist and match expected name
    for item in LEGACY_ITEMS_TO_RETIRE:
        avail = False if item["id"] == 29 else True
        conn.execute(
            text("UPDATE menu_items SET is_available = :avail WHERE id = :id AND name = :name"),
            {"avail": avail, "id": item["id"], "name": item["name"]},
        )

    # Delete 70 café items that have not been ordered
    cafe_names = [p["name"] for p in CAFE_PRODUCTS]
    cafe_cat_names = [c["name"] for c in CAFE_CATEGORIES]

    if conn.dialect.name == "postgresql":
        conn.execute(
            text("""
                DELETE FROM menu_items
                WHERE name = ANY(:names)
                  AND id NOT IN (SELECT DISTINCT menu_item_id FROM order_items)
            """),
            {"names": cafe_names},
        )
        # For any café items with historical order references, mark unavailable instead of deleting
        conn.execute(
            text("""
                UPDATE menu_items
                SET is_available = false
                WHERE name = ANY(:names)
            """),
            {"names": cafe_names},
        )
        # Delete the 9 categories if empty
        conn.execute(
            text("""
                DELETE FROM categories
                WHERE name = ANY(:names)
                  AND id NOT IN (SELECT DISTINCT category_id FROM menu_items)
            """),
            {"names": cafe_cat_names},
        )
    else:
        for name in cafe_names:
            conn.execute(
                text("""
                    DELETE FROM menu_items
                    WHERE name = :name
                      AND id NOT IN (SELECT DISTINCT menu_item_id FROM order_items)
                """),
                {"name": name},
            )
            conn.execute(
                text("""
                    UPDATE menu_items
                    SET is_available = false
                    WHERE name = :name
                """),
                {"name": name},
            )
        for cat_name in cafe_cat_names:
            conn.execute(
                text("""
                    DELETE FROM categories
                    WHERE name = :name
                      AND id NOT IN (SELECT DISTINCT category_id FROM menu_items)
                """),
                {"name": cat_name},
            )
