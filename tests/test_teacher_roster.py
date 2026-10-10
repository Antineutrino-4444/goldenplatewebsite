import io
import uuid

from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import db as database, storage
from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, School, Teacher, db_session


def upload_teachers(client, names, filename='teachers.txt'):
    content = '\n'.join(names).encode('utf-8')
    return client.post('/api/teachers/upload', data={'file': (io.BytesIO(content), filename)})


def test_teacher_filename_and_metadata_survive_cache_reset_and_legacy_rosters(client, login):
    login()
    response = upload_teachers(client, ['Smith, J', 'Morgan, A'], filename='faculty.csv')
    assert response.status_code == 200
    assert response.get_json()['filename'] == 'faculty.csv'
    storage.global_teacher_data.clear()
    db_session.remove()
    data = client.get('/api/teachers/list').get_json()
    assert len(data['names']) == 2
    assert data['metadata']['filename'] == 'faculty.csv'
    assert data['metadata']['uploaded_at']
    assert data['metadata']['uploaded_by'] != 'unknown'
    assert client.get('/api/teachers/preview').get_json()['metadata'] == data['metadata']
    school = db_session.get(School, DEFAULT_SCHOOL_ID)
    school.teacher_roster_filename = None
    db_session.commit()
    data = client.get('/api/teachers/list').get_json()
    assert data['status'] == 'success' and data['names'] and data['metadata']['filename'] is None


def test_teacher_search_covers_all_pages_and_display_names(client, login):
    login()
    assert upload_teachers(client, [f'Teacher {i:03}' for i in range(120)]).status_code == 200
    result = client.get('/api/teachers/preview?per_page=10&search=tEAcHeR%20119').get_json()
    assert result['pagination']['total_records'] == 1
    assert result['data'][0]['name'] == 'Teacher 119'
    teacher = db_session.query(Teacher).filter_by(school_id=DEFAULT_SCHOOL_ID, name='Teacher 119').one()
    teacher.display_name = 'Alex Morgan'
    db_session.commit()
    assert client.get('/api/teachers/preview?search=alex%20morgan').get_json()['pagination']['total_records'] == 1
    first = client.get('/api/teachers/preview?per_page=10&search=Teacher%201').get_json()
    second = client.get('/api/teachers/preview?per_page=10&search=Teacher%201&page=2').get_json()
    assert first['pagination']['total_records'] == 20 and first['pagination']['has_next']
    assert len(second['data']) == 10 and not second['pagination']['has_next']
    assert not ({r['name'] for r in first['data']} & {r['name'] for r in second['data']})
    for search in ['no-such-name', '%25', '_']:
        result = client.get('/api/teachers/preview?search=' + search).get_json()
        assert result['status'] == 'success' and result['data'] == []
        assert result['pagination']['total_pages'] == 1


def test_teacher_replacement_is_school_scoped_and_keeps_recorded_history(client, login):
    login()
    assert upload_teachers(client, ['Alex Morgan', 'Jamie Smith']).status_code == 200
    retained_id = db_session.query(Teacher).filter_by(school_id=DEFAULT_SCHOOL_ID, name='Jamie Smith').one().id
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert client.post('/api/record/faculty', json={'input_value': 'Alex Morgan'}).status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/pick').status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/finalize').status_code == 200
    log_before = client.get(f'/api/session/{session_id}/draw/history').get_json()
    school = School(id=uuid.uuid4().hex, name='Other School', slug=uuid.uuid4().hex)
    db_session.add(school)
    db_session.flush()
    other_teacher = Teacher(id=uuid.uuid4().hex, school_id=school.id, name='Alex Morgan')
    db_session.add(other_teacher)
    other_id = other_teacher.id
    db_session.commit()

    response = upload_teachers(client, ['jamie smith', 'Taylor Lee', 'Taylor Lee'], 'new-teachers.txt')
    assert response.status_code == 200
    assert response.get_json()['count'] == 2
    names = client.get('/api/teachers/list').get_json()
    assert {teacher['display_name'] for teacher in names['names']} == {'jamie smith', 'Taylor Lee'}
    assert db_session.query(Teacher).filter_by(id=retained_id).count() == 1
    assert db_session.get(Teacher, other_id).name == 'Alex Morgan'
    assert names['metadata']['filename'] == 'new-teachers.txt'
    assert client.get('/api/session/status').get_json()['faculty_clean_count'] == 1
    assert client.get('/api/session/status').get_json()['faculty_pick']['finalized'] is True
    assert client.get(f'/api/session/{session_id}/draw/history').get_json() == log_before


def test_empty_or_failed_teacher_upload_preserves_current_database(client, login, monkeypatch):
    login()
    assert upload_teachers(client, ['Alex Morgan'], 'original.txt').status_code == 200
    original = client.get('/api/teachers/list').get_json()
    assert upload_teachers(client, [' ', '""']).status_code == 400
    assert client.get('/api/teachers/list').get_json() == original

    def fail_commit():
        raise RuntimeError('Simulated database failure')

    with monkeypatch.context() as context:
        context.setattr(db_session, 'commit', fail_commit)
        assert upload_teachers(client, ['New Teacher'], 'replacement.txt').status_code == 500
    assert client.get('/api/teachers/list').get_json() == original
    assert storage.global_teacher_data[DEFAULT_SCHOOL_ID]['teachers'][0]['name'] == 'Alex Morgan'


def test_teacher_roster_metadata_migrates_existing_schools_without_losing_roster(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'engine', engine)
    columns = ['teacher_roster_filename', 'teacher_roster_uploaded_at', 'teacher_roster_uploaded_by']
    try:
        with engine.begin() as connection:
            connection.execute(School.__table__.insert().values(id='legacy', name='Legacy', slug='legacy', status='active'))
            connection.execute(Teacher.__table__.insert().values(id='teacher', school_id='legacy', name='Legacy Teacher'))
            for column in columns:
                connection.execute(text(f'ALTER TABLE schools DROP COLUMN {column}'))
        database._bootstrap_database()
        database._bootstrap_database()
        assert set(columns) <= {column['name'] for column in inspect(engine).get_columns('schools')}
        with engine.connect() as connection:
            assert connection.execute(text('SELECT name FROM teachers')).scalar_one() == 'Legacy Teacher'
            assert connection.execute(text('SELECT teacher_roster_filename FROM schools WHERE id = :id'), {'id': 'legacy'}).scalar_one() is None
    finally:
        engine.dispose()
