"""Migrate legacy delete requests JSON into the `session_delete_requests` table.

This script reads `persistent_data/delete_requests.json` and inserts rows into
the database using the existing SQLAlchemy models in
`src.routes.gold_plate_recorder_db.db`.

Usage:
  python migrate_delete_requests_to_db.py [--source-dir persistent_data] [--dry-run] [--backup]

Features:
- Attempts to resolve `requester` and `approved_by` to existing users by
  `username` or `display_name`. If not found, a minimal user record is created.
- Idempotent: skips entries that already exist in the DB by `id`.
- Dry-run mode (no commits) and optional backup of the source JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

# Ensure repo root is importable so we can import the app DB module.
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from src.routes.golden_plate_recorder_db.db import (
    SessionDeleteRequest,
    User,
    SessionFactory,
    _now_utc,
)


def parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        parsed = datetime.fromisoformat(dt)
    except Exception:
        # Fallback: let datetime try some common formats
        try:
            parsed = datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%f")
        except Exception:
            parsed = None
    if parsed and parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def find_or_create_user(session: Session, username: Optional[str], display_name: Optional[str]) -> str:
    """Return user.id for a matching or newly-created user.

    Strategy:
    - Try exact username match on `username` field
    - Try exact match on `display_name`
    - If not found, create a minimal user with role 'user'
    """
    if username:
        user = session.query(User).filter_by(username=username).one_or_none()
        if user:
            return user.id

    if display_name:
        user = session.query(User).filter_by(display_name=display_name).one_or_none()
        if user:
            return user.id

    # Create minimal user record to preserve referential integrity.
    new_username = username or f"migrated_user_{uuid.uuid4().hex[:8]}"
    new_display = display_name or new_username
    user = User(username=new_username, password_hash="migrated", display_name=new_display, role="user", status="active")
    session.add(user)
    session.flush()
    return user.id


def migrate_file(source: Path, dry_run: bool = False, backup: bool = False) -> None:
    if not source.exists():
        raise SystemExit(f"Source file {source} not found")

    if backup:
        backup_path = source.with_suffix(source.suffix + ".bak")
        backup_path.write_bytes(source.read_bytes())
        print(f"Backup written to {backup_path}")

    data = json.loads(source.read_text(encoding="utf-8"))
    inserted = 0
    skipped = 0

    with SessionFactory() as session:
        for item in data:
            existing = session.get(SessionDeleteRequest, item.get("id"))
            if existing:
                skipped += 1
                continue

            # Resolve or create requester user
            requester_username = item.get("requester")
            requester_name = item.get("requester_name")
            requested_by_id = find_or_create_user(session, requester_username, requester_name)

            status = item.get("status") or "pending"
            requested_at = parse_iso(item.get("requested_at")) or _now_utc()

            # Build new delete request
            new_req = SessionDeleteRequest(
                id=item.get("id") or str(uuid.uuid4()),
                session_id=item.get("session_id"),
                requested_by=requested_by_id,
                requested_at=requested_at,
                status=status,
            )

            # Map approved/review fields if present
            if item.get("approved_by"):
                reviewed_by = find_or_create_user(session, item.get("approved_by"), item.get("approved_by"))
                new_req.reviewed_by = reviewed_by
            if item.get("approved_at"):
                new_req.reviewed_at = parse_iso(item.get("approved_at"))
            if item.get("rejection_reason"):
                new_req.rejection_reason = item.get("rejection_reason")

            session.add(new_req)
            # Commit per-row to ensure flush of created user ids; affordable for modest datasets
            if dry_run:
                session.flush()
                session.rollback()
            else:
                session.commit()
            inserted += 1

    print(f"Migration complete: inserted={inserted}, skipped={skipped}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate delete_requests.json into session_delete_requests table.")
    parser.add_argument("--source-dir", default="persistent_data", help="Folder with legacy JSON files")
    parser.add_argument("--file", default="delete_requests.json", help="Filename to migrate")
    parser.add_argument("--dry-run", action="store_true", help="Do not commit changes")
    parser.add_argument("--backup", action="store_true", help="Write a .bak backup of the source file before migrating")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    source_file = source_dir / args.file
    migrate_file(source_file, dry_run=args.dry_run, backup=args.backup)


if __name__ == "__main__":
    main()
