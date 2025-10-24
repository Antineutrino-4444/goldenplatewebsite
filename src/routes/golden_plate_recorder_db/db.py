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
    inspect,
    text,
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


def _migrate_draw_schema() -> None:
    """Ensure draw-related schema is embedded in the sessions table."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if 'sessions' not in table_names:
        return

    with engine.begin() as connection:
        # Ensure new columns exist on sessions.
        session_columns = {column['name'] for column in inspector.get_columns('sessions')}
        required_columns = [
            ('draw_number', 'INTEGER NOT NULL DEFAULT 1'),
            ('winner_student_id', 'TEXT'),
            ('method', 'TEXT'),
            ('finalized', 'INTEGER NOT NULL DEFAULT 0'),
            ('finalized_by', 'TEXT'),
            ('finalized_at', 'DATETIME'),
            ('tickets_at_selection', 'INTEGER'),
            ('probability_at_selection', 'INTEGER'),
            ('eligible_pool_size', 'INTEGER'),
            ('override_applied', 'INTEGER NOT NULL DEFAULT 0'),
        ]

        for column_name, ddl in required_columns:
            if column_name not in session_columns:
                connection.execute(text(f'ALTER TABLE sessions ADD COLUMN {column_name} {ddl}'))

        # Refresh inspector data after altering the sessions table.
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

        # Rebuild session_draw_events if it still depends on session_draws.
        if 'session_draw_events' in table_names:
            event_columns = {column['name'] for column in inspector.get_columns('session_draw_events')}
            needs_rebuild = 'session_draw_id' in event_columns or 'draw_number' not in event_columns

            if needs_rebuild:
                connection.execute(text('ALTER TABLE session_draw_events RENAME TO session_draw_events_old'))
                connection.execute(text(
                    '''
                    CREATE TABLE session_draw_events (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                        draw_number INTEGER,
                        event_type TEXT NOT NULL,
                        selected_record_id TEXT REFERENCES session_records(id),
                        selected_student_id TEXT REFERENCES students(id),
                        tickets_at_event INTEGER,
                        probability_at_event INTEGER,
                        eligible_pool_size INTEGER,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT REFERENCES users(id)
                    )
                    '''
                ))
                # Copy existing history into the rebuilt table.
                if 'session_draws' in table_names:
                    connection.execute(text(
                        '''
                        INSERT INTO session_draw_events (
                            id,
                            session_id,
                            draw_number,
                            event_type,
                            selected_record_id,
                            selected_student_id,
                            tickets_at_event,
                            probability_at_event,
                            eligible_pool_size,
                            created_at,
                            created_by
                        )
                        SELECT
                            e.id,
                            e.session_id,
                            COALESCE(d.draw_number, 1),
                            e.event_type,
                            e.selected_record_id,
                            e.selected_student_id,
                            e.tickets_at_event,
                            e.probability_at_event,
                            e.eligible_pool_size,
                            e.created_at,
                            e.created_by
                        FROM session_draw_events_old e
                        LEFT JOIN session_draws d ON e.session_draw_id = d.id
                        '''
                    ))
                else:
                    connection.execute(text(
                        '''
                        INSERT INTO session_draw_events (
                            id,
                            session_id,
                            draw_number,
                            event_type,
                            selected_record_id,
                            selected_student_id,
                            tickets_at_event,
                            probability_at_event,
                            eligible_pool_size,
                            created_at,
                            created_by
                        )
                        SELECT
                            id,
                            session_id,
                            1,
                            event_type,
                            selected_record_id,
                            selected_student_id,
                            tickets_at_event,
                            probability_at_event,
                            eligible_pool_size,
                            created_at,
                            created_by
                        FROM session_draw_events_old
                        '''
                    ))

                connection.execute(text('DROP TABLE session_draw_events_old'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_draw_events_session ON session_draw_events (session_id, created_at)'))
            else:
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_draw_events_session ON session_draw_events (session_id, created_at)'))

        # Copy draw data into sessions and remove the legacy table.
        if 'session_draws' in table_names:
            draw_rows = connection.execute(text(
                '''
                SELECT
                    session_id,
                    draw_number,
                    winner_student_id,
                    method,
                    finalized,
                    finalized_by,
                    finalized_at,
                    tickets_at_selection,
                    probability_at_selection,
                    eligible_pool_size,
                    override_applied
                FROM session_draws
                '''
            )).fetchall()

            for row in draw_rows:
                mapping = row._mapping
                connection.execute(text(
                    '''
                    UPDATE sessions
                    SET
                        draw_number = COALESCE(:draw_number, draw_number),
                        winner_student_id = COALESCE(:winner_student_id, winner_student_id),
                        method = COALESCE(:method, method),
                        finalized = COALESCE(:finalized, finalized),
                        finalized_by = COALESCE(:finalized_by, finalized_by),
                        finalized_at = COALESCE(:finalized_at, finalized_at),
                        tickets_at_selection = COALESCE(:tickets_at_selection, tickets_at_selection),
                        probability_at_selection = COALESCE(:probability_at_selection, probability_at_selection),
                        eligible_pool_size = COALESCE(:eligible_pool_size, eligible_pool_size),
                        override_applied = COALESCE(:override_applied, override_applied)
                    WHERE id = :session_id
                    '''
                ), mapping)

            connection.execute(text('DROP TABLE session_draws'))


_migrate_draw_schema()


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

    draw_number = Column(Integer, nullable=False, default=1)
    winner_student_id = Column(String, ForeignKey('students.id'))
    method = Column(String)
    finalized = Column(Integer, nullable=False, default=0)
    finalized_by = Column(String, ForeignKey('users.id'))
    finalized_at = Column(DateTime(timezone=True))
    tickets_at_selection = Column(Integer)
    probability_at_selection = Column(Integer)
    eligible_pool_size = Column(Integer)
    override_applied = Column(Integer, nullable=False, default=0)


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


class SessionDrawEvent(Base):
    __tablename__ = 'session_draw_events'
    __table_args__ = (
        Index('idx_draw_events_session', 'session_id', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    draw_number = Column(Integer)
    event_type = Column(String, nullable=False)
    selected_record_id = Column(String, ForeignKey('session_records.id'))
    selected_student_id = Column(String, ForeignKey('students.id'))
    tickets_at_event = Column(Integer)
    probability_at_event = Column(Integer)
    eligible_pool_size = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    created_by = Column(String, ForeignKey('users.id'))


class SessionTicketEvent(Base):
    __tablename__ = 'session_ticket_events'
    __table_args__ = (
        Index('idx_ticket_events_session', 'session_id', 'occurred_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    session_record_id = Column(String, ForeignKey('session_records.id', ondelete='SET NULL'))
    student_id = Column(String, ForeignKey('students.id'))
    event_type = Column(String, nullable=False)
    tickets_delta = Column(Integer, nullable=False)
    ticket_balance_after = Column(Integer)
    occurred_at = Column(DateTime(timezone=True), default=_now_utc)
    occurred_by = Column(String, ForeignKey('users.id'))
    event_metadata = Column(Text)


class DraftPool(Base):
    __tablename__ = 'draft_pool'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String, ForeignKey('students.id'), nullable=False, unique=True)
    ticket_number = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)

__all__ = [
    'DATABASE_URL',
    'Base',
    'DraftPool',
    'Session',
    'SessionDrawEvent',
    'SessionRecord',
    'SessionTicketEvent',
    'Student',
    'Teacher',
    'User',
    'UserInviteCode',
    'db_session',
    'engine',
    '_now_utc',
]
