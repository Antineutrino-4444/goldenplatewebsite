import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

MAP_DATABASE_URL = os.environ.get('MAP_DATABASE_URL', 'sqlite:///data/golden_plate_map.db')
if MAP_DATABASE_URL.startswith('sqlite:///'):
    map_db_path = MAP_DATABASE_URL.replace('sqlite:///', '', 1)
    map_db_dir = os.path.dirname(map_db_path)
    if map_db_dir:
        os.makedirs(map_db_dir, exist_ok=True)

map_connect_args = {}
if MAP_DATABASE_URL.startswith('sqlite'):
    map_connect_args = {
        'check_same_thread': False,
        'timeout': 30,
    }

map_engine = create_engine(
    MAP_DATABASE_URL,
    connect_args=map_connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
)
MapSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=map_engine)
map_db_session = scoped_session(MapSessionFactory)
MapBase = declarative_base()


def _map_now_utc():
    return datetime.now(timezone.utc)


class MapEmailVerification(MapBase):
    __tablename__ = 'map_email_verifications'
    __table_args__ = (
        Index('idx_map_email_verifications_email', 'email'),
        Index('idx_map_email_verifications_purpose', 'purpose'),
        Index('idx_map_email_verifications_expires', 'expires_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False)
    code = Column(String(6), nullable=False)
    purpose = Column(String, nullable=False, default='map_submission')
    created_at = Column(DateTime(timezone=True), default=_map_now_utc)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False, default=0)


class MapSubmission(MapBase):
    __tablename__ = 'map_submissions'
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected')", name='ck_map_submissions_status'),
        Index('idx_map_submissions_school_status', 'school_id', 'status'),
        Index('idx_map_submissions_submitted_at', 'submitted_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, nullable=False)
    email = Column(String, nullable=False)
    text_content = Column(Text, nullable=False)
    image_filename = Column(String)
    image_mime = Column(String)
    image_data = Column(LargeBinary)
    image_size = Column(Integer)
    status = Column(String, nullable=False, default='pending')

    submitted_user_id = Column(String)
    submitted_username = Column(String)
    submitted_display_name = Column(String)
    submitted_role = Column(String)
    submitted_at = Column(DateTime(timezone=True), default=_map_now_utc)

    reviewed_user_id = Column(String)
    reviewed_username = Column(String)
    reviewed_display_name = Column(String)
    reviewed_role = Column(String)
    reviewed_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)


class MapSubmitterAccount(MapBase):
    __tablename__ = 'map_submitter_accounts'
    __table_args__ = (
        CheckConstraint("status IN ('active','disabled')", name='ck_map_submitter_accounts_status'),
        UniqueConstraint('email', name='uq_map_submitter_accounts_email'),
        Index('idx_map_submitter_accounts_school', 'school_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password_hash = Column(Text, nullable=False)
    status = Column(String, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), default=_map_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_map_now_utc, onupdate=_map_now_utc)
    last_used_at = Column(DateTime(timezone=True))
    created_from_submission_id = Column(String)


def _bootstrap_map_database() -> None:
    MapBase.metadata.create_all(bind=map_engine)


_bootstrap_map_database()


__all__ = [
    'MAP_DATABASE_URL',
    'MapBase',
    'MapEmailVerification',
    'MapSubmission',
    'MapSubmitterAccount',
    '_map_now_utc',
    'map_db_session',
    'map_engine',
]
