import uuid
from datetime import timedelta

import pytest

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
    assert status['user']['email_verified'] is False
    assert status['user']['signup_email_confirmation'] is False
    created_admin = db_session.query(User).filter_by(username='pytest-admin').first()
    assert created_admin is not None
    assert is_password_hash(created_admin.password_hash)
    assert verify_password(created_admin.password_hash, 'pytest-pass')

    # Attempting to reuse the invite should fail
    client.post('/api/auth/logout')
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


def test_school_registration_request_and_approval_store_hashes(client, login, email_outbox):
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
    email_outbox.clear()
    approved = client.post(f'/api/interschool/registration-requests/{registration_request.id}/approve')
    assert approved.status_code == 200
    assert approved.get_json()['approval_email_sent'] is True
    school = db_session.get(School, approved.get_json()['school']['id'])
    assert school.contact_email == email

    created_admin = db_session.query(User).filter_by(username=registration_request.admin_username).first()
    assert created_admin is not None
    assert is_password_hash(created_admin.password_hash)
    assert verify_password(created_admin.password_hash, password)
    assert created_admin.email == email
    assert created_admin.email_verified_at is not None

    assert len(email_outbox) == 1
    message = email_outbox[0]
    assert message['to'] == [{'email': email}]
    assert 'Your school has been approved' in message['subject']
    assert school.name in message['htmlContent']
    assert created_admin.username in message['htmlContent']
    assert password not in message['htmlContent']
    assert created_admin.password_hash not in message['htmlContent']

    # Reprocessing cannot send a second approval email.
    assert client.post(f'/api/interschool/registration-requests/{registration_request.id}/approve').status_code == 400
    assert len(email_outbox) == 1

    client.post('/api/auth/logout')
    first_login = login(username=email, password=password)
    assert first_login.status_code == 200
    first_user = first_login.get_json()['user']
    assert first_user['email'] == email
    assert first_user['email_verified'] is True
    assert first_user['signup_email_confirmation'] is True
    assert client.get('/api/auth/status').get_json()['user']['signup_email_confirmation'] is True

    client.post('/api/auth/logout')
    next_login = login(username=created_admin.username, password=password)
    assert next_login.status_code == 200
    assert next_login.get_json()['user']['signup_email_confirmation'] is False
    assert next_login.get_json()['user']['email_verified'] is True


@pytest.mark.parametrize('raises', [False, True])
def test_school_approval_survives_email_delivery_failure(client, login, monkeypatch, raises):
    from src.routes.golden_plate_recorder_db import interschool_routes

    login(username='inter-school-admin')
    suffix = uuid.uuid4().hex[:10]
    registration = SchoolRegistrationRequest(
        email=f'approval-{suffix}@example.com', school_name=f'Approval {suffix}',
        school_slug=f'approval-{suffix}', admin_username=f'approval-{suffix}',
        admin_password_hash='legacy-password', admin_display_name='Applicant',
    )
    db_session.add(registration)
    db_session.commit()

    def fail_after_save(school, admin):
        assert db_session.get(SchoolRegistrationRequest, registration.id).status == 'approved'
        assert db_session.get(User, admin.id).email_verified_at is not None
        if raises:
            raise RuntimeError('Transport unavailable')
        return {'success': False}

    monkeypatch.setattr(interschool_routes, 'notify_school_approval', fail_after_save)
    response = client.post(f'/api/interschool/registration-requests/{registration.id}/approve')
    assert response.status_code == 200
    result = response.get_json()
    assert result['approval_email_sent'] is False
    assert 'approval email could not be sent' in result['message']
    assert db_session.get(School, result['school']['id']).status == 'active'
    assert db_session.get(SchoolRegistrationRequest, registration.id).status == 'approved'
    client.post('/api/auth/logout')
    signed_in = client.post('/api/auth/login', json={
        'username': registration.admin_username, 'password': 'legacy-password',
    })
    assert signed_in.status_code == 200
    assert signed_in.get_json()['user']['email'] == registration.email
