import io
import uuid

import pytest

from src.routes.golden_plate_recorder_db import storage
from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_ID, RosterSnapshot, School, Student, SessionRecord, _now_utc, db_session,
)
from src.routes.golden_plate_recorder_db.draw_db import get_student_ticket_balance


def upload_roster(client, identifiers):
    content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    content += ''.join(f'{identifier},Student,Name{identifier},9,Advisor,Macdonald - Flavelle,Clan\n'
                       for identifier in identifiers)
    return client.post('/api/csv/upload', data={'file': (io.BytesIO(content.encode()), 'students.csv')})


def test_roster_replacement_hides_departed_students_from_all_draw_paths(client, login):
    login()
    assert upload_roster(client, ['801', '802']).status_code == 200
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for identifier in ['801', '802']:
        assert client.post('/api/record/clean', json={'input_value': identifier}).status_code == 200
    departed = db_session.query(Student).filter_by(student_identifier='801').one()
    original_id = departed.id
    assert client.post(f'/api/session/{session_id}/draw/override', json={'student_key': 'id:801'}).status_code == 200

    other_school = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other school')
    db_session.add(other_school)
    db_session.flush()
    other_student = Student(id=uuid.uuid4().hex, school_id=other_school.id, student_identifier='801', preferred_name='Other', last_name='Student')
    db_session.add(other_student)
    other_id = other_student.id
    db_session.commit()

    response = upload_roster(client, ['802'])
    assert response.status_code == 200 and response.get_json()['students_deactivated'] >= 1
    departed = db_session.get(Student, original_id)
    other_student = db_session.get(Student, other_id)
    assert departed.is_active == 0 and other_student.is_active == 1
    assert get_student_ticket_balance(original_id) == 1
    assert db_session.query(SessionRecord).filter_by(session_id=session_id, student_id=original_id).count() == 1
    assert 'id:801' not in storage.get_student_lookup_for_school(DEFAULT_SCHOOL_ID)
    assert [n['student_id'] for n in client.get('/api/csv/student-names').get_json()['names']] == ['802']
    assert client.get('/api/csv/preview').get_json()['pagination']['total_records'] == 1

    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert [c['student_identifier'] for c in summary['candidates']] == ['802']
    assert summary['eligible_count'] == 1 and summary['total_tickets'] == 1
    assert summary['draw_info']['winner'] is None and not summary['draw_info']['has_winner']
    assert client.post(f'/api/session/{session_id}/draw/finalize', json={}).status_code == 400
    for identity in [{'student_key': 'id:801'}, {'input_value': 'Name801 Student'}, {'student_identifier': '801'}]:
        assert client.post(f'/api/session/{session_id}/draw/override', json=identity).status_code in (400, 404)
    result = client.post(f'/api/session/{session_id}/draw/start', json={})
    assert result.status_code == 200 and result.get_json()['winner']['student_identifier'] == '802'

    # Re-uploading the same student restores membership without duplicating history.
    assert upload_roster(client, ['801', '802']).status_code == 200
    departed = db_session.get(Student, original_id)
    assert departed.id == original_id and departed.is_active == 1
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert {c['student_identifier'] for c in summary['candidates']} == {'801', '802'}


def test_invalid_roster_does_not_remove_current_students(client, login):
    login()
    assert upload_roster(client, ['803']).status_code == 200
    content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n804,,Missing,9,Advisor,House,Clan\n'
    response = client.post('/api/csv/upload', data={'file': (io.BytesIO(content.encode()), 'invalid.csv')})
    assert response.status_code == 400
    student = db_session.query(Student).filter_by(student_identifier='803').one()
    assert student.is_active == 1
    assert 'id:803' in storage.get_student_lookup_for_school(DEFAULT_SCHOOL_ID)


def test_roster_filename_persists_and_name_search_covers_all_pages(client, login):
    login()
    identifiers = [str(1000 + i) for i in range(120)]
    assert upload_roster(client, identifiers).status_code == 200
    storage.global_csv_data.clear()  # Metadata must survive clearing the upload cache.
    data = client.get('/api/csv/status').get_json()
    assert data['loaded'] and data['filename'] == 'students.csv' and data['rows_count'] == 120
    response = client.get('/api/csv/preview?per_page=10&search=name1119%20student').get_json()
    assert response['pagination']['total_records'] == 1
    assert response['data'][0]['Preferred'] == 'Name1119'
    assert response['metadata']['filename'] == 'students.csv'
    assert client.get('/api/csv/preview?search=%25').get_json()['data'] == []
    school = db_session.get(School, DEFAULT_SCHOOL_ID)
    school.roster_filename = None
    db_session.commit()
    data = client.get('/api/csv/status').get_json()
    assert data['loaded'] and data['filename'] is None


def test_rankings_require_current_snapshot_membership_even_for_active_historical_students(client, login):
    login()
    assert upload_roster(client, ['811', '812']).status_code == 200
    prior_sessions = []
    for category in ('clean', 'red'):
        meal = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
        prior_sessions.append(meal)
        assert client.post(f'/api/record/{category}', json={'input_value': '811'}).status_code == 200

    assert upload_roster(client, ['812', '813']).status_code == 200
    current = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for identifier in ('812', '813'):
        assert client.post('/api/record/clean', json={'input_value': identifier}).status_code == 200

    school = db_session.get(School, DEFAULT_SCHOOL_ID)
    snapshot_id = school.current_roster_snapshot_id
    school_id, school_slug = school.id, school.slug
    departed = db_session.query(Student).filter_by(school_id=school.id, student_identifier='811').one()
    departed_id = departed.id
    # Legacy rows may still have an active flag. Even recent historical records
    # must not put someone outside the current uploaded roster in the rankings.
    departed.is_active = 1
    departed.house = 'Departed House'
    db_session.query(SessionRecord).filter_by(student_id=departed.id).update({'recorded_at': _now_utc()})
    db_session.commit()
    current_ids = {student.id for student in db_session.query(Student).filter(
        Student.school_id == school.id, Student.student_identifier.in_(['812', '813']),
    )}

    for url in ('/api/leaderboards', '/api/session/individual-rankings'):
        response = client.get(url)
        assert response.status_code == 200
        standings = response.get_json()
        for metric in ('tickets', 'clean'):
            assert {row['student_id'] for row in standings[metric]['students']} == current_ids
            assert all(row['count'] == 1 and row['stats']['draw_odds'] == 50
                       for row in standings[metric]['students'])
        assert standings['red']['students'] == []
    houses = client.get(f'/api/session/{current}/house-stats').get_json()['house_tickets']
    assert not any(house['house'] == 'Departed House' for house in houses)
    assert db_session.get(School, school_id).current_roster_snapshot_id == snapshot_id
    assert db_session.get(Student, departed_id).is_active == 1
    assert db_session.query(SessionRecord).filter(SessionRecord.session_id.in_(prior_sessions)).count() == 2

    # Creating another session refreshes the default school's roster metadata;
    # it must not silently add the historical active identity back to membership.
    assert client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).status_code == 200
    assert {row['student_id'] for row in client.get('/api/leaderboards').get_json()['tickets']['students']} == current_ids

    assert client.post('/api/auth/guest', json={'school_slug': school_slug}).status_code == 200
    standings = client.get('/api/leaderboards').get_json()
    assert len(standings['clean']['students']) == 2
    assert all(row['count'] == 1 for row in standings['clean']['students'])
    assert standings['red']['students'] == []


@pytest.mark.parametrize('roster_state', ['missing', 'empty', 'other-school'])
def test_rankings_do_not_fall_back_to_student_history_without_a_current_roster(client, login, roster_state):
    login()
    assert upload_roster(client, ['814']).status_code == 200
    school = db_session.get(School, DEFAULT_SCHOOL_ID)
    if roster_state == 'empty':
        db_session.get(RosterSnapshot, school.current_roster_snapshot_id).data = '{"members": {}}'
    elif roster_state == 'other-school':
        other = School(id=uuid.uuid4().hex, slug=uuid.uuid4().hex, name='Other school')
        db_session.add(other)
        db_session.get(RosterSnapshot, school.current_roster_snapshot_id).school_id = other.id
    else:
        school.current_roster_snapshot_id = None
    db_session.commit()

    response = client.get('/api/leaderboards')
    assert response.status_code == 200
    standings = response.get_json()
    assert all(standings[metric]['students'] == [] for metric in ('clean', 'red', 'tickets'))
    assert db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, is_active=1).count() == 1
