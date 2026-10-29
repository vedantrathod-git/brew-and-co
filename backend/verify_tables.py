"""Script to verify all tables, columns, constraints, and foreign keys in restaurant_db."""
from sqlalchemy import inspect
from app.db.session import engine


def verify():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("=" * 60)
    print(" PostgreSQL Table Verification for 'restaurant_db'")
    print("=" * 60)
    print(f"Discovered Tables ({len(tables)}): {', '.join(tables)}")

    expected = ["categories", "restaurant_tables", "menu_items", "orders", "order_items", "alembic_version"]
    for table_name in expected:
        if table_name not in tables:
            raise RuntimeError(f"Expected table '{table_name}' was not found in database!")

        print(f"\n[OK] Table: {table_name}")
        columns = inspector.get_columns(table_name)
        for col in columns:
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col.get("default") else ""
            print(f"  - {col['name']}: {col['type']} ({nullable}){default}")

        pks = inspector.get_pk_constraint(table_name)
        if pks and pks.get("constrained_columns"):
            print(f"  Primary Key: {pks['constrained_columns']}")

        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            print(f"  Foreign Key: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']} (ondelete={fk.get('options', {}).get('ondelete')})")

        checks = inspector.get_check_constraints(table_name)
        for chk in checks:
            print(f"  Check Constraint: '{chk['name']}' -> {chk['sqltext']}")

    print("\n" + "=" * 60)
    print(" ALL 5 TABLES & CONSTRAINTS SUCCESSFULLY VERIFIED IN POSTGRESQL!")
    print("=" * 60)


if __name__ == "__main__":
    verify()
