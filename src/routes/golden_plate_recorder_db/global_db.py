import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

GLOBAL_DATABASE_URL = os.environ.get('GLOBAL_DATABASE_URL', 'sqlite:///data/global_meta.db')

if GLOBAL_DATABASE_URL.startswith('sqlite:///'):
    db_path = GLOBAL_DATABASE_URL.replace('sqlite:///', '', 1)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

connect_args = {}
if GLOBAL_DATABASE_URL.startswith('sqlite'):
    connect_args = {
        'check_same_thread': False,
        'timeout': 30,
    }

global_engine = create_engine(
    GLOBAL_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
)
GlobalSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=global_engine)
global_db_session = scoped_session(GlobalSessionFactory)
GlobalBase = declarative_base()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class School(GlobalBase):
    __tablename__ = 'schools'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    address = Column(Text, nullable=True)
    public_contact = Column(Text, nullable=True)
    db_path = Column(Text, nullable=False)
    guest_access_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now_utc, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    settings = relationship('SchoolSetting', cascade='all, delete-orphan', back_populates='school')
    toggles = relationship('FeatureToggle', cascade='all, delete-orphan', back_populates='school')


class SchoolSetting(GlobalBase):
    __tablename__ = 'school_settings'
    __table_args__ = (UniqueConstraint('school_id', 'key', name='uq_school_setting_key'),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, index=True)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc, nullable=False)

    school = relationship('School', back_populates='settings')


class FeatureToggle(GlobalBase):
    __tablename__ = 'feature_toggles'
    __table_args__ = (UniqueConstraint('school_id', 'feature', name='uq_school_feature'),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, index=True)
    feature = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc, nullable=False)

    school = relationship('School', back_populates='toggles')


class GlobalUser(GlobalBase):
    __tablename__ = 'global_users'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    display_name = Column(String, nullable=False)
    status = Column(String, default='active', nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now_utc, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc, nullable=False)


class SchoolInvite(GlobalBase):
    __tablename__ = 'school_invites'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, nullable=False, unique=True, index=True)
    school_name = Column(String, nullable=False)
    address = Column(Text, nullable=True)
    feature_bundle = Column(Text, nullable=True)
    created_by = Column(String, ForeignKey('global_users.id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=_now_utc, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)


class UserDirectory(GlobalBase):
    __tablename__ = 'user_directory'
    __table_args__ = (
        UniqueConstraint('school_id', 'username', name='uq_school_username'),
        Index('ix_directory_username_school', 'username', 'school_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    username = Column(String, nullable=False)
    password_hash = Column(Text, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    status = Column(String, default='active', nullable=False)
    user_ref = Column(String, nullable=True)  # references per-school user id
    created_at = Column(DateTime, default=_now_utc, nullable=False)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc, nullable=False)


class AuditLog(GlobalBase):
    __tablename__ = 'audit_logs'
    __table_args__ = (Index('ix_audit_school_timestamp', 'school_id', 'created_at'),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='SET NULL'), nullable=True)
    actor_id = Column(String, nullable=True)
    actor_scope = Column(String, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc, nullable=False)


def init_global_metadata() -> None:
    GlobalBase.metadata.create_all(bind=global_engine)


def get_school_by_code(code: str) -> Optional[School]:
    if not code:
        return None
    return global_db_session.query(School).filter(School.code == code).first()


__all__ = [
    'AuditLog',
    'FeatureToggle',
    'GlobalBase',
    'GlobalSessionFactory',
    'GlobalUser',
    'School',
    'SchoolInvite',
    'SchoolSetting',
    'UserDirectory',
    'global_db_session',
    'global_engine',
    'init_global_metadata',
    'get_school_by_code',
]
