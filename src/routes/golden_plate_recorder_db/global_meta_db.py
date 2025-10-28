"""Global metadata database models and helpers.

This module manages the new ``global_meta`` SQLite database that tracks
cross-school configuration such as the catalog of schools, global users,
feature toggles, and audit history.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker


GLOBAL_META_DATABASE_URL = os.environ.get(
    'GLOBAL_META_DATABASE_URL', 'sqlite:///data/global_meta.db'
)

if GLOBAL_META_DATABASE_URL.startswith('sqlite:///'):
    db_path = GLOBAL_META_DATABASE_URL.replace('sqlite:///', '', 1)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

connect_args = {}
if GLOBAL_META_DATABASE_URL.startswith('sqlite'):
    connect_args = {
        'check_same_thread': False,
        'timeout': 30,
    }

global_meta_engine = create_engine(
    GLOBAL_META_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
)
GlobalMetaSessionFactory = sessionmaker(
    autocommit=False, autoflush=False, bind=global_meta_engine
)
global_meta_session = scoped_session(GlobalMetaSessionFactory)
GlobalMetaBase = declarative_base()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class School(GlobalMetaBase):
    __tablename__ = 'schools'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    address = Column(Text)
    public_profile_json = Column(Text)
    guest_access_enabled = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True))
    db_path = Column(String(512), nullable=False)


class GlobalUser(GlobalMetaBase):
    __tablename__ = 'global_users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False, unique=True)
    display_name = Column(String(255), nullable=False)
    email = Column(String(255))
    password_hash = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)


class SchoolSettings(GlobalMetaBase):
    __tablename__ = 'school_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    kv_json = Column(Text, nullable=False)


class FeatureToggle(GlobalMetaBase):
    __tablename__ = 'feature_toggles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    key = Column(String(255), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    updated_by = Column(Integer, ForeignKey('global_users.id'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (UniqueConstraint('school_id', 'key', name='uq_feature_toggle_school_key'),)


class SchoolInvite(GlobalMetaBase):
    __tablename__ = 'school_invites'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(255), nullable=False, unique=True)
    requested_features_json = Column(Text)
    initial_owner_display_name = Column(String(255))
    created_by = Column(Integer, ForeignKey('global_users.id'))
    consumed_by_school_id = Column(Integer, ForeignKey('schools.id'))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)
    consumed_at = Column(DateTime(timezone=True))


class UserDirectory(GlobalMetaBase):
    __tablename__ = 'user_directory'

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    username = Column(String(255), nullable=False)
    password_hash_ref = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)

    __table_args__ = (
        UniqueConstraint('school_id', 'username', name='uq_user_directory_school_username'),
    )


class AuditLog(GlobalMetaBase):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_scope = Column(String(50), nullable=False)
    actor_id = Column(String(255), nullable=False)
    target_school_id = Column(Integer, ForeignKey('schools.id'))
    action = Column(String(255), nullable=False)
    payload_json = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now_utc)


_DEFAULT_GLOBAL_SUPERADMIN = {
    'username': 'antineutrino',
    'display_name': 'b-decay',
    'email': None,
    'password_hash': None,
    'is_active': True,
}


def seed_default_global_user() -> GlobalUser:
    """Ensure the default global super administrator exists."""

    session = global_meta_session
    user = session.query(GlobalUser).filter(GlobalUser.username == _DEFAULT_GLOBAL_SUPERADMIN['username']).one_or_none()

    if not user:
        user = GlobalUser(
            username=_DEFAULT_GLOBAL_SUPERADMIN['username'],
            display_name=_DEFAULT_GLOBAL_SUPERADMIN['display_name'],
            email=_DEFAULT_GLOBAL_SUPERADMIN['email'],
            password_hash=_DEFAULT_GLOBAL_SUPERADMIN['password_hash'],
            is_active=_DEFAULT_GLOBAL_SUPERADMIN['is_active'],
        )
        session.add(user)
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        return user

    updated = False
    for key in ('display_name', 'email', 'password_hash', 'is_active'):
        desired = _DEFAULT_GLOBAL_SUPERADMIN[key]
        if getattr(user, key) != desired:
            setattr(user, key, desired)
            updated = True

    if updated:
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

    return user


def sync_superadmins_to_global_users(superadmins: Iterable) -> None:
    """Mirror local superadmin records into the global meta database."""

    superadmins = list(superadmins or [])
    if not superadmins:
        return

    session = global_meta_session

    try:
        for admin in superadmins:
            username = getattr(admin, 'username', None)
            if not username:
                continue

            global_user: Optional[GlobalUser] = (
                session.query(GlobalUser).filter(GlobalUser.username == username).one_or_none()
            )

            status = getattr(admin, 'status', 'active')
            is_active = status not in {'disabled', 'inactive', 'deleted'}
            if username == _DEFAULT_GLOBAL_SUPERADMIN['username']:
                display_name = _DEFAULT_GLOBAL_SUPERADMIN['display_name']
            else:
                display_name = getattr(admin, 'display_name', None) or username
            password_hash = getattr(admin, 'password_hash', None)
            created_at = getattr(admin, 'created_at', None) or _now_utc()

            if global_user is None:
                global_user = GlobalUser(
                    username=username,
                    display_name=display_name,
                    email=getattr(admin, 'email', None),
                    password_hash=password_hash,
                    is_active=is_active,
                    created_at=created_at,
                )
                session.add(global_user)
                continue

            updated = False
            if global_user.display_name != display_name:
                global_user.display_name = display_name
                updated = True
            if global_user.password_hash != password_hash:
                global_user.password_hash = password_hash
                updated = True
            if global_user.is_active != is_active:
                global_user.is_active = is_active
                updated = True
            if getattr(admin, 'email', None) and global_user.email != admin.email:
                global_user.email = admin.email
                updated = True
            if updated:
                session.add(global_user)

        session.commit()
    except Exception:
        session.rollback()
        raise


def init_global_meta_db() -> None:
    """Create tables and seed required defaults."""

    GlobalMetaBase.metadata.create_all(bind=global_meta_engine)
    seed_default_global_user()


# Initialize the database on import.
init_global_meta_db()


__all__ = [
    'AuditLog',
    'FeatureToggle',
    'GlobalMetaBase',
    'GlobalUser',
    'School',
    'SchoolInvite',
    'SchoolSettings',
    'UserDirectory',
    'global_meta_engine',
    'global_meta_session',
    'init_global_meta_db',
    'seed_default_global_user',
    'sync_superadmins_to_global_users',
]
