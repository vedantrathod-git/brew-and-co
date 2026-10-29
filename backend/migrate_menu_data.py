#!/usr/bin/env python3
"""Repeatable, idempotent migration and validation runner for Phase 17B.

Can be run via:
  python migrate_menu_data.py
Or through Alembic:
  alembic upgrade head
"""

import sys
from decimal import Decimal
from pathlib import Path
from sqlalchemy import text

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import engine, SessionLocal
from app.db.menu_data_phase17 import (
    CAFE_CATEGORIES,
    CAFE_PRODUCTS,
    LEGACY_ITEMS_TO_RETIRE,
    EXCHANGE_RATE_USD_TO_INR,
    inr_to_usd,
)


def run_migration():
    print("=" * 70)
    print(" Phase 17B: Brew & Co. Café Menu Data Migration")
    print("=" * 70)
    print(f"Target Database: {engine.url.database} on {engine.url.host}:{engine.url.port}")
    print(f"Exchange Rate:   1 USD = {EXCHANGE_RATE_USD_TO_INR} INR\n")

    db = SessionLocal()
    try:
        # Pre-migration validation
        pre_cat_count = db.execute(text("SELECT count(*) FROM categories;")).scalar()
        pre_item_count = db.execute(text("SELECT count(*) FROM menu_items;")).scalar()
        pre_order_count = db.execute(text("SELECT count(*) FROM orders;")).scalar()
        pre_order_item_count = db.execute(text("SELECT count(*) FROM order_items;")).scalar()

        print("1. Pre-Migration Database State:")
        print(f"   Categories:   {pre_cat_count}")
        print(f"   Menu Items:   {pre_item_count}")
        print(f"   Orders:       {pre_order_count}")
        print(f"   Order Items:  {pre_order_item_count}\n")

        # Step 1: Verify and retire legacy items if they exist
        print("2. Retiring Legacy Menu Items (if present, setting is_available = False)...")
        cafe_product_names = {p["name"] for p in CAFE_PRODUCTS}
        retired_count = 0
        skipped_count = 0
        for item in LEGACY_ITEMS_TO_RETIRE:
            row = db.execute(
                text("SELECT id, name, price, is_available FROM menu_items WHERE id = :id"),
                {"id": item["id"]},
            ).fetchone()
            if not row:
                print(f"   - Legacy ID {item['id']:2d}: {item['name']:<28} (Not present on fresh DB — skipping)")
                skipped_count += 1
                continue
            if row[1] == item["name"]:
                db.execute(
                    text("UPDATE menu_items SET is_available = false WHERE id = :id"),
                    {"id": item["id"]},
                )
                retired_count += 1
                print(f"   ✓ Retired ID {item['id']:2d}: {item['name']:<28} (Price: {row[2]})")
            elif row[1] in cafe_product_names:
                print(f"   - ID {item['id']:2d} is café product '{row[1]}' (Rerun on fresh DB — skipping)")
                skipped_count += 1
                continue
            else:
                raise RuntimeError(f"Legacy item ID {item['id']} has name '{row[1]}', expected '{item['name']}'.")

        print(f"   Total retired: {retired_count}, Skipped (not present / café product): {skipped_count}\n")

        # Step 2: Idempotently upsert 9 café categories
        print("\n3. Creating / Verifying 9 Approved Café Categories...")
        category_id_map = {}
        for cat in CAFE_CATEGORIES:
            existing = db.execute(
                text("SELECT id FROM categories WHERE name = :name"),
                {"name": cat["name"]},
            ).fetchone()
            if existing:
                category_id_map[cat["name"]] = existing[0]
                print(f"   ✓ Category exists:  {cat['name']:<32} (ID: {existing[0]})")
            else:
                new_id = db.execute(
                    text("""
                        INSERT INTO categories (name, description, created_at, updated_at)
                        VALUES (:name, :desc, now(), now())
                        RETURNING id
                    """),
                    {"name": cat["name"], "desc": cat["description"]},
                ).scalar()
                category_id_map[cat["name"]] = new_id
                print(f"   + Created Category: {cat['name']:<32} (ID: {new_id})")

        # Step 3: Idempotently upsert 70 café products
        print("\n4. Upserting 70 Approved Café Products...")
        inserted_count = 0
        updated_count = 0
        for prod in CAFE_PRODUCTS:
            cat_id = category_id_map[prod["category"]]
            usd_price = inr_to_usd(prod["inr_price"])

            existing_item = db.execute(
                text("SELECT id, category_id, price FROM menu_items WHERE name = :name"),
                {"name": prod["name"]},
            ).fetchone()

            if existing_item:
                if existing_item[1] != cat_id:
                    raise RuntimeError(
                        f"Product '{prod['name']}' already exists under conflicting category ID {existing_item[1]}, expected {cat_id}."
                    )
                db.execute(
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
                updated_count += 1
            else:
                db.execute(
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
                inserted_count += 1

        print(f"   ✓ Products Upsert Completed: {inserted_count} inserted, {updated_count} updated.")

        # Commit transaction
        db.commit()
        print("\n5. Transaction Committed Cleanly.")

        # Mark alembic revision if needed
        current_rev = db.execute(text("SELECT version_num FROM alembic_version;")).scalar()
        if current_rev != "c1f8a92e4b3d":
            db.execute(text("UPDATE alembic_version SET version_num = 'c1f8a92e4b3d';"))
            db.commit()
            print("   ✓ Alembic version synchronized to 'c1f8a92e4b3d'.")

        # Post-migration verification
        print("\n6. Post-Migration Verification Checks:")
        post_cat_count = db.execute(text("SELECT count(*) FROM categories;")).scalar()
        post_item_count = db.execute(text("SELECT count(*) FROM menu_items;")).scalar()
        post_order_count = db.execute(text("SELECT count(*) FROM orders;")).scalar()
        post_order_item_count = db.execute(text("SELECT count(*) FROM order_items;")).scalar()

        print(f"   Total Categories: {post_cat_count} (Expected 14 = 5 legacy + 9 café)")
        print(f"   Total Menu Items: {post_item_count} (Expected 80 = 10 legacy + 70 café)")
        print(f"   Total Orders:     {post_order_count} (Preserved: {post_order_count == pre_order_count})")
        print(f"   Order Items:      {post_order_item_count} (Preserved: {post_order_item_count == pre_order_item_count})")

        assert post_cat_count == 14, f"Categories count mismatch: {post_cat_count} != 14"
        assert post_item_count == 80, f"Menu items count mismatch: {post_item_count} != 80"
        assert post_order_count == pre_order_count, "Order count changed during migration!"
        assert post_order_item_count == pre_order_item_count, "Order items count changed during migration!"

        # Verify all 10 legacy items are unavailable
        legacy_unavail_count = db.execute(
            text("SELECT count(*) FROM menu_items WHERE id = ANY(:ids) AND is_available = false;"),
            {"ids": [item["id"] for item in LEGACY_ITEMS_TO_RETIRE]},
        ).scalar()
        assert legacy_unavail_count == 10, f"Expected 10 unavailable legacy items, got {legacy_unavail_count}"
        print("   ✓ All 10 legacy items confirmed retired (is_available = false).")

        # Verify all 70 café items are available with positive prices
        cafe_names = [p["name"] for p in CAFE_PRODUCTS]
        cafe_avail_count = db.execute(
            text("SELECT count(*) FROM menu_items WHERE name = ANY(:names) AND is_available = true AND price > 0;"),
            {"names": cafe_names},
        ).scalar()
        assert cafe_avail_count == 70, f"Expected 70 available café items, got {cafe_avail_count}"
        print("   ✓ Exactly 70 new café products active with valid positive USD prices.")

        # Verify category distribution
        print("\n7. Category Product Distribution:")
        for cat in CAFE_CATEGORIES:
            count = db.execute(
                text("""
                    SELECT count(m.id)
                    FROM menu_items m
                    JOIN categories c ON m.category_id = c.id
                    WHERE c.name = :cname AND m.is_available = true
                """),
                {"cname": cat["name"]},
            ).scalar()
            print(f"   - {cat['name']:<30}: {count:2d} products (Expected {cat['target_count']})")
            assert count == cat["target_count"], f"Distribution mismatch for '{cat['name']}': {count} != {cat['target_count']}"

        print("\n" + "=" * 70)
        print(" PHASE 17B MIGRATION & VALIDATION PASSED 100% SUCCESSFULLY!")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n❌ MIGRATION FAILED — TRANSACTION ROLLED BACK: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
