import io
import uuid

from src.routes.golden_plate_recorder_db.db import Session as SessionModel, SessionRecord, Student, Teacher, db_session
from src.routes.golden_plate_recorder_db.draw_db import secure_random
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db
from src.routes.golden_plate_recorder_db.users import create_user_record


def upload_roster(client, identifiers):
    content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    content += ''.join(f'{identifier},Student,Name{identifier},9,Advisor,House,Clan\n' for identifier in identifiers)
    return client.post('/api/csv/upload', data={'file': (io.BytesIO(content.encode()), 'students.csv')})


def test_faculty_finalization_survives_restart_and_redraw_requires_confirmation(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    url = f'/api/session/{session_id}/faculty'
    assert client.post(f'{url}/finalize').status_code == 400
    assert client.post('/api/record/faculty', json={'input_value': 'Alex Morgan'}).status_code == 200
    assert client.post(f'{url}/pick', json={}).status_code == 200
    response = client.post(f'{url}/finalize')
    assert response.status_code == 200 and response.get_json()['faculty']['finalized']
    assert hydrate_session_from_db(session_id)['faculty_pick']['finalized'] is True
    assert client.get('/api/session/status').get_json()['faculty_pick']['finalized'] is True
    assert client.post(f'{url}/finalize').status_code == 200  # No duplicate finalize log.
    assert client.post(f'{url}/pick', json={}).status_code == 409
    history = client.get(f'/api/session/{session_id}/draw/summary').get_json()['history']
    assert [event['event_type'] for event in history] == ['faculty_draw', 'faculty_finalize']
    assert all(event['faculty_name'] == 'Alex Morgan' for event in history)
    assert client.post(f'{url}/pick', json={'confirm_redraw': True}).status_code == 400
    assert client.post('/api/record/faculty', json={'input_value': 'Jamie Doe'}).status_code == 200
    response = client.post(f'{url}/pick', json={'confirm_redraw': True})
    assert response.status_code == 200 and response.get_json()['faculty']['finalized'] is False
    assert response.get_json()['faculty']['display_name'] == 'Jamie Doe'
    history = client.get(f'/api/session/{session_id}/draw/summary').get_json()['history']
    assert [event['event_type'] for event in history] == ['faculty_draw', 'faculty_finalize', 'faculty_draw']


def test_faculty_weights_roster_tickets_across_sessions_and_keeps_manual_tickets_local(client, login, monkeypatch):
    login()
    roster = b'Faculty ID,First,Last\nweight-1,Riley,Roster\nweight-2,Taylor,Roster'
    assert client.post('/api/teachers/upload', data={'file': (io.BytesIO(roster), 'faculty.csv')}).status_code == 200

    def create_session():
        return client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']

    def record(*names):
        for name in names:
            assert client.post('/api/record/faculty', json={'input_value': name}).status_code == 200

    previous_id = create_session()
    record('Riley Roster', 'Casey Manual', 'Taylor Roster')
    # Existing faculty records have no roster marker.
    db_session.query(SessionRecord).filter_by(session_id=previous_id).update({'faculty_roster_entry': None})
    db_session.commit()
    session_id = create_session()
    record('Riley Roster', 'Casey Manual', '')

    def summary():
        return client.get(f'/api/session/{session_id}/draw/summary').get_json()

    standings = summary()['faculty_draw']
    assert standings['total_tickets'] == 3
    assert [(candidate['display_name'], candidate['tickets']) for candidate in standings['candidates']] == [
        ('Riley Roster', 2), ('Casey Manual', 1),
    ]
    assert standings['candidates'][0]['probability'] == 2 / 3 * 100
    monkeypatch.setattr(secure_random, 'random', lambda: 0.6)
    url = f'/api/session/{session_id}/faculty'
    assert client.post(f'{url}/pick').get_json()['faculty']['display_name'] == 'Riley Roster'
    assert summary()['faculty_draw'] == standings
    selection = summary()['history'][-1]
    assert (selection['tickets'], selection['probability'], selection['pool_size']) == (2, 66.67, 2)
    assert client.post(f'{url}/finalize').status_code == 200
    assert summary()['faculty_draw']['total_tickets'] == 1
    new_session_id = create_session()
    record('Riley Roster')
    new_summary_url = f'/api/session/{new_session_id}/draw/summary'
    assert client.get(new_summary_url).get_json()['faculty_draw']['total_tickets'] == 1
    assert client.delete(f'/api/session/delete/{session_id}').status_code == 200
    assert client.get(new_summary_url).get_json()['faculty_draw']['total_tickets'] == 1


def test_finalizing_manual_faculty_draw_preserves_tickets_earned_after_joining_roster(client, login):
    login()
    manual_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert client.post('/api/record/faculty', json={'input_value': 'Jordan Newhire'}).status_code == 200
    assert client.post(f'/api/session/{manual_id}/faculty/pick').status_code == 200
    roster = b'Faculty ID,First,Last\nnewhire,Jordan,Newhire'
    assert client.post('/api/teachers/upload', data={'file': (io.BytesIO(roster), 'faculty.csv')}).status_code == 200
    roster_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert client.post('/api/record/faculty', json={'input_value': 'Jordan Newhire'}).status_code == 200
    assert client.post(f'/api/session/{manual_id}/faculty/finalize').status_code == 200
    assert client.get(f'/api/session/{manual_id}/draw/summary').get_json()['faculty_draw']['total_tickets'] == 0
    assert client.get(f'/api/session/{roster_id}/draw/summary').get_json()['faculty_draw']['total_tickets'] == 1


def test_student_redraw_keeps_public_history_and_requires_explicit_confirmation(client, login):
    login()
    upload_roster(client, ['901', '902'])
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for identifier in ['901', '902']:
        client.post('/api/record/clean', json={'input_value': identifier})
    url = f'/api/session/{session_id}/draw'
    assert client.post(f'{url}/start').status_code == 200
    assert client.post(f'{url}/finalize').status_code == 200
    assert client.post(f'{url}/start', json={'confirm_redraw': 'true'}).status_code == 409
    assert db_session.get(SessionModel, session_id).finalized == 1
    assert client.post(f'{url}/start', json={'confirm_redraw': True}).status_code == 200
    history = client.get(f'{url}/summary').get_json()['history']
    assert [event['event_type'] for event in history] == ['draw', 'finalize', 'draw']


def test_legacy_faculty_winner_has_a_distinct_finalize_log_without_a_linked_record(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    session = db_session.get(SessionModel, session_id)
    session.faculty_pick_display_name = 'Legacy Faculty'
    session.faculty_pick_preferred_name = 'Legacy'
    session.faculty_pick_last_name = 'Faculty'
    db_session.commit()
    assert client.post(f'/api/session/{session_id}/faculty/finalize').status_code == 200
    history = client.get(f'/api/session/{session_id}/draw/summary').get_json()['history']
    assert history[0]['event_type'] == 'faculty_finalize'
    assert history[0]['faculty_name'] == 'Legacy Faculty'


def test_faculty_options_log_comments_and_allow_override_with_zero_tickets(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert client.post('/api/record/faculty', json={'input_value': 'Sam Faculty'}).status_code == 200
    url = f'/api/session/{session_id}/faculty'
    assert client.post(f'{url}/pick', json={'comment': 'Start faculty selection'}).status_code == 200
    assert client.post(f'{url}/finalize', json={'comment': 'Confirm faculty selection'}).status_code == 200
    assert client.post(f'{url}/reset', json={'comment': 'Clear faculty selection'}).status_code == 200
    assert client.get('/api/session/status').get_json()['faculty_pick'] is None
    summary_url = f'/api/session/{session_id}/draw/summary'
    faculty = client.get(summary_url).get_json()['faculty_draw']
    assert faculty['total_tickets'] == 0
    candidate = faculty['override_candidates'][0]
    assert client.post(f'{url}/override', json={
        'record_id': candidate['record_id'], 'comment': 'Manual selection',
    }).get_json()['faculty']['display_name'] == 'Sam Faculty'
    assert client.post(f'{url}/finalize').status_code == 200
    history = client.get(summary_url).get_json()['history']
    assert [(row['event_type'], row['comment']) for row in history[:4]] == [
        ('faculty_draw', 'Start faculty selection'),
        ('faculty_finalize', 'Confirm faculty selection'),
        ('faculty_restore', 'Clear faculty selection'),
        ('faculty_override', 'Manual selection'),
    ]
    assert history[3]['tickets'] == 0
    school_id = db_session.get(SessionModel, session_id).school_id
    admin = create_user_record(f'faculty-admin-{uuid.uuid4().hex}', 'faculty-option-test-password',
                               'Faculty Admin', role='admin', school_id=school_id)
    assert login(admin.username, 'faculty-option-test-password').status_code == 200
    assert client.post(f'{url}/reset').status_code == 403
    assert client.post(f'{url}/override', json={'record_id': candidate['record_id']}).status_code == 403
    assert 'override_candidates' not in client.get(summary_url).get_json()['faculty_draw']


def test_ticket_rankings_carry_balances_across_sessions_and_use_current_houses(client, login):
    login()
    assert upload_roster(client, ['9401', '9402', '9403']).status_code == 200
    roster = b'Faculty ID,First,Last\nrank-faculty,Alex,Ranked'
    assert client.post('/api/teachers/upload', data={'file': (io.BytesIO(roster), 'faculty.csv')}).status_code == 200
    prior = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for student in ['9401', '9402', '9403']:
        assert client.post('/api/record/clean', json={'input_value': student}).status_code == 200
    assert client.post('/api/record/faculty', json={'input_value': 'Alex Ranked'}).status_code == 200
    current = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert current != prior
    assert client.post('/api/record/clean', json={'input_value': '9401'}).status_code == 200
    assert client.post('/api/record/red', json={'input_value': '9402'}).status_code == 200
    assert client.post('/api/record/clean', json={'input_value': ''}).status_code == 200
    by_id = {row.student_identifier: row for row in db_session.query(Student)
             .filter(Student.student_identifier.in_(['9401', '9402', '9403']))}
    by_id['9401'].house = 'Current House'
    by_id['9402'].house = 'Current House'
    by_id['9403'].house = 'Former House'
    by_id['9403'].is_active = 0
    db_session.commit()

    rankings = client.get('/api/leaderboards').get_json()
    assert [(row['display_name'], row['count']) for row in rankings['tickets']['students']] == [
        ('Name9401 Student', 2), ('Name9402 Student', 0),
    ]
    assert [(row['display_name'], row['count']) for row in rankings['tickets']['faculty']] == [('Alex Ranked', 1)]
    assert [row['count'] for row in rankings['clean']['students']] == [2, 1]
    assert [(row['display_name'], row['count']) for row in rankings['red']['students']] == [('Name9402 Student', 1)]
    houses = client.get(f'/api/session/{current}/house-stats').get_json()['house_tickets']
    assert {'house': 'Current House', 'roster_count': 2, 'tickets': 2} in houses
    assert not any(house['house'] == 'Former House' for house in houses)


def test_leaderboard_is_global_without_draw_estimates_and_keeps_finalized_wins(client, login, monkeypatch):
    login()
    assert upload_roster(client, ['9501', '9502']).status_code == 200
    roster = b'Faculty ID,First,Last\nrank-faculty-1,Alex,Ranked\nrank-faculty-2,Alex,Ranked'
    assert client.post('/api/teachers/upload', data={'file': (io.BytesIO(roster), 'faculty.csv')}).status_code == 200
    faculty = {teacher.faculty_identifier: teacher.id for teacher in db_session.query(Teacher).filter(
        Teacher.faculty_identifier.in_(['rank-faculty-1', 'rank-faculty-2']),
    )}

    def make_meal(name):
        return client.post('/api/session/create', json={'session_name': f'{name} {uuid.uuid4().hex}'}).get_json()['session_id']

    def standings():
        return client.get('/api/leaderboards').get_json()

    prior = make_meal('Prior')
    for category, data in [('clean', {'input_value': '9501'}), ('faculty', {'teacher_id': faculty['rank-faculty-1']})]:
        assert client.post(f'/api/record/{category}', json=data).status_code == 200

    prior_results = standings()
    current = make_meal('Current')
    assert standings() == prior_results
    with client.session_transaction() as browser_session:
        browser_session.pop('session_id', None)
    assert standings() == prior_results
    assert client.post(f'/api/session/switch/{current}').status_code == 200
    for identifier in ('9501', '9502'):
        assert client.post('/api/record/clean', json={'input_value': identifier}).status_code == 200
    for teacher_id in faculty.values():
        assert client.post('/api/record/faculty', json={'teacher_id': teacher_id}).status_code == 200

    results = standings()
    assert set(results) == {'clean', 'red', 'tickets', 'historical_tickets'}
    for metric in results.values():
        for rows in metric.values():
            assert all(set(row['stats']) == {'clean', 'red', 'wins', 'clean_rate', 'tickets', 'historical_tickets'} for row in rows)
    teachers = results['clean']['faculty']
    assert [row['faculty_identifier'] for row in teachers] == ['rank-faculty-1', 'rank-faculty-2']
    assert all(row['stats']['red'] is None for row in teachers)
    assert all('student_identifier' not in row for row in results['clean']['students'])

    monkeypatch.setattr(secure_random, 'random', lambda: 0)
    assert client.post(f'/api/session/{current}/draw/start').status_code == 200
    assert standings() == results
    assert client.post(f'/api/session/{current}/draw/finalize').status_code == 200
    results = standings()
    winner, other = results['clean']['students']
    assert (winner['stats']['wins'], winner['stats']['tickets']) == (1, 0)
    assert winner['stats']['historical_tickets'] == 2
    assert (other['stats']['wins'], other['stats']['tickets']) == (0, 1)

    assert client.post(f'/api/session/{current}/faculty/pick').status_code == 200
    assert client.post(f'/api/session/{current}/faculty/finalize').status_code == 200
    finalized_results = standings()
    assert [row['count'] for row in finalized_results['historical_tickets']['faculty']] == [2, 1]
    next_meal = make_meal('Next')
    assert next_meal != prior
    assert standings() == finalized_results
    assert client.post('/api/record/clean', json={'input_value': '9501'}).status_code == 200
    assert client.post('/api/record/faculty', json={'teacher_id': faculty['rank-faculty-1']}).status_code == 200
    results = standings()
    assert client.post(f'/api/session/switch/{current}').status_code == 200
    assert standings() == results
    for group in ('students', 'faculty'):
        winner, other = results['clean'][group]
        assert (winner['stats']['wins'], winner['stats']['tickets']) == (1, 1)
        assert winner['stats']['historical_tickets'] == 3
        assert (other['stats']['wins'], other['stats']['tickets']) == (0, 1)


def test_leaderboard_preserves_student_history_and_keeps_faculty_upload_window(client, login, monkeypatch):
    login()
    assert upload_roster(client, ['9601', '9602']).status_code == 200

    def upload_faculty(rows):
        roster = f'Faculty ID,First,Last\n{rows}'.encode()
        return client.post('/api/teachers/upload', data={'file': (io.BytesIO(roster), 'faculty.csv')})

    assert upload_faculty('retained,Alex,Retained\nremoved,Jamie,Removed').status_code == 200
    prior = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for category, name in [('clean', '9601'), ('red', '9602'), ('faculty', 'Alex Retained')]:
        assert client.post(f'/api/record/{category}', json={'input_value': name}).status_code == 200
    monkeypatch.setattr(secure_random, 'random', lambda: 0)
    for draw, action in [('draw', 'start'), ('faculty', 'pick')]:
        assert client.post(f'/api/session/{prior}/{draw}/{action}').status_code == 200
        assert client.post(f'/api/session/{prior}/{draw}/finalize').status_code == 200

    older = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    for category, name in [('clean', '9601'), ('clean', '9602'), ('faculty', 'Alex Retained'), ('faculty', 'Jamie Removed')]:
        assert client.post(f'/api/record/{category}', json={'input_value': name}).status_code == 200

    assert upload_roster(client, ['9601', '9603']).status_code == 200
    assert upload_faculty('retained,Alex,Retained\nnew,Taylor,New').status_code == 200
    with client.session_transaction() as browser_session:
        browser_session.pop('session_id', None)
    url = '/api/leaderboards'
    result = client.get(url)
    assert result.status_code == 200
    standings = result.get_json()
    assert [(row['display_name'], row['count']) for row in standings['tickets']['students']] == [
        ('Name9601 Student', 1), ('Name9603 Student', 0),
    ]
    assert [(row['display_name'], row['count']) for row in standings['tickets']['faculty']] == [
        ('Alex Retained', 0), ('Taylor New', 0),
    ]
    assert [(row['display_name'], row['count']) for row in standings['historical_tickets']['students']] == [
        ('Name9601 Student', 2), ('Name9603 Student', 0),
    ]
    assert [(row['display_name'], row['count']) for row in standings['historical_tickets']['faculty']] == [
        ('Alex Retained', 2), ('Taylor New', 0),
    ]
    assert [(row['display_name'], row['count']) for row in standings['clean']['students']] == [
        ('Name9601 Student', 2), ('Name9603 Student', 0),
    ]
    assert [(row['display_name'], row['count']) for row in standings['clean']['faculty']] == [
        ('Alex Retained', 0), ('Taylor New', 0),
    ]
    assert standings['red'] == {'students': []}
    assert [row['stats']['wins'] for row in standings['tickets']['students']] == [1, 0]
    assert all(row['stats']['wins'] == 0 for row in standings['tickets']['faculty'])

    assert client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).status_code == 200
    for category, name in [('clean', '9601'), ('faculty', 'Alex Retained'), ('faculty', 'Manual Faculty')]:
        assert client.post(f'/api/record/{category}', json={'input_value': name}).status_code == 200
    standings = client.get(url).get_json()
    for group in ('students', 'faculty'):
        winner, other = standings['tickets'][group]
        assert winner['count'] == winner['stats']['tickets'] == (2 if group == 'students' else 1)
        assert winner['stats']['clean'] == (3 if group == 'students' else 1)
        assert 'draw_odds' not in winner['stats']
        assert winner['stats']['wins'] == (1 if group == 'students' else 0)
        assert other['count'] == 0
        assert 'draw_tickets' not in winner['stats']
    assert db_session.query(SessionRecord).filter_by(session_id=older).count() == 4
