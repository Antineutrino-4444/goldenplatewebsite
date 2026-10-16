import io
import json
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import db as database, storage
from src.routes.golden_plate_recorder_db.db import (
    School, Session as Meal, SessionDrawEvent, SessionRecord, Student, Teacher, User, db_session,
)
from src.routes.golden_plate_recorder_db.users import create_user_record


@pytest.fixture
def identity_school(client, login):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=suffix, name='Identity school', slug=suffix)
    db_session.add(school)
    db_session.commit()
    user = create_user_record(suffix, 'identity-password', 'Identity admin', role='admin', school_id=school.id)
    assert login(user.username, 'identity-password').status_code == 200
    return school


def upload(client, content):
    return client.post('/api/teachers/upload', data={'file': (io.BytesIO(content.encode()), 'faculty.csv')})


def meal(client):
    response = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex})
    assert response.status_code == 200
    return response.get_json()['session_id']


def test_faculty_identity_survives_renames_imports_departure_and_restart(client, identity_school):
    assert upload(client, 'Faculty ID,Preferred,Last\nF001,Mary Jo,de la Cruz').status_code == 200
    person = client.get('/api/teachers/list').get_json()['names'][0]
    person_id = person['teacher_id']
    session_id = meal(client)
    response = client.post('/api/record/faculty', json={
        'teacher_id': person_id, 'preferred_name': 'Forged', 'last_name': 'Name',
    })
    assert response.status_code == 200
    assert response.get_json()['preferred_name'] == 'Mary Jo'
    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
    record_id = record.id
    assert record.teacher_id == person_id
    assert client.post(f'/api/session/{session_id}/faculty/pick').status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/finalize').status_code == 200
    event_ids = [row.id for row in db_session.query(SessionDrawEvent).filter_by(session_id=session_id)]

    assert client.patch(f'/api/teachers/{person_id}', json={
        'preferred_name': 'MJ', 'last_name': 'Rivera',
    }).status_code == 200
    storage.session_data.clear()
    db_session.remove()
    for path in ('/api/session/scan-history', '/api/session/history'):
        entry = client.get(path).get_json()['scan_history'][0]
        assert (entry.get('name') or entry.get('display_name')) == 'MJ Rivera'
        assert entry['recorded_name'] == 'Mary Jo de la Cruz'
    pick = client.get('/api/session/status').get_json()['faculty_pick']
    assert pick['display_name'] == 'MJ Rivera' and pick['finalized'] is True
    log = client.get(f'/api/session/{session_id}/draw/summary').get_json()['history']
    assert all(event['faculty_name'] == 'MJ Rivera' for event in log)
    assert all(event['recorded_name'] == 'Mary Jo de la Cruz' for event in log)
    assert 'MJ Rivera' in client.get('/api/export/csv').get_data(as_text=True)
    assert client.post('/api/record/faculty', json={'teacher_id': person_id}).status_code == 409

    assert upload(client, 'Faculty ID,First,Last\nf001,Morgan,Rivera').status_code == 200
    assert client.get('/api/teachers/list').get_json()['names'][0]['teacher_id'] == person_id
    assert client.get('/api/session/scan-history').get_json()['scan_history'][0]['name'] == 'Morgan Rivera'
    assert upload(client, 'Faculty ID,First,Last\nf002,Taylor,Lee').status_code == 200
    assert db_session.get(Teacher, person_id).is_active == 0
    assert client.get('/api/session/status').get_json()['faculty_pick']['display_name'] == 'Morgan Rivera'
    assert upload(client, 'Faculty ID,First,Last\nf001,Morgan,Rivera').status_code == 200
    assert db_session.get(Teacher, person_id).is_active == 1
    record = db_session.get(SessionRecord, record_id)
    assert (record.preferred_name, record.last_name) == ('Mary Jo', 'de la Cruz')
    assert record.teacher_id == person_id
    events = db_session.query(SessionDrawEvent).filter_by(session_id=session_id).all()
    assert [event.id for event in events] == event_ids
    assert all(event.selected_teacher_id == person_id and event.selected_record_id == record_id for event in events)
    assert all(event.faculty_name == 'Mary Jo de la Cruz' for event in events)
    assert db_session.get(Meal, session_id).faculty_number == 1


def test_namesakes_are_separate_people_and_cannot_be_selected_by_name_alone(client, identity_school):
    assert upload(client, 'Faculty ID,First,Last\nf1,Alex,Smith\nf2,Alex,Smith').status_code == 200
    people = client.get('/api/teachers/list').get_json()['names']
    assert len({person['teacher_id'] for person in people}) == 2
    session_id = meal(client)
    assert client.post('/api/record/faculty', json={'input_value': 'Alex Smith'}).status_code == 409
    for person in people:
        assert client.post('/api/record/faculty', json={'teacher_id': person['teacher_id']}).status_code == 200
    assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == 2
    assert upload(client, 'Last,First\nSmith,Alex').status_code == 400


@pytest.mark.parametrize('content', [
    'Faculty ID,Last,First\nf1,Smith,Alex\nF1,Jones,Jamie',
    'Faculty ID,Last,First\n,Smith,Alex',
    'Faculty ID,Last\nf1,Smith',
])
def test_invalid_identity_import_is_atomic(client, identity_school, content):
    assert upload(client, 'Faculty ID,First,Last\nf1,Alex,Smith').status_code == 200
    before = client.get('/api/teachers/list').get_json()
    assert upload(client, content).status_code == 400
    assert client.get('/api/teachers/list').get_json() == before


def test_person_links_and_renames_are_school_scoped(client, identity_school):
    other = School(id=uuid.uuid4().hex, name='Other', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.flush()
    teacher = Teacher(school_id=other.id, name='Foreign Faculty')
    db_session.add(teacher)
    db_session.commit()
    person_id = teacher.id
    session_id = meal(client)
    assert client.post('/api/record/faculty', json={'teacher_id': person_id}).status_code == 404
    assert client.patch(f'/api/teachers/{person_id}', json={'preferred_name': 'New', 'last_name': 'Name'}).status_code == 404
    assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == 0
    assert db_session.get(Teacher, person_id).name == 'Foreign Faculty'


def test_rename_requires_admin_and_failed_save_preserves_the_name(client, identity_school, monkeypatch):
    assert upload(client, 'Faculty ID,First,Last\nf1,Alex,Original').status_code == 200
    person_id = client.get('/api/teachers/list').get_json()['names'][0]['teacher_id']
    def fail():
        raise RuntimeError('Simulated database failure')
    with monkeypatch.context() as context:
        context.setattr(db_session, 'commit', fail)
        assert client.patch(f'/api/teachers/{person_id}', json={
            'preferred_name': 'Avery', 'last_name': 'Updated',
        }).status_code == 500
    assert db_session.get(Teacher, person_id).display_name == 'Alex Original'
    user = create_user_record(uuid.uuid4().hex, 'identity-password', 'Recorder', role='user', school_id=identity_school.id)
    assert client.post('/api/auth/login', json={'username': user.username, 'password': 'identity-password'}).status_code == 200
    assert client.patch(f'/api/teachers/{person_id}', json={
        'preferred_name': 'Avery', 'last_name': 'Updated',
    }).status_code == 403


def test_student_history_resolves_current_name_without_rewriting_original(client, identity_school):
    def roster(first, last):
        content = f'Student ID,First,Last\nstudent1,{first},{last}'
        assert client.post('/api/csv/upload', data={'file': (io.BytesIO(content.encode()), 'students.csv')}).status_code == 200
    roster('Alex', 'Original')
    session_id = meal(client)
    assert client.post('/api/record/clean', json={'input_value': 'student1'}).status_code == 200
    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
    record_id, person_id = record.id, record.student_id
    roster('Avery', 'Updated')
    entry = client.get('/api/session/scan-history').get_json()['scan_history'][0]
    assert entry['name'] == 'Avery Updated' and entry['recorded_name'] == 'Alex Original'
    entry = client.get('/api/session/history').get_json()['scan_history'][0]
    assert entry['display_name'] == 'Avery Updated'
    record = db_session.get(SessionRecord, record_id)
    assert record.student_id == person_id
    assert json.loads(record.student_profile)['Preferred'] == 'Alex'


@pytest.mark.parametrize('name_key', ['school_id, name', 'name'])
def test_active_database_migration_preserves_ids_fks_and_snapshots(monkeypatch, name_key):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'engine', engine)
    with engine.begin() as connection:
        # Reproduce the original faculty schema, with incoming foreign keys already present.
        connection.execute(text('DROP TABLE teachers'))
        connection.execute(text('CREATE TABLE teachers (id TEXT PRIMARY KEY, school_id TEXT NOT NULL REFERENCES schools(id), '
                                f'name TEXT NOT NULL, display_name TEXT, CONSTRAINT uq_teachers_school_name UNIQUE({name_key}))'))
        connection.execute(School.__table__.insert().values(id='school', name='School', slug='school'))
        connection.execute(User.__table__.insert().values(id='admin', school_id='school', username='admin', display_name='Admin', password_hash='test', role='admin'))
        connection.execute(Meal.__table__.insert().values(id='meal', school_id='school', created_by='admin', session_name='Meal',
                                                         faculty_pick_record_id='record', faculty_pick_display_name='Alex Smith'))
        connection.execute(text("INSERT INTO teachers VALUES ('person', 'school', 'Alex Smith', 'Alex Smith')"))
        connection.execute(SessionRecord.__table__.insert().values(id='record', school_id='school', session_id='meal',
                            category='faculty', preferred_name='Alex', last_name='Smith', dedupe_key='faculty_alex_smith', recorded_by='admin'))
        connection.execute(SessionDrawEvent.__table__.insert().values(id='draw', school_id='school', session_id='meal',
                            event_type='draw', draw_target='faculty', faculty_name='Alex Smith', selected_record_id='record'))
        connection.execute(SessionDrawEvent.__table__.insert().values(id='name-only', school_id='school', session_id='meal',
                            event_type='draw', draw_target='faculty', faculty_name='Alex Smith'))
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
    try:
        database._bootstrap_database()
        database._bootstrap_database()
        with engine.connect() as connection:
            record = connection.execute(SessionRecord.__table__.select()).one()
            event = connection.execute(SessionDrawEvent.__table__.select().where(SessionDrawEvent.id == 'draw')).one()
            assert record.id == 'record' and record.teacher_id == 'person'
            assert record.preferred_name == 'Alex' and record.last_name == 'Smith'
            assert event.id == 'draw' and event.selected_teacher_id == 'person'
            assert connection.execute(text("SELECT selected_teacher_id FROM session_draw_events WHERE id='name-only'")).scalar_one() == 'person'
            assert connection.execute(text("SELECT faculty_pick_teacher_id FROM sessions WHERE id='meal'")).scalar_one() == 'person'
            assert not connection.exec_driver_sql('PRAGMA foreign_key_check').all()
        with engine.begin() as connection:
            connection.execute(Teacher.__table__.insert().values(id='namesake', school_id='school', name='Alex Smith', faculty_identifier='f2'))
            connection.execute(School.__table__.insert().values(id='foreign', name='Foreign', slug='foreign'))
            connection.execute(Teacher.__table__.insert().values(id='foreign-person', school_id='foreign', name='Other Person'))
            for key, preferred, last in [('ambiguous', 'Alex', 'Smith'), ('unmatched', 'Other', 'Person')]:
                connection.execute(SessionRecord.__table__.insert().values(id=key, school_id='school', session_id='meal',
                                   category='faculty', preferred_name=preferred, last_name=last, dedupe_key=key, recorded_by='admin'))
        database._bootstrap_database()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT teacher_id FROM session_records WHERE id='ambiguous'")).scalar_one() is None
            assert connection.execute(text("SELECT teacher_id FROM session_records WHERE id='unmatched'")).scalar_one() is None
        assert {'faculty_identifier', 'is_active'} <= {c['name'] for c in inspect(engine).get_columns('teachers')}
    finally:
        engine.dispose()


def test_legacy_backfill_never_assigns_unmatched_history_to_a_later_arrival(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'engine', engine)
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(id='school', name='School', slug='school'))
        connection.execute(User.__table__.insert().values(id='admin', school_id='school', username='admin',
                                                         display_name='Admin', password_hash='test', role='admin'))
        connection.execute(Meal.__table__.insert().values(id='meal', school_id='school', created_by='admin', session_name='Meal'))
        connection.execute(SessionRecord.__table__.insert().values(id='old-record', school_id='school', session_id='meal',
                           category='faculty', preferred_name='Alex', last_name='Unknown', dedupe_key='legacy', recorded_by='admin'))
        connection.execute(Teacher.__table__.insert(), [
            {'id': 'a', 'school_id': 'school', 'name': 'Jamie Shared', 'display_name': 'Jamie Shared'},
            {'id': 'b', 'school_id': 'school', 'name': 'Old Label', 'display_name': 'Jamie Shared'},
        ])
        connection.execute(SessionRecord.__table__.insert().values(id='ambiguous', school_id='school', session_id='meal',
                           category='faculty', preferred_name='Jamie', last_name='Shared', dedupe_key='ambiguous', recorded_by='admin'))
    try:
        database._bootstrap_database()
        with engine.begin() as connection:
            connection.execute(Teacher.__table__.insert().values(id='newcomer', school_id='school', name='Alex Unknown'))
        database._bootstrap_database()
        with engine.connect() as connection:
            assert all(row.teacher_id is None for row in connection.execute(SessionRecord.__table__.select()))
    finally:
        engine.dispose()
