"""Interactive helper to create or update an inter-school admin user.

This script prompts for the basic account details and ensures that the
resulting user has the `inter_school` role and is linked to the
Inter-School Control records in the database.

Usage:
    python scripts/create_interschool_admin.py
"""
from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

# Ensure project root is on sys.path when running as a standalone script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.routes.golden_plate_recorder_db.db import (
    INTERSCHOOL_SCHOOL_ID,
    INTERSCHOOL_SCHOOL_NAME,
    INTERSCHOOL_SCHOOL_SLUG,
    School,
    _now_utc,
    db_session,
)
from src.routes.golden_plate_recorder_db.users import (
    create_user_record,
    get_user_by_username,
    update_user_credentials,
)

DEFAULT_USERNAME = "inter-school-admin"
DEFAULT_DISPLAY_NAME = "Inter-School Controller"
DEFAULT_STATUS = "active"
TARGET_ROLE = "inter_school"


def _prompt(prompt_text: str, *, default: str | None = None, allow_blank: bool = False) -> str:
    while True:
        suffix = f" [{default}]" if default else ""
        response = input(f"{prompt_text}{suffix}: ").strip()
        if response:
            return response
        if response == "" and default is not None:
            return default
        if allow_blank:
            return ""
        print("A value is required. Please try again.")


def _prompt_password(existing: bool) -> str | None:
    if existing:
        choice = _prompt("Update password? (y/N)", default="n").lower()
        if choice not in {"y", "yes"}:
            return None
    while True:
        password = getpass("Enter password: ")
        if not password:
            print("Password cannot be empty.")
            continue
        confirm = getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Please try again.")
            continue
        return password


def _ensure_interschool_school() -> School:
    school = db_session.query(School).filter_by(id=INTERSCHOOL_SCHOOL_ID).first()
    if school:
        return school
    school = School(
        id=INTERSCHOOL_SCHOOL_ID,
        name=INTERSCHOOL_SCHOOL_NAME,
        slug=INTERSCHOOL_SCHOOL_SLUG,
        status="active",
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )
    try:
        db_session.add(school)
        db_session.commit()
    except SQLAlchemyError:
        db_session.rollback()
        print("Failed to create the inter-school control record.")
        raise
    return school


def main() -> int:
    print("Inter-School Admin Setup")
    print("This will create or update an inter-school administrator account.\n")

    _ensure_interschool_school()

    username = _prompt("Username", default=DEFAULT_USERNAME)
    existing_user = get_user_by_username(username)

    if existing_user:
        print(f"Found existing user '{username}'. Updating details...")
        display_name_default = existing_user.display_name or DEFAULT_DISPLAY_NAME
        status_default = existing_user.status or DEFAULT_STATUS
    else:
        display_name_default = DEFAULT_DISPLAY_NAME
        status_default = DEFAULT_STATUS

    display_name = _prompt("Display name", default=display_name_default)
    status = _prompt("Status", default=status_default)

    password = _prompt_password(existing_user is not None)

    try:
        if existing_user:
            update_user_credentials(
                existing_user,
                password=password if password is not None else None,
                display_name=display_name,
                role=TARGET_ROLE,
                status=status,
                school_id=INTERSCHOOL_SCHOOL_ID,
            )
        else:
            create_user_record(
                username,
                password if password is not None else _prompt_password(False),
                display_name,
                role=TARGET_ROLE,
                status=status,
                school_id=INTERSCHOOL_SCHOOL_ID,
            )
        db_session.commit()
    except SQLAlchemyError as exc:
        db_session.rollback()
        print(f"Database error: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - guard for unexpected issues
        db_session.rollback()
        print(f"Unexpected error: {exc}")
        return 1

    print("Inter-school admin setup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
