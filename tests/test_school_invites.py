import uuid
from datetime import timedelta

from src.routes.golden_plate_recorder_db.db import (
    EmailVerification,
    School,
    SchoolInviteCode,
    SchoolRegistrationRequest,
    User,
    _now_utc,
    db_session,
)
from src.routes.golden_plate_recorder_db.passwords import is_password_hash, verify_password


def test_interschool_can_generate_school_invite(client, login):
    login(username='inter-school-admin')
    resp = client.post('/api/interschool/school-invite')
    assert resp.status_code == 201

    data = resp.get_json()
    assert data['status'] == 'success'
    invite_code = data['invite_code']
    school_id = data['school_id']

    invite = db_session.query(SchoolInviteCode).filter_by(code=invite_code).first()
    assert invite is not None
    assert invite.status == 'unused'
    assert invite.school_id == school_id


def test_non_interschool_cannot_generate_school_invite(client, login):
    login()  # default superadmin
    resp = client.post('/api/interschool/school-invite')
    assert resp.status_code == 403


def test_school_registration_flow(client, login):
    # Interschool user issues invite
    login(username='inter-school-admin')
    invite_resp = client.post('/api/interschool/school-invite')
    assert invite_resp.status_code == 201
    invite_data = invite_resp.get_json()
    invite_code = invite_data['invite_code']
    school_id = invite_data['school_id']

    client.post('/api/auth/logout')

    payload = {
        'invite_code': invite_code,
        'school_name': 'Pytest Academy',
        'school_slug': 'pytest-academy',
        'admin_username': 'pytest-admin',
        'admin_password': 'pytest-pass',
        'admin_display_name': 'Pytest Admin',
    }

    register_resp = client.post('/api/auth/register-school', json=payload)
    assert register_resp.status_code == 201
    register_data = register_resp.get_json()
    assert register_data['school']['id'] == school_id

    # Logging in as the new admin should succeed and reflect school assignment
    login(username='pytest-admin', password='pytest-pass')
    status = client.get('/api/auth/status').get_json()
    assert status['authenticated'] is True
    assert status['user']['school_id'] == school_id
    created_admin = db_session.query(User).filter_by(username='pytest-admin').first()
    assert created_admin is not None
    assert is_password_hash(created_admin.password_hash)
    assert verify_password(created_admin.password_hash, 'pytest-pass')

    # Attempting to reuse the invite should fail
    reuse_resp = client.post('/api/auth/register-school', json={
        'invite_code': invite_code,
        'school_name': 'Duplicate Academy',
        'school_slug': 'duplicate-academy',
        'admin_username': 'duplicate-admin',
        'admin_password': 'duplicate-pass',
        'admin_display_name': 'Dup Admin',
    })
    assert reuse_resp.status_code == 403

    # Cleanup created data to keep test isolation
    created_user = db_session.query(User).filter_by(username='pytest-admin').first()
    created_school = db_session.query(School).filter_by(id=school_id).first()
    invite_model = db_session.query(SchoolInviteCode).filter_by(code=invite_code).first()

    try:
        if created_user:
            db_session.delete(created_user)
        if created_school:
            db_session.delete(created_school)
        if invite_model:
            db_session.delete(invite_model)
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise


def test_school_registration_request_and_approval_store_hashes(client, login):
    client.get('/api/auth/status')
    email = f'registration-{uuid.uuid4().hex[:8]}@example.com'
    password = 'approved-pass'
    verification = EmailVerification(
        email=email,
        code='123456',
        purpose='school_registration',
        expires_at=_now_utc() + timedelta(minutes=5),
        verified_at=_now_utc(),
        attempts=0,
    )
    db_session.add(verification)
    db_session.commit()

    register = client.post('/api/auth/register-school', json={
        'email': email,
        'school_name': 'Approval Academy',
        'school_slug': f'approval-academy-{uuid.uuid4().hex[:8]}',
        'admin_username': f'approval-admin-{uuid.uuid4().hex[:8]}',
        'admin_password': password,
        'admin_display_name': 'Approval Admin',
    })
    assert register.status_code == 201

    registration_request = (
        db_session.query(SchoolRegistrationRequest)
        .filter_by(email=email, status='pending')
        .first()
    )
    assert registration_request is not None
    assert is_password_hash(registration_request.admin_password_hash)
    assert verify_password(registration_request.admin_password_hash, password)

    login(username='inter-school-admin')
    approved = client.post(f'/api/interschool/registration-requests/{registration_request.id}/approve')
    assert approved.status_code == 200

    created_admin = db_session.query(User).filter_by(username=registration_request.admin_username).first()
    assert created_admin is not None
    assert is_password_hash(created_admin.password_hash)
    assert verify_password(created_admin.password_hash, password)
