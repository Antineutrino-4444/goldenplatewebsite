import os
import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

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
        'timeout': 30,
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionFactory)
Base = declarative_base()


def _now_utc():
    return datetime.now(timezone.utc)


DEFAULT_SCHOOL_ID = 'default-school'
DEFAULT_SCHOOL_NAME = "St. Andrew's College"
DEFAULT_SCHOOL_SLUG = 'SAC'

INTERSCHOOL_SCHOOL_ID = 'a11'
INTERSCHOOL_SCHOOL_NAME = 'Inter-School Control'
INTERSCHOOL_SCHOOL_SLUG = 'inter-school-control'


class School(Base):
    __tablename__ = 'schools'
    __table_args__ = (
        CheckConstraint("status IN ('active','disabled')", name='ck_school_status'),
    )

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    status = Column(String, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("role IN ('user','admin','superadmin','inter_school')", name='ck_users_role'),
        CheckConstraint("status IN ('active','disabled')", name='ck_users_status'),
        UniqueConstraint('school_id', 'username', name='uq_users_school_username'),
        Index('idx_users_school', 'school_id'),
        Index('idx_users_username', 'username', unique=True),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
    username = Column(String, nullable=False)
    password_hash = Column(Text, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)
    status = Column(String, nullable=False, default='active')

    school = relationship('School', lazy='joined')


class UserInviteCode(Base):
    __tablename__ = 'user_invite_codes'
    __table_args__ = (
        CheckConstraint("status IN ('unused','used','revoked')", name='ck_user_invite_status'),
        UniqueConstraint('school_id', 'code', name='uq_user_invite_school_code'),
        Index('idx_invite_codes_school', 'school_id'),
        Index('idx_invite_codes_user', 'user_id', 'status'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
    user_id = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    code = Column(String, nullable=False)
    issued_by = Column(String, ForeignKey('users.id'), nullable=False)
    issued_at = Column(DateTime(timezone=True), default=_now_utc)
    expires_at = Column(DateTime(timezone=True))
    used_by = Column(String, ForeignKey('users.id'))
    used_at = Column(DateTime(timezone=True))
    status = Column(String, nullable=False, default='unused')
    role = Column(String, nullable=False, default='user')
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class SchoolInviteCode(Base):
    __tablename__ = 'school_invite_codes'
    __table_args__ = (
        CheckConstraint("status IN ('unused','used','revoked')", name='ck_school_invite_status'),
        UniqueConstraint('school_id', 'code', name='uq_school_invite_school_code'),
        Index('idx_school_invite_codes_school', 'school_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
    code = Column(String, nullable=False)
    issued_by = Column(String, ForeignKey('users.id'), nullable=False)
    issued_at = Column(DateTime(timezone=True), default=_now_utc)
    expires_at = Column(DateTime(timezone=True))
    used_by = Column(String, ForeignKey('users.id'))
    used_at = Column(DateTime(timezone=True))
    status = Column(String, nullable=False, default='unused')


class Student(Base):
    __tablename__ = 'students'
    __table_args__ = (
        UniqueConstraint('school_id', 'student_identifier', name='uq_students_school_identifier'),
        Index('idx_students_school', 'school_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
    student_identifier = Column(String, nullable=False)
    preferred_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    grade = Column(String)
    advisor = Column(String)
    house = Column(String)
    clan = Column(String)


class Teacher(Base):
    __tablename__ = 'teachers'
    __table_args__ = (
        UniqueConstraint('school_id', 'name', name='uq_teachers_school_name'),
        Index('idx_teachers_school', 'school_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
    name = Column(String, nullable=False)
    display_name = Column(String)


class Session(Base):
    __tablename__ = 'sessions'
    __table_args__ = (
        CheckConstraint("status IN ('active','archived','discarded')", name='ck_sessions_status'),
        UniqueConstraint('school_id', 'session_name', name='uq_sessions_school_name'),
        Index('idx_sessions_school', 'school_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
    created_by = Column(String, ForeignKey('users.id'), nullable=False)
    session_name = Column(String, nullable=False)
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
        CheckConstraint("category IN ('clean','dirty','red','faculty')", name='ck_session_records_category'),
        UniqueConstraint('school_id', 'session_id', 'dedupe_key', name='uq_session_records_dedupe'),
        Index('idx_records_school_session_category', 'school_id', 'session_id', 'category'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
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
        CheckConstraint("event_type IN ('draw','override','finalize','restore')", name='ck_session_draw_events_type'),
        Index('idx_draw_events_school_session', 'school_id', 'session_id', 'created_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False, default=DEFAULT_SCHOOL_ID)
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
        CheckConstraint("event_type IN ('earn','reset','manual_adjust')", name='ck_session_ticket_events_type'),
        Index('idx_ticket_events_school_session', 'school_id', 'session_id', 'occurred_at'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
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
    __table_args__ = (
        UniqueConstraint('school_id', 'student_id', name='uq_draft_pool_student'),
        Index('idx_draft_pool_school_session', 'school_id', 'session_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'))
    student_id = Column(String, ForeignKey('students.id'))
    ticket_number = Column(Integer, nullable=False)


class SessionDeleteRequest(Base):
    __tablename__ = 'session_delete_requests'
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','completed')", name='ck_session_delete_requests_status'),
        Index('idx_delete_requests_school_session', 'school_id', 'session_id'),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = Column(String, ForeignKey('schools.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(String, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    requested_by = Column(String, ForeignKey('users.id'), nullable=False)
    requested_at = Column(DateTime(timezone=True), default=_now_utc)
    status = Column(String, nullable=False, default='pending')
    reviewed_by = Column(String, ForeignKey('users.id'))
    reviewed_at = Column(DateTime(timezone=True))
    rejection_reason = Column(Text)


def _ensure_column(
    inspector, table_name: str, column_name: str, ddl: str, *, update_nulls_sql: Optional[str] = None
) -> None:
    if column_name in {col['name'] for col in inspector.get_columns(table_name)}:
        return
    with engine.begin() as connection:
        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}'))
        if update_nulls_sql:
            connection.execute(text(update_nulls_sql))


def _format_identifier(name: str) -> str:
    if not name:
        return name
    quote_char = '`' if engine.dialect.name == 'mysql' else '"'
    escaped = name.replace(quote_char, quote_char * 2)
    return f'{quote_char}{escaped}{quote_char}'


def _has_unique_combination(inspector, table_name: str, expected_columns: Iterable[str]) -> bool:
    target = tuple(sorted(expected_columns))
    for constraint in inspector.get_unique_constraints(table_name):
        columns = tuple(sorted(constraint.get('column_names') or []))
        if columns == target:
            return True
    for index in inspector.get_indexes(table_name):
        if not index.get('unique'):
            continue
        columns = tuple(sorted(index.get('column_names') or []))
        if columns == target:
            return True
    return False


def _rebuild_sessions_table(existing_columns: List[str]) -> None:
    if engine.dialect.name != 'sqlite':
        return

    with engine.begin() as connection:
        connection.execute(text('PRAGMA foreign_keys=OFF'))
        try:
            connection.execute(text('ALTER TABLE sessions RENAME TO sessions__old'))
            index_rows = connection.execute(text("PRAGMA index_list('sessions__old')")).fetchall()
            for row in index_rows:
                index_name = row[1]
                if index_name and not str(index_name).startswith('sqlite_autoindex'):
                    connection.execute(text(f'DROP INDEX IF EXISTS {_format_identifier(index_name)}'))

            Session.__table__.create(bind=connection, checkfirst=False)

            new_columns = [column.name for column in Session.__table__.columns]
            shared_columns = [col for col in existing_columns if col in new_columns]
            if shared_columns:
                column_csv = ', '.join(shared_columns)
                connection.execute(text(
                    f'INSERT INTO sessions ({column_csv}) SELECT {column_csv} FROM sessions__old'
                ))

            connection.execute(text('DROP TABLE sessions__old'))
        finally:
            connection.execute(text('PRAGMA foreign_keys=ON'))


def _rebuild_students_table(existing_columns: List[str]) -> None:
    if engine.dialect.name != 'sqlite':
        return

    with engine.begin() as connection:
        connection.execute(text('PRAGMA foreign_keys=OFF'))
        try:
            connection.execute(text('ALTER TABLE students RENAME TO students__old'))
            index_rows = connection.execute(text("PRAGMA index_list('students__old')")).fetchall()
            for row in index_rows:
                index_name = row[1]
                if index_name and not str(index_name).startswith('sqlite_autoindex'):
                    connection.execute(text(f'DROP INDEX IF EXISTS {_format_identifier(index_name)}'))

            Student.__table__.create(bind=connection, checkfirst=False)

            new_columns = [column.name for column in Student.__table__.columns]
            shared_columns = [col for col in existing_columns if col in new_columns]
            if shared_columns:
                column_csv = ', '.join(shared_columns)
                connection.execute(text(
                    f'INSERT INTO students ({column_csv}) SELECT {column_csv} FROM students__old'
                ))

            connection.execute(text('DROP TABLE students__old'))
        finally:
            connection.execute(text('PRAGMA foreign_keys=ON'))


def _ensure_session_name_scope(inspector):
    table_name = 'sessions'
    if table_name not in inspector.get_table_names():
        return inspector

    dialect_name = engine.dialect.name
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    unique_constraints = inspector.get_unique_constraints(table_name)
    indexes = inspector.get_indexes(table_name)

    drop_constraint_names: List[str] = []
    drop_index_names: List[str] = []
    requires_rebuild = False

    for constraint in unique_constraints:
        columns = constraint.get('column_names') or []
        if set(columns) == {'session_name'}:
            name = constraint.get('name') or ''
            if dialect_name == 'sqlite' and (not name or name.startswith('sqlite_autoindex')):
                requires_rebuild = True
            elif name:
                drop_constraint_names.append(name)

    for index in indexes:
        columns = index.get('column_names') or []
        if index.get('unique') and len(columns) == 1 and columns[0] == 'session_name':
            name = index.get('name') or ''
            if dialect_name == 'sqlite' and name.startswith('sqlite_autoindex'):
                requires_rebuild = True
            elif name:
                drop_index_names.append(name)

    if drop_index_names or drop_constraint_names:
        with engine.begin() as connection:
            for name in drop_constraint_names:
                if dialect_name == 'sqlite':
                    connection.execute(text(f'DROP INDEX IF EXISTS {_format_identifier(name)}'))
                else:
                    connection.execute(text(
                        f'ALTER TABLE sessions DROP CONSTRAINT IF EXISTS {_format_identifier(name)}'
                    ))
            for name in drop_index_names:
                connection.execute(text(f'DROP INDEX IF EXISTS {_format_identifier(name)}'))

    if requires_rebuild:
        _rebuild_sessions_table(existing_columns)

    inspector = inspect(engine)

    if not _has_unique_combination(inspector, table_name, ('school_id', 'session_name')):
        with engine.begin() as connection:
            if engine.dialect.name == 'sqlite':
                connection.execute(text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_school_session_name '
                    'ON sessions (school_id, session_name)'
                ))
            else:
                connection.execute(text(
                    'ALTER TABLE sessions ADD CONSTRAINT uq_sessions_school_session_name '
                    'UNIQUE (school_id, session_name)'
                ))
        inspector = inspect(engine)

    return inspector


def _dedupe_student_identifiers(connection) -> bool:
    """Resolve legacy duplicate student identifiers within the same school."""
    rows = connection.execute(text(
        '''
        SELECT id, school_id, student_identifier
        FROM students
        ORDER BY school_id, student_identifier, id
        '''
    )).fetchall()
    if not rows:
        return False

    seen_counts = {}
    existing_pairs = {(row.school_id, row.student_identifier) for row in rows}
    planned_updates = []

    for row in rows:
        school_id = row.school_id
        identifier = row.student_identifier or ''
        key = (school_id, identifier)
        count = seen_counts.get(key, 0)
        if count == 0:
            seen_counts[key] = 1
            continue

        suffix = count
        base_identifier = identifier
        while True:
            candidate = f"{base_identifier}__dup{suffix}" if base_identifier else f"__dup{suffix}"
            candidate_key = (school_id, candidate)
            if candidate_key not in existing_pairs:
                break
            suffix += 1

        planned_updates.append((row.id, candidate))
        existing_pairs.add(candidate_key)
        seen_counts[key] = count + 1

    for row_id, new_identifier in planned_updates:
        connection.execute(
            text('UPDATE students SET student_identifier = :identifier WHERE id = :id'),
            {'identifier': new_identifier, 'id': row_id},
        )

    return bool(planned_updates)


def _ensure_student_identifier_scope(inspector):
    table_name = 'students'
    if table_name not in inspector.get_table_names():
        return inspector

    with engine.begin() as connection:
        deduped = _dedupe_student_identifiers(connection)

    if deduped:
        inspector = inspect(engine)

    dialect_name = engine.dialect.name
    existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
    unique_constraints = inspector.get_unique_constraints(table_name)
    indexes = inspector.get_indexes(table_name)

    drop_constraint_names: List[str] = []
    drop_index_names: List[str] = []
    requires_rebuild = False

    for constraint in unique_constraints:
        columns = tuple(sorted(constraint.get('column_names') or ()))
        name = constraint.get('name') or ''
        if columns == ('student_identifier',):
            if dialect_name == 'sqlite' and (not name or name.startswith('sqlite_autoindex')):
                requires_rebuild = True
            elif name:
                drop_constraint_names.append(name)

    for index in indexes:
        if not index.get('unique'):
            continue
        columns = tuple(sorted(index.get('column_names') or ()))
        name = index.get('name') or ''
        if columns == ('student_identifier',):
            if dialect_name == 'sqlite' and name.startswith('sqlite_autoindex'):
                requires_rebuild = True
            elif name:
                drop_index_names.append(name)

    if drop_constraint_names or drop_index_names:
        with engine.begin() as connection:
            for name in drop_constraint_names:
                if dialect_name == 'sqlite':
                    connection.execute(text(f'DROP INDEX IF EXISTS {_format_identifier(name)}'))
                else:
                    connection.execute(text(
                        f'ALTER TABLE students DROP CONSTRAINT IF EXISTS {_format_identifier(name)}'
                    ))
            for name in drop_index_names:
                connection.execute(text(f'DROP INDEX IF EXISTS {_format_identifier(name)}'))

    if requires_rebuild:
        _rebuild_students_table(existing_columns)
        inspector = inspect(engine)
    else:
        inspector = inspect(engine)

    combo_exists = _has_unique_combination(inspector, table_name, ('school_id', 'student_identifier'))

    if not combo_exists:
        with engine.begin() as connection:
            _dedupe_student_identifiers(connection)
            if engine.dialect.name == 'sqlite':
                connection.execute(text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS uq_students_school_identifier '
                    'ON students (school_id, student_identifier)'
                ))
            else:
                connection.execute(text(
                    'ALTER TABLE students ADD CONSTRAINT uq_students_school_identifier '
                    'UNIQUE (school_id, student_identifier)'
                ))
        inspector = inspect(engine)

    return inspector


def _migrate_schema() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if 'sessions' in tables:
        session_columns = {col['name'] for col in inspector.get_columns('sessions')}
        for column_name, ddl in [
            ('draw_number', 'INTEGER DEFAULT 1'),
            ('winner_student_id', 'TEXT'),
            ('method', 'TEXT'),
            ('finalized', 'INTEGER DEFAULT 0'),
            ('finalized_by', 'TEXT'),
            ('finalized_at', 'DATETIME'),
            ('tickets_at_selection', 'INTEGER'),
            ('probability_at_selection', 'INTEGER'),
            ('eligible_pool_size', 'INTEGER'),
            ('override_applied', 'INTEGER DEFAULT 0'),
        ]:
            if column_name not in session_columns:
                with engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE sessions ADD COLUMN {column_name} {ddl}'))
        inspector = _ensure_session_name_scope(inspector)
        tables = set(inspector.get_table_names())

    if 'session_draw_events' in tables and 'session_draws' in tables:
        with engine.begin() as connection:
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
            connection.execute(text('DROP TABLE session_draw_events_old'))
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

    # Handle legacy session_draws table
    if 'session_draws' in tables:
        with engine.begin() as connection:
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

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if 'students' in tables:
        inspector = _ensure_student_identifier_scope(inspector)
        tables = set(inspector.get_table_names())

    if 'draft_pool' in tables:
        draft_columns = {col['name'] for col in inspector.get_columns('draft_pool')}
        if 'session_id' not in draft_columns:
            _ensure_column(inspector, 'draft_pool', 'session_id', 'TEXT')

    if 'user_invite_codes' in tables:
        invite_columns = {col['name'] for col in inspector.get_columns('user_invite_codes')}
        if 'updated_at' not in invite_columns:
            _ensure_column(
                inspector,
                'user_invite_codes',
                'updated_at',
                'DATETIME',
                update_nulls_sql='UPDATE user_invite_codes SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL',
            )

    tables_requiring_school: Iterable[str] = (
        'users',
        'user_invite_codes',
        'students',
        'teachers',
        'sessions',
        'session_records',
        'session_draw_events',
        'session_ticket_events',
        'draft_pool',
        'session_delete_requests',
    )

    for table_name in tables_requiring_school:
        if table_name not in tables:
            continue
        inspector = inspect(engine)
        column_names = {col['name'] for col in inspector.get_columns(table_name)}
        if 'school_id' not in column_names:
            default = DEFAULT_SCHOOL_ID
            _ensure_column(
                inspector,
                table_name,
                'school_id',
                'TEXT',
                update_nulls_sql=f"UPDATE {table_name} SET school_id = '{default}' WHERE school_id IS NULL",
            )

    with engine.begin() as connection:
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_invite_codes_school ON user_invite_codes (school_id)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_records_school_session_category ON session_records (school_id, session_id, category)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_draw_events_school_session ON session_draw_events (school_id, session_id, created_at)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_ticket_events_school_session ON session_ticket_events (school_id, session_id, occurred_at)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_delete_requests_school_session ON session_delete_requests (school_id, session_id)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_students_school ON students (school_id)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_teachers_school ON teachers (school_id)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_sessions_school ON sessions (school_id)'
        ))
        connection.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_users_school ON users (school_id)'
        ))


def _ensure_seed_schools() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            '''
            INSERT INTO schools (id, name, slug, status, created_at, updated_at)
            VALUES (:id, :name, :slug, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, slug = excluded.slug
            '''
        ), {
            'id': DEFAULT_SCHOOL_ID,
            'name': DEFAULT_SCHOOL_NAME,
            'slug': DEFAULT_SCHOOL_SLUG,
        })
        connection.execute(text(
            '''
            INSERT INTO schools (id, name, slug, status, created_at, updated_at)
            VALUES (:id, :name, :slug, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, slug = excluded.slug
            '''
        ), {
            'id': INTERSCHOOL_SCHOOL_ID,
            'name': INTERSCHOOL_SCHOOL_NAME,
            'slug': INTERSCHOOL_SCHOOL_SLUG,
        })


def _ensure_user_school_assignments() -> None:
    with engine.begin() as connection:
        connection.execute(text(
            '''
            UPDATE users
            SET school_id = :default_school
            WHERE school_id IS NULL OR school_id = ''
            '''
        ), {'default_school': DEFAULT_SCHOOL_ID})


_migrate_schema()
Base.metadata.create_all(bind=engine)
_ensure_seed_schools()
_ensure_user_school_assignments()


__all__ = [
    'DATABASE_URL',
    'Base',
    'DEFAULT_SCHOOL_ID',
    'DEFAULT_SCHOOL_NAME',
    'DEFAULT_SCHOOL_SLUG',
    'DraftPool',
    'INTERSCHOOL_SCHOOL_ID',
    'INTERSCHOOL_SCHOOL_NAME',
    'INTERSCHOOL_SCHOOL_SLUG',
    'School',
    'SchoolInviteCode',
    'Session',
    'SessionDeleteRequest',
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
