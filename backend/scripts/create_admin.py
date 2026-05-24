"""Create or update the admin user.

Usage:
    python -m backend.scripts.create_admin <login> <password>
    python -m backend.scripts.create_admin --hash <password>     # print bcrypt hash
"""
from __future__ import annotations

import getpass
import sys

from backend.app import db
from backend.app.auth import hash_password, prehash
from backend.app.repositories import users as users_repo


def _upsert_admin(login: str, plain_password: str) -> None:
    db.init_db()
    login = login.strip().lower()
    users_repo.ensure_admin(login, hash_password(prehash(plain_password)))
    print(f"Admin user '{login}' created or updated.")


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--hash":
        print(hash_password(prehash(argv[1])))
        return 0

    if len(argv) >= 1:
        login = argv[0]
    else:
        login = input("Admin login: ").strip()

    if len(argv) >= 2:
        password = argv[1]
    else:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Repeat password: ")
        if password != confirm:
            print("Passwords do not match", file=sys.stderr)
            return 2

    if not login or not password:
        print("Login and password are required", file=sys.stderr)
        return 2

    _upsert_admin(login, password)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
