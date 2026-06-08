#!/usr/bin/env python3
"""Administrator CLI for provisioning Accessibility Tools accounts.

There is no self-registration anywhere in the application. Accounts are
created here, by someone with shell access to the server.

Usage
-----
Interactive (prompts for username, password, role):

    python create_user.py

One-shot with arguments:

    python create_user.py --username admin --password "Admin@123" --role admin

Programmatic:

    from create_user import add_user
    add_user(username="admin", password="Admin@123", role="admin")
"""
from __future__ import annotations

import argparse
import getpass
import sys

from database import init_db
from database.models import create_user, list_users, update_role


def add_user(username: str, password: str, role: str = "user") -> bool:
    """Create a user. Returns True on success, prints the outcome."""
    init_db()
    ok, msg = create_user(username, password, role)
    print(("OK: " if ok else "ERROR: ") + msg)
    return ok


def add_users_from_csv(path: str) -> int:
    """Bulk-create users from a CSV with columns: username,password[,role].

    A header row is optional. Returns the number of users created.
    """
    import csv
    init_db()
    created = 0
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or not row[0].strip():
                continue
            if row[0].strip().lower() in ("username", "user", "name"):
                continue  # header row
            username = row[0].strip()
            password = row[1].strip() if len(row) > 1 else ""
            role = row[2].strip() if len(row) > 2 else "user"
            ok, msg = create_user(username, password, role)
            print((" OK: " if ok else " ERROR: ") + msg)
            created += 1 if ok else 0
    print(f"\nDone. {created} user(s) created.")
    return created


def _interactive() -> int:
    print("Create an Accessibility Tools user (Ctrl+C to cancel)\n")
    username = input("Username (3-32 chars): ").strip()
    password = getpass.getpass("Password (min 6 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: Passwords do not match.")
        return 1
    role = (input("Role [user/admin] (default user): ").strip() or "user")
    return 0 if add_user(username, password, role) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create an Accessibility Tools user account.")
    parser.add_argument("--username", "-u")
    parser.add_argument("--password", "-p")
    parser.add_argument("--role", "-r", default="user",
                        choices=["user", "admin"])
    parser.add_argument("--list", action="store_true",
                        help="List existing users and exit.")
    parser.add_argument("--csv",
                        help="Bulk-create users from a CSV: username,password[,role].")
    parser.add_argument("--set-role", action="store_true",
                        help="Change an existing user's role (use with --username --role).")
    args = parser.parse_args(argv)

    init_db()

    if args.set_role:
        if not args.username:
            print("ERROR: --set-role requires --username (and --role).")
            return 1
        ok, msg = update_role(args.username, args.role)
        print(("OK: " if ok else "ERROR: ") + msg)
        return 0 if ok else 1

    if args.csv:
        add_users_from_csv(args.csv)
        return 0

    if args.list:
        users = list_users()
        if not users:
            print("No users yet. Create one with: python create_user.py")
            return 0
        print(f"{'ID':<4} {'USERNAME':<24} {'ROLE':<8} CREATED")
        for u in users:
            print(f"{u.id:<4} {u.username:<24} {u.role:<8} {u.created_at}")
        return 0

    if args.username and args.password:
        return 0 if add_user(args.username, args.password, args.role) else 1

    # fall back to interactive prompts
    try:
        return _interactive()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
