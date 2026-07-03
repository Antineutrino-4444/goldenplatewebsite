"""Interactive helper to change an existing user's username and/or password.

Usage:
    python scripts/change_user_credentials.py
"""
from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")

from src.routes.golden_plate_recorder_db.db import _now_utc, db_session
from src.routes.golden_plate_recorder_db.app_config import default_admin_credentials_enabled
from src.routes.golden_plate_recorder_db.users import (
    DEFAULT_SUPERADMIN,
    get_user_by_username,
    update_user_credentials,
)


def _prompt(prompt_text: str, *, allow_blank: bool = False) -> str:
    while True:
        response = input(f"{prompt_text}: ").strip()
        if response or allow_blank:
            return response
        print("A value is required.")


def _prompt_new_username(current_username: str, user_id: str) -> str | None:
    while True:
        new_username = _prompt(
            f"New username [press Enter to keep '{current_username}']",
            allow_blank=True,
        )
        if not new_username or new_username == current_username:
            return None
        if len(new_username) < 3:
            print("Username must be at least 3 characters.")
            continue

        existing = get_user_by_username(new_username)
        if existing and existing.id != user_id:
            print("That username is already in use.")
            continue
        return new_username


def _prompt_new_password() -> str | None:
    choice = _prompt("Change password? (y/N)", allow_blank=True).lower()
    if choice not in {"y", "yes"}:
        return None

    while True:
        password = getpass("New password: ")
        if len(password) < 6:
            print("Password must be at least 6 characters.")
            continue
        confirm = getpass("Confirm new password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue
        return password


def main() -> int:
    print("Change User Credentials")
    print("This updates an existing account in the configured database.\n")

    current_username = _prompt("Current username")
    user = get_user_by_username(current_username)
    if not user:
        print(f"User '{current_username}' was not found.")
        return 1

    print(f"Found: {user.username} ({user.display_name}, role={user.role})")
    if user.username == DEFAULT_SUPERADMIN["username"] and default_admin_credentials_enabled():
        print(
            "Note: APP_ENV=development keeps the built-in greenguys/begreendogood "
            "login enabled. Set APP_ENV=production before using this for deployment."
        )

    new_username = _prompt_new_username(user.username, user.id)
    new_password = _prompt_new_password()

    if not new_username and new_password is None:
        print("No changes made.")
        return 0

    try:
        if new_username:
            user.username = new_username
            user.updated_at = _now_utc()
        update_user_credentials(
            user,
            password=new_password,
            auto_commit=False,
        )
        db_session.commit()
    except SQLAlchemyError as exc:
        db_session.rollback()
        print(f"Database error: {exc}")
        return 1
    finally:
        db_session.remove()

    print("Credentials updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
