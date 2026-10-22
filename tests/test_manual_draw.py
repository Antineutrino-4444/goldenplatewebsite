"""Named manual plate entries participate in the Draw Center."""
import io
import json
import uuid

from sqlalchemy import text

from src.routes.golden_plate_recorder_db import db as database
from src.routes.golden_plate_recorder_db.db import (
    DraftPool, SessionRecord, SessionTicketEvent, Student, db_session,
)
from src.routes.golden_plate_recorder_db.draw_db import get_student_ticket_balance
from src.routes.golden_plate_recorder_db.manual_draw import (
    backfill_manual_draw_participants, manual_student_identifier,
)


def upload_roster(client, rows):
    content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    content += ''.join(f'{identifier},{last},{preferred},9,Advisor,Barn,Alpha\n'
                       for identifier, last, preferred in rows)
    return client.post('/api/csv/upload', data={
        'file': (io.BytesIO(content.encode()), 'students.csv'),
    }, content_type='multipart/form-data')


def named_manual_clean(client, name='Manual Person'):
    return client.post('/api/record/clean', json={'input_value': name})


def test_named_manual_clean_enters_draw_and_can_finalize(client, login):
    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'manual-{uuid.uuid4().hex}',
    }).get_json()['session_id']

    response = named_manual_clean(client)
    assert response.status_code == 200
    assert response.get_json()['is_manual_entry'] is True
    # The synthetic internal identity never appears as a student ID.
    assert response.get_json()['student_id'] == ''

    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['eligible_count'] == 1
    assert summary['total_tickets'] == 1
    candidate = summary['candidates'][0]
    assert candidate['display_name'] == 'Manual Person'
    assert candidate['student_identifier'] == ''
    assert candidate['key'] == 'manual|person'
    assert candidate['tickets'] == 1

    draw = client.post(f'/api/session/{session_id}/draw/start', json={})
    assert draw.status_code == 200
    winner = draw.get_json()['winner']
    assert winner['display_name'] == 'Manual Person'
    assert winner['key'] == 'manual|person'

    finalize = client.post(f'/api/session/{session_id}/draw/finalize', json={})
    assert finalize.status_code == 200
    assert finalize.get_json()['winner']['display_name'] == 'Manual Person'

    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['draw_info']['finalized'] is True
    assert summary['draw_info']['winner']['display_name'] == 'Manual Person'
    assert summary['candidates'] == []
    student = db_session.query(Student).filter_by(
        student_identifier=manual_student_identifier('Manual', 'Person')
    ).one()
    assert get_student_ticket_balance(student.id) == 0


def test_named_manual_clean_with_unmatched_student_id_enters_draw(client, login):
    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'manual-id-{uuid.uuid4().hex}',
    }).get_json()['session_id']

    response = client.post('/api/record/clean', json={
        'student_id': 'manual-999', 'preferred_name': 'Manual', 'last_name': 'Id',
    })
    assert response.status_code == 200
    assert response.get_json()['is_manual_entry'] is True

    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    candidate = summary['candidates'][0]
    assert candidate['display_name'] == 'Manual Id'
    assert candidate['student_identifier'] == 'manual-999'
    assert candidate['key'] == 'id:manual-999'
    assert candidate['tickets'] == 1

    override = client.post(f'/api/session/{session_id}/draw/override', json={
        'input_value': 'Manual Id',
    })
    assert override.status_code == 200
    assert override.get_json()['winner']['student_identifier'] == 'manual-999'


def test_manual_tickets_reset_in_each_session(client, login):
    login()
    first_session = client.post('/api/session/create', json={
        'session_name': f'manual-first-{uuid.uuid4().hex}',
    }).get_json()['session_id']
    response = named_manual_clean(client)
    assert response.status_code == 200
    assert response.get_json()['student_id'] == ''
    first_summary = client.get(f'/api/session/{first_session}/draw/summary').get_json()
    assert first_summary['candidates'][0]['tickets'] == 1

    second_session = client.post('/api/session/create', json={
        'session_name': f'manual-second-{uuid.uuid4().hex}',
    }).get_json()['session_id']
    response = named_manual_clean(client)
    assert response.status_code == 200
    assert response.get_json()['student_id'] == ''

    second_summary = client.get(f'/api/session/{second_session}/draw/summary').get_json()
    assert second_summary['candidates'][0]['display_name'] == 'Manual Person'
    assert second_summary['candidates'][0]['tickets'] == 1
    # The previous session keeps its own local total; it is not increased.
    first_summary = client.get(f'/api/session/{first_session}/draw/summary').get_json()
    assert first_summary['candidates'][0]['tickets'] == 1

    student = db_session.query(Student).filter_by(
        student_identifier=manual_student_identifier('Manual', 'Person')
    ).one()
    assert get_student_ticket_balance(student.id) == 0

    client.post('/api/session/create', json={'session_name': f'manual-red-{uuid.uuid4().hex}'})
    response = client.post('/api/record/red', json={'input_value': 'Manual Person'})
    assert response.status_code == 200
    assert response.get_json()['student_id'] == ''
    session_id = client.get('/api/session/status').get_json()['session_id']
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['candidates'] == [] and summary['total_tickets'] == 0


def test_finalized_manual_tickets_stay_consumed(client, login):
    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'manual-consumed-{uuid.uuid4().hex}',
    }).get_json()['session_id']
    assert named_manual_clean(client).status_code == 200
    assert client.post(f'/api/session/{session_id}/draw/start', json={}).status_code == 200
    assert client.post(f'/api/session/{session_id}/draw/finalize', json={}).status_code == 200
    assert client.post(f'/api/session/{session_id}/draw/reset', json={}).status_code == 200

    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['candidates'] == [] and summary['total_tickets'] == 0


def test_manual_participant_survives_roster_replacement(client, login):
    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'manual-roster-{uuid.uuid4().hex}',
    }).get_json()['session_id']
    assert named_manual_clean(client).status_code == 200

    assert upload_roster(client, [('701', 'Roster', 'Riley')]).status_code == 200
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert [candidate['display_name'] for candidate in summary['candidates']] == ['Manual Person']

    # A current roster student who also plates clean joins the same draw.
    assert client.post('/api/record/clean', json={'input_value': '701'}).status_code == 200
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert {candidate['display_name'] for candidate in summary['candidates']} == {
        'Manual Person', 'Riley Roster',
    }
    assert summary['total_tickets'] == 2


def test_manual_participant_can_be_excluded_and_restored(client, login):
    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'manual-exclusion-{uuid.uuid4().hex}',
    }).get_json()['session_id']
    assert named_manual_clean(client).status_code == 200
    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()

    response = client.post(f'/api/session/{session_id}/records/{record.id}/exclusion',
                           json={'excluded': True, 'reason': 'Manual entry correction'})
    assert response.status_code == 200
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['candidates'] == [] and summary['total_tickets'] == 0

    response = client.post(f'/api/session/{session_id}/records/{record.id}/exclusion',
                           json={'excluded': False, 'reason': 'Restore manual entry'})
    assert response.status_code == 200
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['candidates'][0]['display_name'] == 'Manual Person'
    assert summary['candidates'][0]['tickets'] == 1


def test_backfill_links_legacy_name_only_manual_records(client, login, monkeypatch):
    login()
    session_id = client.post('/api/session/create', json={
        'session_name': f'legacy-manual-{uuid.uuid4().hex}',
    }).get_json()['session_id']
    assert named_manual_clean(client).status_code == 200

    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
    student_id = record.student_id
    record.student_id = None
    record.student_profile = None
    db_session.query(SessionTicketEvent).filter_by(student_id=student_id).delete()
    db_session.query(DraftPool).filter_by(student_id=student_id).delete()
    db_session.query(Student).filter_by(id=student_id).delete()
    db_session.execute(text("DELETE FROM data_migrations WHERE version = 'manual-draw-participants-v1'"))
    db_session.commit()

    backfill_manual_draw_participants(database.engine)
    db_session.expire_all()

    record = db_session.query(SessionRecord).filter_by(id=record.id).one()
    assert record.student_id and record.student_id != student_id
    assert json.loads(record.student_profile)['Student ID'] == ''
    student = db_session.get(Student, record.student_id)
    assert student.student_identifier == manual_student_identifier('Manual', 'Person')
    assert student.is_active == 0
    # Manual tickets are session-local and are not written to the global pool.
    assert get_student_ticket_balance(student.id) == 0

    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert summary['candidates'][0]['display_name'] == 'Manual Person'
    assert summary['candidates'][0]['tickets'] == 1
