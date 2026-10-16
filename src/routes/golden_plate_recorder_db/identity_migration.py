"""Idempotent faculty identity upgrades against the configured SQLAlchemy engine."""
from collections import defaultdict

from sqlalchemy import Column, DateTime, MetaData, String, Table, UniqueConstraint, inspect, text
from sqlalchemy.schema import CreateIndex, CreateTable


def _name_key(columns):
    return set(columns) in ({'name'}, {'school_id', 'name'})


def migrate_faculty_identity(engine):
    inspector = inspect(engine)
    name_constraints = [item for item in inspector.get_unique_constraints('teachers')
                        if _name_key(item['column_names'])]
    name_indexes = [item for item in inspector.get_indexes('teachers')
                    if item.get('unique') and _name_key(item['column_names'])]
    if engine.dialect.name == 'sqlite' and (name_constraints or name_indexes):
        # Copy rather than rename the old table: SQLite must not retarget incoming FKs.
        original = Table('teachers', MetaData(), autoload_with=engine)
        replacement = original.to_metadata(original.metadata, name='teachers__identity')
        for constraint in list(replacement.constraints):
            if isinstance(constraint, UniqueConstraint) and _name_key(constraint.columns.keys()):
                replacement.constraints.remove(constraint)
        quote = engine.dialect.identifier_preparer.quote
        columns = ', '.join(quote(column.name) for column in original.columns)
        with engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql('PRAGMA foreign_keys').scalar()
            connection.commit()
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            connection.commit()
            try:
                with connection.begin():
                    # Explicit BEGIN includes SQLite DDL in the rollback boundary.
                    connection.exec_driver_sql('BEGIN IMMEDIATE')
                    connection.execute(CreateTable(replacement))
                    connection.exec_driver_sql(f'INSERT INTO teachers__identity ({columns}) SELECT {columns} FROM teachers')
                    connection.exec_driver_sql('DROP TABLE teachers')
                    connection.exec_driver_sql('ALTER TABLE teachers__identity RENAME TO teachers')
                    for index in original.indexes:
                        if not (index.unique and _name_key(index.columns.keys())):
                            connection.execute(CreateIndex(index))
            finally:
                connection.exec_driver_sql(f'PRAGMA foreign_keys={int(foreign_keys)}')
                connection.commit()
    elif name_constraints or name_indexes:
        quote = engine.dialect.identifier_preparer.quote
        with engine.begin() as connection:
            for item in name_constraints:
                connection.execute(text(f'ALTER TABLE teachers DROP CONSTRAINT {quote(item["name"])}'))
            for item in name_indexes:
                if not item.get('duplicates_constraint'):
                    connection.execute(text(f'DROP INDEX {quote(item["name"])}'))

    inspector = inspect(engine)
    has_identifier_key = any(set(item['column_names']) == {'school_id', 'faculty_identifier'}
                             for item in inspector.get_unique_constraints('teachers'))
    if not has_identifier_key:
        with engine.begin() as connection:
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_teachers_school_identifier '
                                    'ON teachers (school_id, faculty_identifier)'))
    backfill_faculty_links(engine)


def backfill_faculty_links(engine):
    """Link only unambiguous same-school historical names; retain original snapshots."""
    state = Table('data_migrations', MetaData(),
                  Column('version', String, primary_key=True), Column('applied_at', DateTime, nullable=False))
    state.create(engine, checkfirst=True)
    tables = set(inspect(engine).get_table_names())
    with engine.begin() as connection:
        # Claim the migration in this transaction. A failure rolls back both
        # the links and this marker; subsequent startups never assign old
        # unlinked records to a newly arrived person who happens to share a name.
        claimed = connection.execute(text(
            'INSERT INTO data_migrations (version, applied_at) VALUES (:version, CURRENT_TIMESTAMP) '
            'ON CONFLICT(version) DO NOTHING'
        ), {'version': 'permanent-faculty-identity-v1'})
        if claimed.rowcount == 0:
            return
        names = defaultdict(set)
        for teacher in connection.execute(text('SELECT id, school_id, name, display_name FROM teachers')).mappings():
            for name in (teacher['name'], teacher['display_name']):
                if name:
                    names[(teacher['school_id'], name.strip().casefold())].add(teacher['id'])
        records = connection.execute(text(
            "SELECT id, school_id, preferred_name, last_name FROM session_records "
            "WHERE category = 'faculty' AND teacher_id IS NULL"
        )).mappings().all() if 'session_records' in tables else []
        for record in records:
            name = ' '.join(filter(None, [record['preferred_name'], record['last_name']])).strip().casefold()
            matches = names.get((record['school_id'], name), set())
            if len(matches) == 1:
                connection.execute(text('UPDATE session_records SET teacher_id = :teacher_id '
                                        'WHERE id = :id AND teacher_id IS NULL'),
                                   {'teacher_id': next(iter(matches)), 'id': record['id']})
        if 'session_draw_events' in tables:
            if 'session_records' in tables:
                connection.execute(text(
                    'UPDATE session_draw_events SET selected_teacher_id = '
                    '(SELECT r.teacher_id FROM session_records r WHERE r.id = session_draw_events.selected_record_id '
                    "AND r.school_id = session_draw_events.school_id AND r.category = 'faculty') "
                    "WHERE selected_teacher_id IS NULL AND draw_target = 'faculty'"
                ))
            for event in connection.execute(text(
                "SELECT id, school_id, faculty_name FROM session_draw_events WHERE draw_target = 'faculty' "
                'AND selected_teacher_id IS NULL AND selected_record_id IS NULL'
            )).mappings().all():
                matches = names.get((event['school_id'], (event['faculty_name'] or '').strip().casefold()), set())
                if len(matches) == 1:
                    connection.execute(text('UPDATE session_draw_events SET selected_teacher_id=:person WHERE id=:id'),
                                       {'person': next(iter(matches)), 'id': event['id']})
        if 'sessions' in tables:
            if 'session_records' in tables:
                connection.execute(text(
                    'UPDATE sessions SET faculty_pick_teacher_id = '
                    '(SELECT r.teacher_id FROM session_records r WHERE r.id = sessions.faculty_pick_record_id '
                    "AND r.school_id = sessions.school_id AND r.category = 'faculty') "
                    'WHERE faculty_pick_teacher_id IS NULL AND faculty_pick_record_id IS NOT NULL'
                ))
            for meal in connection.execute(text(
                'SELECT id, school_id, faculty_pick_display_name, faculty_pick_preferred_name, faculty_pick_last_name '
                'FROM sessions WHERE faculty_pick_teacher_id IS NULL AND faculty_pick_record_id IS NULL'
            )).mappings().all():
                name = meal['faculty_pick_display_name'] or ' '.join(filter(None, [
                    meal['faculty_pick_preferred_name'], meal['faculty_pick_last_name']]))
                matches = names.get((meal['school_id'], name.strip().casefold()), set())
                if len(matches) == 1:
                    connection.execute(text('UPDATE sessions SET faculty_pick_teacher_id=:person WHERE id=:id'),
                                       {'person': next(iter(matches)), 'id': meal['id']})
