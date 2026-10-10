import io
import uuid

import pytest
from sqlalchemy import create_engine, text

from src.routes.golden_plate_recorder_db import db as database
from src.routes.golden_plate_recorder_db.db import SessionRecord, Student, db_session
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db
from src.routes.golden_plate_recorder_db.utils import normalize_house


@pytest.mark.parametrize('original,expected', [
    ('Macdonald - Flavelle', 'Macdonald'),
    ('  Macdonald - Flavelle  ', 'Macdonald'),
    ('Macdonald', 'Macdonald'),
    ('Macdonald-Flavelle', 'Macdonald-Flavelle'),
    ('Macdonald – Flavelle', 'Macdonald – Flavelle'),
    ('Macdonald — Flavelle', 'Macdonald — Flavelle'),
    ('Macdonald - Flavelle - Other', 'Macdonald - Flavelle - Other'),
    ('Macdonald  -  Flavelle', 'Macdonald  -  Flavelle'),
    ('Macdonald - ', 'Macdonald -'),
    (None, ''),
])
def test_only_exact_two_part_house_labels_are_split(original, expected):
    assert normalize_house(original) == expected


def test_historical_house_migration_is_persistent_and_idempotent(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'engine', engine)
    try:
        with engine.begin() as connection:
            for school_id in ['school-one', 'school-two']:
                connection.execute(Student.__table__.insert().values(
                    id=school_id, school_id=school_id, student_identifier=school_id,
                    preferred_name='Test', last_name='Student', house='Macdonald - Flavelle',
                ))
                connection.execute(SessionRecord.__table__.insert().values(
                    id=school_id, school_id=school_id, session_id='old-session',
                    category='dirty', dedupe_key=school_id, house='Macdonald - Flavelle', recorded_by='test-user',
                ))
            connection.execute(Student.__table__.insert().values(
                id='unsplit', student_identifier='unsplit', preferred_name='Other',
                last_name='Student', house='A - B - C',
            ))
        # Simulate the previous schema and verify automatic startup migration.
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE students DROP COLUMN is_active'))
            for table, columns in {
                'schools': ['roster_filename', 'roster_uploaded_at', 'roster_uploaded_by'],
                'sessions': ['faculty_pick_record_id', 'faculty_finalized', 'faculty_finalized_at'],
                'session_draw_events': ['draw_target', 'faculty_name'],
            }.items():
                for column in columns:
                    connection.execute(text(f'ALTER TABLE {table} DROP COLUMN {column}'))
        database._bootstrap_database()
        database._bootstrap_database()
        with engine.connect() as connection:
            assert connection.execute(text('SELECT house FROM session_records')).scalars().all() == ['Macdonald', 'Macdonald']
            houses = dict(connection.execute(text('SELECT id, house FROM students')).all())
            assert houses == {'school-one': 'Macdonald', 'school-two': 'Macdonald', 'unsplit': 'A - B - C'}
            assert connection.execute(text('SELECT is_active FROM students')).scalars().all() == [1, 1, 1]
    finally:
        engine.dispose()


def test_dirty_house_counts_merge_legacy_labels_and_use_each_house_total(client, login):
    login()
    content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    for identifier, house in [('701', 'Macdonald - Flavelle'), ('702', 'Macdonald'),
                              ('703', 'Macdonald - Flavelle'), ('704', 'Other')]:
        content += f'{identifier},Student,Name{identifier},9,Advisor,{house},Clan\n'
    response = client.post('/api/csv/upload', data={'file': (io.BytesIO(content.encode()), 'roster.csv')})
    assert response.status_code == 200
    assert db_session.query(Student).filter_by(student_identifier='701').one().house == 'Macdonald'
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for category, identifier in [('clean', '701'), ('dirty', '702'), ('red', '703'), ('clean', '704')]:
        assert client.post(f'/api/record/{category}', json={'input_value': identifier}).status_code == 200
    assert client.post('/api/record/dirty', json={}).status_code == 200
    # A legacy label added before restart must also aggregate into the same house.
    record = db_session.query(SessionRecord).filter_by(session_id=session_id, dedupe_key='id:702').one()
    record.house = 'Macdonald - Flavelle'
    db_session.commit()
    data = client.get(f'/api/session/{session_id}/house-stats').get_json()
    assert [h['house'] for h in data['house_stats']] == ['Other', 'Macdonald']
    macdonald = data['house_stats'][1]
    assert (macdonald['clean_count'], macdonald['dirty_count'], macdonald['red_count']) == (1, 1, 1)
    assert macdonald['total_count'] == 3 and macdonald['clean_rate'] == 33.3
    assert data['total_records_with_house'] == 4
    restored = hydrate_session_from_db(session_id)
    assert restored['dirty_records'][0]['house'] == 'Macdonald'
    assert 'Macdonald - Flavelle' not in client.get('/api/export/csv/detailed').get_data(as_text=True)
