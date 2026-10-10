import io
import uuid

from src.routes.golden_plate_recorder_db.db import Session as SessionModel, db_session
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db


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
    response = client.post(f'{url}/pick', json={'confirm_redraw': True})
    assert response.status_code == 200 and response.get_json()['faculty']['finalized'] is False
    history = client.get(f'/api/session/{session_id}/draw/summary').get_json()['history']
    assert [event['event_type'] for event in history] == ['faculty_draw', 'faculty_finalize', 'faculty_draw']


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
