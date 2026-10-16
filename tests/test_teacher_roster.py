import io
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import db as database, storage
from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, School, Teacher, db_session


def upload_teachers(client, names, filename='teachers.txt'):
    content = '\n'.join(names).encode('utf-8')
    return client.post('/api/teachers/upload', data={'file': (io.BytesIO(content), filename)})


def test_teacher_filename_and_metadata_survive_cache_reset_and_legacy_rosters(client, login):
    login()
    response = upload_teachers(client, ['Last,Preferred', 'Smith,J', 'Morgan,A'], filename='faculty.csv')
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
    assert upload_teachers(client, ['First,Last', *[f'Teacher,{i:03}' for i in range(120)]]).status_code == 200
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
    assert upload_teachers(client, ['Faculty ID,Last,Preferred', 'roster-alex,Morgan,Alex', 'roster-jamie,Smith,Jamie']).status_code == 200
    retained_id = db_session.query(Teacher).filter_by(school_id=DEFAULT_SCHOOL_ID, faculty_identifier='roster-jamie').one().id
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    alex_id = db_session.query(Teacher).filter_by(school_id=DEFAULT_SCHOOL_ID, faculty_identifier='roster-alex').one().id
    assert client.post('/api/record/faculty', json={'teacher_id': alex_id}).status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/pick').status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/finalize').status_code == 200
    log_before = client.get(f'/api/session/{session_id}/draw/summary').get_json()['history']
    school = School(id=uuid.uuid4().hex, name='Other School', slug=uuid.uuid4().hex)
    db_session.add(school)
    db_session.flush()
    other_teacher = Teacher(id=uuid.uuid4().hex, school_id=school.id, name='Alex Morgan')
    db_session.add(other_teacher)
    other_id = other_teacher.id
    db_session.commit()

    response = upload_teachers(client, ['Faculty ID,First,Last', 'roster-jamie,jamie,smith', 'roster-taylor,Taylor,Lee', 'roster-taylor,Taylor,Lee'], 'new-teachers.txt')
    assert response.status_code == 200
    assert response.get_json()['count'] == 2
    names = client.get('/api/teachers/list').get_json()
    assert {teacher['display_name'] for teacher in names['names']} == {'jamie smith', 'Taylor Lee'}
    assert db_session.query(Teacher).filter_by(id=retained_id).count() == 1
    assert db_session.get(Teacher, other_id).name == 'Alex Morgan'
    assert names['metadata']['filename'] == 'new-teachers.txt'
    assert client.get('/api/session/status').get_json()['faculty_clean_count'] == 1
    assert client.get('/api/session/status').get_json()['faculty_pick']['finalized'] is True
    assert client.get(f'/api/session/{session_id}/draw/summary').get_json()['history'] == log_before


@pytest.mark.parametrize('filename', ['teachers.CSV', 'teachers.TXT'])
@pytest.mark.parametrize('content, expected_names', [
    ('Last,Preferred\nSmith,Alex\n', {'Alex Smith'}),
    ('First,Last\nAlex,Smith\n', {'Alex Smith'}),
    ('FIRST,LaSt,pReFeRrEd\nAlexander,Smith,Alex\n', {'Alex Smith'}),
    ('\ufeff last , FIRST ,Title,Email\nSmith,Alex,Dr,ignored@example.com\n', {'Alex Smith'}),
    ('LAST,preferred,Student ID,student id\nSmith,Alex,1,2\n', {'Alex Smith'}),
    ('Preferred,Last\nAlex,Smith\naLEX,sMITH\nJamie,Morgan\n', {'Alex Smith', 'Jamie Morgan'}),
    ('First,Last,Preferred\nAlexander,Smith,\nJamie,Morgan,Jay\n', {'Jay Morgan'}),
    ('preferred,last\nAlex,\n,Smith\nJamie,Morgan\n', {'Jamie Morgan'}),
    ('LAST,FIRST\n"Smith, Jr.",Alex\n', {'Alex Smith, Jr.'}),
])
def test_teacher_roster_matches_name_columns(client, login, content, expected_names, filename):
    login()
    response = upload_teachers(client, content.splitlines(), filename=filename)
    assert response.status_code == 200
    assert response.get_json()['count'] == len(expected_names)
    result = client.get('/api/teachers/list').get_json()
    assert {teacher['display_name'] for teacher in result['names']} == expected_names
    assert {teacher['name'] for teacher in result['names']} == expected_names
    assert {teacher['name'] for teacher in client.get('/api/teachers/preview').get_json()['data']} == expected_names


def test_teacher_csv_case_changes_keep_existing_identity(client, login):
    login()
    assert upload_teachers(client, ['Last,Preferred', 'Smith,Alex'], filename='teachers.csv').status_code == 200
    teacher_id = db_session.query(Teacher).filter_by(school_id=DEFAULT_SCHOOL_ID, name='Alex Smith').one().id
    response = upload_teachers(client, ['FIRST,LAST', 'aLEX,sMITH'], filename='teachers.csv')
    assert response.status_code == 200
    assert response.get_json()['teachers_created'] == 0
    assert response.get_json()['teachers_removed'] == 0
    assert client.get('/api/teachers/list').get_json()['names'][0]['display_name'] == 'aLEX sMITH'
    assert db_session.get(Teacher, teacher_id).name == 'Alex Smith'
    assert db_session.get(Teacher, teacher_id).preferred_name == 'aLEX'
    assert db_session.get(Teacher, teacher_id).last_name == 'sMITH'


def test_teacher_name_parts_survive_reload_and_update_without_changing_identity(client, login):
    login()
    assert upload_teachers(client, ['Last,First,Preferred', 'de la Cruz,Mary Jane,Mary Jo']).status_code == 200
    teacher = db_session.query(Teacher).filter_by(school_id=DEFAULT_SCHOOL_ID, is_active=1).one()
    teacher_id = teacher.id
    assert (teacher.preferred_name, teacher.last_name) == ('Mary Jo', 'de la Cruz')

    storage.global_teacher_data.clear()
    db_session.remove()
    expected = {
        'teacher_id': teacher_id, 'faculty_identifier': None,
        'name': 'Mary Jo de la Cruz', 'display_name': 'Mary Jo de la Cruz',
        'preferred_name': 'Mary Jo', 'last_name': 'de la Cruz',
    }
    assert client.get('/api/teachers/list').get_json()['names'] == [expected]
    assert client.get('/api/teachers/preview').get_json()['data'] == [expected]

    # A corrected boundary between name parts must persist even if the combined name stays the same.
    response = upload_teachers(client, ['First,Last', 'Mary,Jo de la Cruz'])
    assert response.status_code == 200
    assert response.get_json()['teachers_updated'] == 1
    assert response.get_json()['teachers_created'] == response.get_json()['teachers_removed'] == 0
    teacher = db_session.get(Teacher, teacher_id)
    assert (teacher.preferred_name, teacher.last_name) == ('Mary', 'Jo de la Cruz')


@pytest.mark.parametrize('filename', ['invalid.csv', 'invalid.txt'])
@pytest.mark.parametrize('content', [
    '',
    'Alex Smith\nJamie Morgan\n',
    'Smith,Alex\nMorgan,Jamie\n',
    'Name,Email\nAlex Smith,alex@example.com\n',
    'First\nAlex\n',
    'Last\nSmith\n',
    'Last,First,Preferred\nSmith,Alexander,\n',
    'LAST,FIRST\nSmith,\n',
    'LAST,FIRST\n,Alex\n',
    'Last,Preferred,preferred\nSmith,Alex,Alexander\n',
    'Last,LAST,First\nSmith,Morgan,Alex\n',
    'Last,First,FIRST\nSmith,Alex,Alexander\n',
    'Last,First\n',
])
def test_invalid_teacher_roster_preserves_roster(client, login, content, filename):
    login()
    assert upload_teachers(client, ['Last,Preferred', 'Teacher,Original']).status_code == 200
    original = client.get('/api/teachers/list').get_json()
    original_cache = storage.global_teacher_data[DEFAULT_SCHOOL_ID].copy()
    response = upload_teachers(client, content.splitlines(), filename=filename)
    assert response.status_code == 400
    assert response.get_json()['error']
    assert client.get('/api/teachers/list').get_json() == original
    assert storage.global_teacher_data[DEFAULT_SCHOOL_ID] == original_cache


def test_empty_or_failed_teacher_upload_preserves_current_database(client, login, monkeypatch):
    login()
    assert upload_teachers(client, ['Faculty ID,Last,Preferred', 'roster-alex,Morgan,Alex'], 'original.txt').status_code == 200
    original = client.get('/api/teachers/list').get_json()
    assert upload_teachers(client, [' ', '""']).status_code == 400
    assert client.get('/api/teachers/list').get_json() == original

    def fail_commit():
        raise RuntimeError('Simulated database failure')

    with monkeypatch.context() as context:
        context.setattr(db_session, 'commit', fail_commit)
        assert upload_teachers(client, ['Last,First', 'Teacher,New'], 'replacement.txt').status_code == 500
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


@pytest.mark.parametrize('missing_columns', [
    ('preferred_name', 'last_name'), ('preferred_name',), ('last_name',),
])
def test_active_database_bootstrap_adds_only_missing_teacher_fields(monkeypatch, missing_columns):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    monkeypatch.setattr(database, 'engine', engine)
    try:
        with engine.begin() as connection:
            connection.execute(School.__table__.insert().values(id='legacy', name='Legacy', slug='legacy', status='active'))
            connection.execute(Teacher.__table__.insert().values(
                id='teacher', school_id='legacy', name='Mary Jo de la Cruz',
                display_name='Mary Jo de la Cruz', preferred_name='Mary Jo', last_name='de la Cruz',
            ))
            for column in missing_columns:
                connection.execute(text(f'ALTER TABLE teachers DROP COLUMN {column}'))

        database._bootstrap_database()
        database._bootstrap_database()

        assert {'preferred_name', 'last_name'} <= {
            column['name'] for column in inspect(engine).get_columns('teachers')
        }
        with engine.connect() as connection:
            row = connection.execute(Teacher.__table__.select()).one()
            assert row.id == 'teacher' and row.school_id == 'legacy'
            assert row.name == row.display_name == 'Mary Jo de la Cruz'
            # Preserve existing parts; do not guess how to split old combined names.
            assert row.preferred_name == (None if 'preferred_name' in missing_columns else 'Mary Jo')
            assert row.last_name == (None if 'last_name' in missing_columns else 'de la Cruz')
    finally:
        engine.dispose()
