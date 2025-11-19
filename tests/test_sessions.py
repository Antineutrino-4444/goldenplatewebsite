import uuid

from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_SLUG,
    Session as SessionModel,
    SessionDrawEvent,
    SessionRecord,
    User,
    db_session,
)


def test_create_and_list_session(client, login):
    login()
    create = client.post('/api/session/create', json={'session_name': 'pytest_session'})
    assert create.status_code == 200
    session_id = create.get_json()['session_id']

    listing = client.get('/api/session/list')
    assert listing.status_code == 200
    data = listing.get_json()
    assert any(s['session_id'] == session_id for s in data['sessions'])


def test_guest_cannot_create_session(client):
    client.post('/api/auth/guest', json={'school_slug': DEFAULT_SCHOOL_SLUG})
    resp = client.post('/api/session/create', json={'session_name': 'guest_session'})
    assert resp.status_code == 401


def test_default_session_name_suffix(client, login):
    login()
    first = client.post('/api/session/create', json={})
    assert first.status_code == 200
    base_name = first.get_json()['session_name']
    second = client.post('/api/session/create', json={})
    assert second.status_code == 200
    assert second.get_json()['session_name'] == f"{base_name}_1"


def test_custom_name_duplicate_rejected(client, login):
    login()
    first = client.post('/api/session/create', json={'session_name': 'dup'})
    assert first.status_code == 200
    second = client.post('/api/session/create', json={'session_name': 'dup'})
    assert second.status_code == 400


def _seed_record_and_draw_event(session_id: str) -> None:
    user = db_session.query(User).filter_by(username='antineutrino').first()
    session_model = db_session.query(SessionModel).filter_by(id=session_id).first()
    school_id = session_model.school_id if session_model else (user.school_id if user else None)
    record = SessionRecord(
        school_id=school_id,
        session_id=session_id,
        category='clean',
        grade='',
        house='',
        is_manual_entry=0,
        recorded_by=user.id,
        dedupe_key=f'test-{uuid.uuid4()}',
        preferred_name='Test',
        last_name='Student',
    )
    db_session.add(record)
    db_session.flush()

    event = SessionDrawEvent(
        school_id=school_id,
        session_id=session_id,
        draw_number=1,
        event_type='draw',
        selected_record_id=record.id,
        created_by=user.id,
    )
    db_session.add(event)
    db_session.commit()


def test_delete_session_removes_related_rows(client, login):
    login()
    create = client.post('/api/session/create', json={'session_name': 'delete_me'})
    assert create.status_code == 200
    session_id = create.get_json()['session_id']

    _seed_record_and_draw_event(session_id)

    resp = client.delete(f'/api/session/delete/{session_id}')
    assert resp.status_code == 200
    assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == 0
    assert db_session.query(SessionDrawEvent).filter_by(session_id=session_id).count() == 0


def test_admin_delete_request_removes_related_rows(client, login):
    login()
    create = client.post('/api/session/create', json={'session_name': 'delete_me_admin'})
    assert create.status_code == 200
    session_id = create.get_json()['session_id']

    _seed_record_and_draw_event(session_id)

    resp = client.post('/api/session/request-delete', json={'session_id': session_id})
    assert resp.status_code == 200
    assert db_session.query(SessionRecord).filter_by(session_id=session_id).count() == 0
    assert db_session.query(SessionDrawEvent).filter_by(session_id=session_id).count() == 0

