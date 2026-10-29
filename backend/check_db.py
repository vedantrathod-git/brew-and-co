"""Standalone CLI script to verify PostgreSQL database connectivity."""
import sys
from app.db.session import check_db_connection
from app.core.config import settings


def main():
    print("=" * 60)
    print(" Restaurant Management System - Database Connection Check")
    print("=" * 60)
    print(f"Target Database URL: {settings.sanitized_database_url}")
    print("Executing 'SELECT 1' via SQLAlchemy...")

    result = check_db_connection()

    if result["success"]:
        print("\n[SUCCESS] Successfully connected to PostgreSQL!")
        print(f"Server response (SELECT 1): {result['result']}")
        print("Database foundation is working correctly.\n")
        sys.exit(0)
    else:
        print("\n[FAILED] Could not connect to PostgreSQL.")
        print(f"Error detail: {result['error']}")
        print("\nTroubleshooting tips:")
        print(" 1. Ensure PostgreSQL service is running on port 5432.")
        print(" 2. Verify that 'restaurant_db' exists.")
        print(" 3. Update 'DATABASE_URL' in 'backend/.env' with your actual PostgreSQL password:")
        print("    DATABASE_URL=postgresql+psycopg://postgres:<your_password>@localhost:5432/restaurant_db\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
