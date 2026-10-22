"""Give named manual plate entries a stable identity for ticket draws.

Manual entries are intentionally kept outside the current roster
(``Student.is_active == 0``) and their tickets are replayed only from the
current session's records, so each new session starts them at zero.  They
still represent a person who earned or lost tickets, so draw eligibility
treats a clean manual record in the session as sufficient regardless of roster
membership.  Name-only entries need a synthetic, school-scoped identifier so
repeated entries can share one draw identity without appearing in roster
suggestions or roster snapshots.
"""
import json
import uuid

from sqlalchemy import MetaData, Table, Column, String, DateTime, text

from .utils import make_student_key, normalize_house, normalize_name, split_student_key

MANUAL_STUDENT_PREFIX = 'manual:'
BACKFILL_VERSION = 'manual-draw-participants-v1'


def manual_student_identifier(preferred_name, last_name):
    """Return the persistent internal identifier for a name-only manual entry."""
    key = make_student_key(preferred_name, last_name)
    return f'{MANUAL_STUDENT_PREFIX}{key}' if key else ''


def is_manual_student_identifier(value):
    return normalize_name(value).casefold().startswith(MANUAL_STUDENT_PREFIX)


def public_student_identifier(value):
    """Hide the synthetic identifier used for name-only manual participants."""
    value = normalize_name(value)
    return '' if is_manual_student_identifier(value) else value


def _json(value):
    try:
        decoded = json.loads(value or 'null')
        return decoded if isinstance(decoded, dict) else {}
    except (TypeError, ValueError):
        return {}


def backfill_manual_draw_participants(engine):
    """Link legacy name-only manual records to stable draw identities.

    Manual tickets are replayed from the session's own records, so this
    backfill only needs to establish the identity link.  It never writes a
    cumulative ticket balance for a manual participant.
    """
    state = Table('data_migrations', MetaData(),
                  Column('version', String, primary_key=True),
                  Column('applied_at', DateTime, nullable=False))
    state.create(engine, checkfirst=True)
    with engine.begin() as connection:
        claimed = connection.execute(text(
            'INSERT INTO data_migrations (version, applied_at) '
            'VALUES (:version, CURRENT_TIMESTAMP) ON CONFLICT(version) DO NOTHING'
        ), {'version': BACKFILL_VERSION})
        if claimed.rowcount == 0:
            return

        rows = connection.execute(text(
            '''
            SELECT id, school_id, session_id, category, recorded_at, recorded_by,
                   preferred_name, last_name, student_profile, dedupe_key
            FROM session_records
            WHERE is_manual_entry = 1 AND student_id IS NULL
              AND category IN ('clean', 'red')
              AND (dedupe_key IS NULL OR dedupe_key NOT LIKE 'count:%')
            ORDER BY recorded_at, id
            '''
        )).mappings().all()

        groups = {}
        for row in rows:
            profile = _json(row['student_profile'])
            preferred = normalize_name(row['preferred_name'] or profile.get('Preferred'))
            last = normalize_name(row['last_name'] or profile.get('Last'))
            if not preferred and not last:
                preferred, last = split_student_key(row['dedupe_key'])
            if not preferred and not last:
                continue
            supplied_id = normalize_name(profile.get('Student ID'))
            identifier = supplied_id or manual_student_identifier(preferred, last)
            if not identifier:
                continue
            identity = (row['school_id'], identifier.casefold())
            group = groups.setdefault(identity, {
                'identifier': identifier, 'preferred': preferred, 'last': last,
                'grade': normalize_name(profile.get('Grade')),
                'advisor': normalize_name(profile.get('Advisor')),
                'house': normalize_house(profile.get('House')),
                'clan': normalize_name(profile.get('Clan')),
                'records': [],
            })
            group['records'].append(row)

        for (school_id, _), group in groups.items():
            student_id = connection.execute(text(
                'SELECT id FROM students WHERE school_id = :school_id '
                'AND lower(student_identifier) = lower(:identifier)'
            ), {'school_id': school_id, 'identifier': group['identifier']}).scalar()
            if not student_id:
                student_id = str(uuid.uuid4())
                connection.execute(text(
                    '''
                    INSERT INTO students
                        (id, school_id, student_identifier, preferred_name, last_name,
                         grade, advisor, house, clan, is_active)
                    VALUES
                        (:id, :school_id, :identifier, :preferred, :last,
                         :grade, :advisor, :house, :clan, 0)
                    '''
                ), {
                    'id': student_id, 'school_id': school_id,
                    'identifier': group['identifier'], 'preferred': group['preferred'],
                    'last': group['last'], 'grade': group['grade'],
                    'advisor': group['advisor'], 'house': group['house'],
                    'clan': group['clan'],
                })
            updates = []
            for row in group['records']:
                row_profile = _json(row['student_profile'])
                updates.append({
                    'student_id': student_id,
                    'record_id': row['id'],
                    'profile': json.dumps({
                        'Student ID': normalize_name(row_profile.get('Student ID')),
                        'Preferred': normalize_name(row['preferred_name']) or group['preferred'],
                        'Last': normalize_name(row['last_name']) or group['last'],
                        'Grade': normalize_name(row_profile.get('Grade')),
                        'Advisor': normalize_name(row_profile.get('Advisor')),
                        'House': normalize_house(row_profile.get('House')),
                        'Clan': normalize_name(row_profile.get('Clan')),
                    }, ensure_ascii=False),
                })
            connection.execute(text(
                'UPDATE session_records '
                'SET student_id = :student_id, student_profile = COALESCE(student_profile, :profile) '
                'WHERE id = :record_id'
            ), updates)
