#!/usr/bin/env python3
"""CLI utility to safely create or update the initial administrator account.

Usage:
  Interactive mode (secure):
    python create_admin.py

  Non-interactive mode (for CI / automated setup):
    python create_admin.py --username admin --email admin@restaurant.local --full-name "System Administrator" --password <password>
"""

import argparse
import getpass
import sys
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main():
    parser = argparse.ArgumentParser(description="Create or update an administrative user account.")
    parser.add_argument("--username", help="Admin username (e.g. admin)")
    parser.add_argument("--email", help="Admin email address (e.g. admin@restaurant.local)")
    parser.add_argument("--full-name", help="Full name of administrator")
    parser.add_argument("--password", help="Password (interactive prompt used if omitted)")

    args = parser.parse_args()

    username = args.username
    if not username:
        username = input("Enter admin username: ").strip()
    if not username:
        print("Error: Username cannot be blank.", file=sys.stderr)
        sys.exit(1)

    email = args.email
    if not email:
        email = input("Enter admin email address: ").strip()
    if not email:
        print("Error: Email cannot be blank.", file=sys.stderr)
        sys.exit(1)

    full_name = args.full_name
    if not full_name:
        full_name = input("Enter full name (optional): ").strip() or "Administrator"

    password = args.password
    if not password:
        password = getpass.getpass("Enter password (min 8 characters): ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            existing_user.username = username
            existing_user.email = email
            existing_user.full_name = full_name
            existing_user.role = "admin"
            existing_user.is_active = True
            existing_user.hashed_password = hash_password(password)
            db.commit()
            print(f"✓ Successfully updated existing user '{username}' to administrator (ID: {existing_user.id}).")
        else:
            new_admin = User(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                role="admin",
                is_active=True,
            )
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            print(f"✓ Successfully created administrator '{username}' with role 'admin' (ID: {new_admin.id}).")
    except Exception as err:
        db.rollback()
        print(f"Error creating administrator: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
