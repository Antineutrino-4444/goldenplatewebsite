import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///data/golden_plate_recorder.db')
if DATABASE_URL.startswith('sqlite:///'):
    db_path = DATABASE_URL.replace('sqlite:///', '', 1)
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionFactory)
Base = declarative_base()


def _now_utc():
    return datetime.now(timezone.utc)


class KeyValueStore(Base):
    __tablename__ = 'kv_store'

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False, default='{}')
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (Index('idx_users_username', 'username'),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)
    status = Column(String, nullable=False, default='active')


class UserInviteCode(Base):
    __tablename__ = 'user_invite_codes'
    __table_args__ = (Index('idx_invite_codes_user', 'user_id', 'status'),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    code = Column(String, unique=True, nullable=False)
    issued_by = Column(String, ForeignKey('users.id'), nullable=False)
    issued_at = Column(DateTime(timezone=True), default=_now_utc)
    expires_at = Column(DateTime(timezone=True))
    used_by = Column(String, ForeignKey('users.id'))
    used_at = Column(DateTime(timezone=True))
    status = Column(String, nullable=False, default='unused')
    role = Column(String, nullable=False, default='user')


class Student(Base):
    __tablename__ = 'students'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_identifier = Column(String, unique=True, nullable=False)
    preferred_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    grade = Column(String)
    advisor = Column(String)
    house = Column(String)
    clan = Column(String)


class Teacher(Base):
    __tablename__ = 'teachers'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    display_name = Column(String)


Base.metadata.create_all(bind=engine)

__all__ = [
    'DATABASE_URL',
    'Base',
    'KeyValueStore',
    'Student',
    'Teacher',
    'User',
    'UserInviteCode',
    'db_session',
    'engine',
    '_now_utc',
]
