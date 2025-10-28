def test_login_logout_status(client, login):
    resp = login()
    assert resp.status_code == 200

    status = client.get('/api/auth/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['authenticated'] is True
    assert data['user']['role'] == 'global_admin'
    assert data.get('global_admin', {}).get('active_school') is not None

    superadmin_check = client.post('/api/superadmin/change-role', json={'username': 'antineutrino', 'role': 'admin'})
    assert superadmin_check.status_code == 400

    client.post('/api/auth/logout')
    status = client.get('/api/auth/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['authenticated'] is False


def _create_school_invite(code=None, feature_bundle=None):
    code_value = code or f"INV-{uuid.uuid4().hex[:6].upper()}"

    existing = (
        global_db_session.query(SchoolInvite)
        .filter(SchoolInvite.code == code_value)
        .first()
    )
    if existing:
        existing.school_name = 'New Academy'
        existing.address = '123 Elm Street'
        existing.feature_bundle = feature_bundle
        existing.used_at = None
        global_db_session.add(existing)
        global_db_session.commit()
        return existing

    invite = SchoolInvite(
        code=code_value,
        school_name='New Academy',
        address='123 Elm Street',
        feature_bundle=feature_bundle,
    )
    global_db_session.add(invite)
    global_db_session.commit()
    return invite


def test_school_signup_provisions_school(client):
    invite = _create_school_invite(feature_bundle='{ "student_directory": true, "ticket_draws": false }')
    payload = {
        'invite_code': invite.code,
        'school_name': 'North Ridge Academy',
        'school_address': '123 Campus Way',
        'public_contact': 'contact@nra.edu',
        'owner': {
            'display_name': 'Dean Admin',
            'username': 'nra-admin',
            'password': 'secure-pass',
        },
        'feature_toggles': {
            'student_directory': True,
            'ticket_draws': False,
        },
        'guest_access_enabled': False,
    }

    resp = client.post('/api/auth/school-signup', json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    school_id = data['school']['id']

    school = global_db_session.query(School).filter(School.id == school_id).one()
    assert school.name == 'North Ridge Academy'
    assert school.guest_access_enabled is False

    toggles = {
        toggle.feature: toggle.enabled
        for toggle in global_db_session.query(FeatureToggle).filter(FeatureToggle.school_id == school_id)
    }
    assert toggles.get('student_directory') is True
    assert toggles.get('ticket_draws') is False

    directory_entry = (
        global_db_session.query(UserDirectory)
        .filter(UserDirectory.school_id == school_id, UserDirectory.username == 'nra-admin')
        .one()
    )
    assert directory_entry.role == 'school_super_admin'


def test_school_signup_duplicate_username_scoped_per_school(client):
    invite_one = _create_school_invite(code='INV-A001')
    invite_two = _create_school_invite(code='INV-A002')

    payload = {
        'invite_code': invite_one.code,
        'school_name': 'Riverdale Prep',
        'public_contact': 'admin@riverdale.edu',
        'owner': {
            'display_name': 'Lead Admin',
            'username': 'shared-admin',
            'password': 'initial-pass',
        },
    }

    resp_one = client.post('/api/auth/school-signup', json=payload)
    assert resp_one.status_code == 201

    payload['invite_code'] = invite_two.code
    payload['school_name'] = 'Harborview School'
    resp_two = client.post('/api/auth/school-signup', json=payload)
    assert resp_two.status_code == 201

    directories = (
        global_db_session.query(UserDirectory)
        .filter(UserDirectory.username == 'shared-admin')
        .all()
    )
    assert len(directories) >= 2
    assert {entry.school_id for entry in directories} == {
        resp_one.get_json()['school']['id'],
        resp_two.get_json()['school']['id'],
    }


def test_school_signup_rejects_reused_invite(client):
    invite = _create_school_invite(code='INV-REUSE')
    base_payload = {
        'invite_code': invite.code,
        'school_name': 'Maple Leaf Collegiate',
        'owner': {
            'display_name': 'Maple Admin',
            'username': 'maple-admin',
            'password': 'secret-pass',
        },
    }

    first = client.post('/api/auth/school-signup', json=base_payload)
    assert first.status_code == 201

    second = client.post('/api/auth/school-signup', json=base_payload)
    assert second.status_code == 409


def test_login_failure(client):
    resp = client.post('/api/auth/login', json={'username': 'antineutrino', 'password': 'wrong'})
    assert resp.status_code == 401


def test_guest_login(client):
    resp = client.post('/api/auth/guest')
    assert resp.status_code == 200

    status = client.get('/api/auth/status')
    data = status.get_json()
    assert status.status_code == 200
    assert data['authenticated'] is True
    assert data['user']['role'] == 'guest'

import uuid

from src.routes.golden_plate_recorder_db.global_db import (
    FeatureToggle,
    School,
    SchoolInvite,
    UserDirectory,
    global_db_session,
)
