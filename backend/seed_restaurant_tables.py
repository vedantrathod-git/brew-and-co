#!/usr/bin/env python3
"""Safe, idempotent script to seed initial dining tables for Brew & Co.

Rules:
- Never deletes or drops existing records.
- Checks each table_number (case-insensitive) to avoid duplicates.
- Preserves existing order relationships and table occupancy.
- Safe to run repeatedly.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.session import SessionLocal
from app.models.table import RestaurantTable

INITIAL_TABLES = [
    {"table_number": "T-1", "capacity": 2, "status": "available"},
    {"table_number": "T-2", "capacity": 2, "status": "available"},
    {"table_number": "T-3", "capacity": 4, "status": "available"},
    {"table_number": "T-4", "capacity": 4, "status": "available"},
    {"table_number": "T-5", "capacity": 4, "status": "available"},
    {"table_number": "T-6", "capacity": 6, "status": "available"},
    {"table_number": "Patio-1", "capacity": 4, "status": "available"},
    {"table_number": "Patio-2", "capacity": 4, "status": "available"},
    {"table_number": "Booth-A", "capacity": 8, "status": "available"},
    {"table_number": "Booth-B", "capacity": 6, "status": "available"},
]


def seed_tables():
    print("=" * 70)
    print(" Seeding Restaurant Dining Tables (Idempotent)")
    print("=" * 70)

    db = SessionLocal()
    try:
        existing_tables = db.query(RestaurantTable).all()
        existing_numbers = {t.table_number.strip().lower() for t in existing_tables}
        print(f"Existing tables in database: {len(existing_tables)}")

        inserted_count = 0
        skipped_count = 0

        for t_data in INITIAL_TABLES:
            num_lower = t_data["table_number"].strip().lower()
            if num_lower in existing_numbers:
                print(f"  - Table '{t_data['table_number']}' already exists. Skipping.")
                skipped_count += 1
            else:
                new_table = RestaurantTable(
                    table_number=t_data["table_number"],
                    capacity=t_data["capacity"],
                    status=t_data["status"],
                )
                db.add(new_table)
                inserted_count += 1
                print(f"  + Added table '{t_data['table_number']}' (Capacity: {t_data['capacity']}, Status: {t_data['status']})")

        if inserted_count > 0:
            db.commit()
            print(f"\n✓ Successfully committed {inserted_count} table(s) to database.")
        else:
            print("\n✓ No new tables needed. Database is already up to date.")

        print(f"Summary: {inserted_count} inserted, {skipped_count} skipped.")

        # Post-seed verification
        all_tables = db.query(RestaurantTable).order_by(RestaurantTable.id.asc()).all()
        print(f"\nTotal tables now in database: {len(all_tables)}")
        for t in all_tables:
            print(f"  ID {t.id}: {t.table_number} | Capacity: {t.capacity} | Status: {t.status}")

        return len(all_tables)
    except Exception as err:
        db.rollback()
        print(f"Error seeding tables: {err}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_tables()
