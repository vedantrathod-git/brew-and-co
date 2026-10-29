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

    # Step 1: Verify and retire 10 legacy items
    legacy_ids = []
    for item in LEGACY_ITEMS_TO_RETIRE:
        row = conn.execute(
            text("SELECT id, name FROM menu_items WHERE id = :id"),
            {"id": item["id"]},
        ).fetchone()
        if not row:
            raise RuntimeError(f"Expected legacy menu item ID {item['id']} ({item['name']}) not found in database.")
        if row[1] != item["name"]:
            raise RuntimeError(f"Legacy item ID {item['id']} has unexpected name '{row[1]}', expected '{item['name']}'.")
        legacy_ids.append(item["id"])

    conn.execute(
        text("UPDATE menu_items SET is_available = false WHERE id = ANY(:ids)"),
        {"ids": legacy_ids},
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

    # Revert legacy items availability
    for item in LEGACY_ITEMS_TO_RETIRE:
        avail = False if item["id"] == 29 else True
        conn.execute(
            text("UPDATE menu_items SET is_available = :avail WHERE id = :id"),
            {"avail": avail, "id": item["id"]},
        )

    # Delete 70 café items that have not been ordered
    cafe_names = [p["name"] for p in CAFE_PRODUCTS]
    conn.execute(
        text("""
            DELETE FROM menu_items
            WHERE name = ANY(:names)
              AND id NOT IN (SELECT DISTINCT menu_item_id FROM order_items)
        """),
        {"names": cafe_names},
    )

    # Delete the 9 categories if empty
    cafe_cat_names = [c["name"] for c in CAFE_CATEGORIES]
    conn.execute(
        text("""
            DELETE FROM categories
            WHERE name = ANY(:names)
              AND id NOT IN (SELECT DISTINCT category_id FROM menu_items)
        """),
        {"names": cafe_cat_names},
    )
