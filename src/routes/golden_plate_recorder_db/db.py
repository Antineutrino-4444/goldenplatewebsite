import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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

# Configure SQLite-specific settings for better concurrency
connect_args = {}
if DATABASE_URL.startswith('sqlite'):
    connect_args = {
        'check_same_thread': False,
        'timeout': 30,  # Wait up to 30 seconds for locks to clear
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections after 1 hour
)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionFactory)
Base = declarative_base()


def _now_utc():
    return datetime.now(timezone.utc)


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


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_by = Column(String, ForeignKey('users.id'), nullable=False)
    session_name = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default='active')
    is_public = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)
    discarded_at = Column(DateTime(timezone=True))
    discarded_by = Column(String, ForeignKey('users.id'))

    clean_number = Column(Integer)
    dirty_number = Column(Integer)
    red_number = Column(Integer)
    faculty_number = Column(Integer)

    total_records = Column(Integer)
    total_clean = Column(Integer)
    total_dirty = Column(Integer)


class SessionRecord(Base):
    __tablename__ = 'session_records'
    __table_args__ = (
        Index('idx_records_session_category', 'session_id', 'category'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    student_id = Column(String, ForeignKey('students.id'))
    category = Column(String, nullable=False)
    grade = Column(String)
    house = Column(String)
    is_manual_entry = Column(Integer, nullable=False, default=0)
    recorded_by = Column(String, ForeignKey('users.id'), nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=_now_utc)
    dedupe_key = Column(String, nullable=False)
    preferred_name = Column(String)
    last_name = Column(String)


Base.metadata.create_all(bind=engine)

__all__ = [
    'DATABASE_URL',
    'Base',
    'Session',
    'SessionRecord',
    'Student',
    'Teacher',
    'User',
    'UserInviteCode',
    'db_session',
    'engine',
    '_now_utc',
]
