"""Utility to migrate persistent JSON files into the key-value SQLite store."""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base

DEFAULT_DATABASE_URL = "sqlite:///data/golden_plate_recorder.db"

Base = declarative_base()


def _now_utc() -> datetime:
    """Return timezone-aware UTC timestamps."""
    return datetime.now(timezone.utc)


class KeyValueStore(Base):
    __tablename__ = "kv_store"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


STORE_KEYS: Dict[str, str] = {
    "sessions": "sessions.json",
    "users": "users.json",
    "delete_requests": "delete_requests.json",
    "invite_codes": "invite_codes.json",
    "global_csv_data": "global_csv_data.json",
    "teacher_list": "teacher_list.json",
}


@dataclass
class MigrationConfig:
    database_url: str
    source_dir: Path
    dry_run: bool = False


def load_json(source: Path) -> Any:
    if not source.exists():
        raise FileNotFoundError(f"{source} does not exist")
    with source.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def upsert_record(session: Session, key: str, payload: Any, dry_run: bool) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    record = session.get(KeyValueStore, key)
    if record is None:
        record = KeyValueStore(key=key, value=serialized)
        session.add(record)
    else:
        record.value = serialized
        record.updated_at = _now_utc()
    if dry_run:
        session.flush()
        session.rollback()
    else:
        session.commit()


def migrate(config: MigrationConfig) -> None:
    engine = create_engine(
        config.database_url,
        connect_args={"check_same_thread": False} if config.database_url.startswith("sqlite") else {},
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        for key, filename in STORE_KEYS.items():
            source_path = config.source_dir / filename
            if not source_path.exists():
                print(f"Skipping {filename}: no source file found")
                continue
            data = load_json(source_path)
            print(f"Migrating {filename} -> {key}")
            upsert_record(session, key, data, config.dry_run)
        if config.dry_run:
            print("Dry run complete; no changes committed.")


def parse_args() -> MigrationConfig:
    parser = argparse.ArgumentParser(description="Convert JSON persistence files into the SQLite kv_store table.")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="Target database URL. Defaults to DATABASE_URL env var or the app default.",
    )
    parser.add_argument(
        "--source-dir",
        default="persistent_data",
        help="Directory that contains the legacy JSON files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data and validate serialization without committing changes.",
    )
    args = parser.parse_args()
    source_dir = Path(args.source_dir).resolve()
    return MigrationConfig(database_url=args.database_url, source_dir=source_dir, dry_run=args.dry_run)


def main() -> None:
    config = parse_args()
    if not config.source_dir.exists():
        raise SystemExit(f"Source directory {config.source_dir} does not exist")
    migrate(config)


if __name__ == "__main__":
    main()
