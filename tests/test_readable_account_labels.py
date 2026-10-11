import csv
import io
import uuid

from conftest import TEST_SUPERADMIN_USERNAME
from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_ID, INTERSCHOOL_SCHOOL_ID, School,
    Session as SessionModel, SessionDrawEvent, SessionRecord, User, db_session,
)
from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db, session_data
from src.routes.golden_plate_recorder_db.users import readable_user_label, user_labels_for_school


def test_session_owner_is_readable_after_cache_loss(client, login):
    login()
    created = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()
    session_id = created['session_id']
    owner = db_session.query(User).filter_by(username=TEST_SUPERADMIN_USERNAME).first()
    assert created['owner'] == owner.username
    assert db_session.get(SessionModel, session_id).created_by == owner.id

    # Both old cached UUIDs and a rebuilt cache must resolve to the account.
    session_data[session_id]['owner'] = owner.id
    for endpoint in ('/api/session/list', '/api/admin/sessions', '/api/admin/overview'):
        response = client.get(endpoint)
        assert response.status_code == 200
        entry = next(item for item in response.get_json()['sessions'] if item['session_id'] == session_id)
        assert entry['owner'] == owner.username

    session_data.pop(session_id)
    assert hydrate_session_from_db(session_id)['owner'] == owner.username
    assert client.get('/api/session/status').get_json()['owner'] == owner.username
    assert client.post(f'/api/session/switch/{session_id}').get_json()['owner'] == owner.username


def test_draw_author_is_readable_without_changing_audit_reference(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    owner = db_session.query(User).filter_by(username=TEST_SUPERADMIN_USERNAME).first()
    owner_id, username = owner.id, owner.username
    event = SessionDrawEvent(
        school_id=owner.school_id, session_id=session_id,
        draw_number=1, event_type='draw', created_by=owner.id,
    )
    db_session.add(event)
    db_session.commit()
    event_id = event.id
    response = client.get(f'/api/session/{session_id}/draw/summary')
    assert response.status_code == 200
    assert response.get_json()['history'][0]['created_by'] == username
    assert db_session.get(SessionDrawEvent, event_id).created_by == owner_id


def test_detailed_export_resolves_authors_after_hydration(client, login):
    login()
    session_id = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex}).get_json()['session_id']
    assert client.post('/api/record/faculty', json={'input_value': 'Example Faculty'}).status_code == 200
    owner = db_session.query(User).filter_by(username=TEST_SUPERADMIN_USERNAME).first()
    record = db_session.query(SessionRecord).filter_by(session_id=session_id).one()
    record_id = record.id
    assert record.recorded_by == owner.id
    session_data.pop(session_id)
    hydrate_session_from_db(session_id)

    response = client.get('/api/export/csv/detailed')
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
    assert rows[0]['Recorded By'] == owner.username
    assert owner.id not in response.get_data(as_text=True)
    assert db_session.get(SessionRecord, record_id).recorded_by == owner.id


def test_legacy_roster_uploader_ids_are_readable(client, login):
    login()
    owner = db_session.query(User).filter_by(username=TEST_SUPERADMIN_USERNAME).first()
    school_id = owner.school_id
    username = owner.username
    school = db_session.get(School, school_id)
    previous = school.roster_uploaded_by, school.teacher_roster_uploaded_by
    school.roster_uploaded_by = owner.id
    school.teacher_roster_uploaded_by = owner.id
    db_session.commit()
    try:
        assert client.get('/api/csv/status').get_json()['uploaded_by'] == username
        from src.routes.golden_plate_recorder_db.teacher_routes import _teacher_roster_metadata
        assert _teacher_roster_metadata(school_id)['uploaded_by'] == username
    finally:
        school = db_session.get(School, school_id)
        school.roster_uploaded_by, school.teacher_roster_uploaded_by = previous
        db_session.commit()


def test_readable_labels_stay_within_school_and_handle_missing_accounts(client, login):
    login()
    labels = user_labels_for_school(DEFAULT_SCHOOL_ID)
    other_account = db_session.query(User).filter_by(school_id=INTERSCHOOL_SCHOOL_ID).first()
    assert other_account is not None
    assert readable_user_label(other_account.id, labels=labels) == 'Unavailable account'
    assert readable_user_label(str(uuid.uuid4()), labels=labels) == 'Unavailable account'
    assert readable_user_label('legacy-username', labels=labels) == 'legacy-username'
    assert readable_user_label(None, labels=labels) == 'Unknown account'
