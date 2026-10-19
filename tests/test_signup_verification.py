import uuid
from datetime import timedelta

import pytest

from src.main import app
from src.routes.golden_plate_recorder_db import auth_routes, email_service
from src.routes.golden_plate_recorder_db.db import (
    AccountCreationRequest, DEFAULT_SCHOOL_SLUG, EmailVerification, User,
    UserInviteCode, _now_utc, db_session,
)

SEND_CODE = '/api/auth/signup/send-verification-code'


@pytest.fixture(params=['school', 'invite'])
def applicant(client, login, request):
    suffix = uuid.uuid4().hex[:12]
    payload = dict(username=f'verify-{suffix}', password='signup-test-password',
                   name='Signup Applicant', email=f'Applicant-{suffix}@Example.com')
    if request.param == 'invite':
        login()
        payload['invite_code'] = client.post('/api/admin/invite').get_json()['invite_code']
        client.post('/api/auth/logout')
    else:
        payload['school_code'] = DEFAULT_SCHOOL_SLUG
    return payload


def send_code(client, payload):
    response = client.post(SEND_CODE, json={key: payload[key] for key in ('email', 'school_code', 'invite_code') if key in payload})
    assert response.status_code == 200
    with client.session_transaction() as session:
        challenge_id = session['signup_email_challenge']
    record = db_session.get(EmailVerification, challenge_id)
    return record.id, record.code, response


def assert_no_account(payload):
    assert db_session.query(User).filter_by(username=payload['username']).first() is None
    assert db_session.query(AccountCreationRequest).filter_by(username=payload['username']).first() is None
    if payload.get('invite_code'):
        assert db_session.query(UserInviteCode).filter_by(code=payload['invite_code']).one().status == 'unused'


def test_code_delivery_and_verified_signup(client, applicant, email_outbox, monkeypatch, caplog):
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'reviewer@example.com')
    with caplog.at_level('INFO'):
        challenge_id, code, response = send_code(client, applicant)
    assert len(email_outbox) == 1
    assert email_outbox[0]['to'] == [{'email': applicant['email'].lower()}]
    assert 'Account Email Verification' in email_outbox[0]['htmlContent']
    assert code in email_outbox[0]['htmlContent']
    assert code not in response.get_data(as_text=True)
    assert code not in caplog.text
    assert response.get_json()['expiry_minutes'] == 5
    with client.session_transaction() as session:
        assert code not in str(dict(session))
    applicant['verification_code'] = code
    assert client.post('/api/auth/signup', json=applicant).status_code == 201
    model = User if 'invite_code' in applicant else AccountCreationRequest
    assert db_session.query(model).filter_by(username=applicant['username']).one().email == applicant['email'].lower()
    assert db_session.get(EmailVerification, challenge_id).verified_at is not None
    with client.session_transaction() as session:
        assert 'signup_email_challenge' not in session
    for notification in email_outbox[1:]:
        assert code not in notification['htmlContent']


def test_unverified_signup_cannot_bypass_with_client_flag(client, applicant, email_outbox):
    applicant.update(verification_code='123456', email_verified=True)
    response = client.post('/api/auth/signup', json=applicant)
    assert response.status_code == 400
    assert response.get_json()['code'] == 'SIGNUP_EMAIL_NOT_VERIFIED'
    assert_no_account(applicant)
    assert email_outbox == []


@pytest.mark.parametrize('code', [None, '', 'wrong', '１２３４５６', 123456])
def test_invalid_or_missing_code_preserves_invite_and_request(client, applicant, code):
    send_code(client, applicant)
    applicant['verification_code'] = code
    assert client.post('/api/auth/signup', json=applicant).status_code == 400
    assert_no_account(applicant)


def test_expired_code_is_rejected(client, applicant):
    challenge_id, code, _ = send_code(client, applicant)
    record = db_session.get(EmailVerification, challenge_id)
    record.expires_at = _now_utc() - timedelta(seconds=1)
    db_session.commit()
    applicant['verification_code'] = code
    response = client.post('/api/auth/signup', json=applicant)
    assert response.status_code == 400
    assert 'expired' in response.get_json()['error']
    assert_no_account(applicant)


def test_five_wrong_attempts_block_even_correct_code(client, applicant):
    challenge_id, code, _ = send_code(client, applicant)
    applicant['verification_code'] = '000000' if code != '000000' else '111111'
    for _ in range(5):
        assert client.post('/api/auth/signup', json=applicant).status_code == 400
    applicant['verification_code'] = code
    response = client.post('/api/auth/signup', json=applicant)
    assert response.status_code == 400
    assert 'Too many' in response.get_json()['error']
    assert db_session.get(EmailVerification, challenge_id).attempts == 5
    assert_no_account(applicant)


def test_code_is_bound_to_email_and_browser(client, applicant):
    _, code, _ = send_code(client, applicant)
    applicant['verification_code'] = code
    with app.test_client() as other_client:
        assert other_client.post('/api/auth/signup', json=applicant).status_code == 400
    changed = dict(applicant, email='changed@example.com')
    assert client.post('/api/auth/signup', json=changed).status_code == 400
    assert_no_account(applicant)
    assert client.post('/api/auth/signup', json=applicant).status_code == 201


def test_used_challenge_cannot_be_replayed(client, signup_email_code):
    payload = dict(username=f'replay-{uuid.uuid4().hex[:8]}', password='signup-password',
                   name='Replay Test', email='replay@example.com', school_code=DEFAULT_SCHOOL_SLUG)
    payload['verification_code'] = signup_email_code(payload['email'])
    with client.session_transaction() as session:
        challenge_id = session['signup_email_challenge']
    assert client.post('/api/auth/signup', json=payload).status_code == 201
    with client.session_transaction() as session:
        session['signup_email_challenge'] = challenge_id
    payload['username'] += '-second'
    assert client.post('/api/auth/signup', json=payload).status_code == 400
    assert_no_account(payload)


def test_school_registration_verification_cannot_verify_account(client, signup_email_code):
    email = 'wrong-purpose@example.com'
    code = signup_email_code(email)
    with client.session_transaction() as session:
        challenge_id = session['signup_email_challenge']
    db_session.get(EmailVerification, challenge_id).purpose = 'school_registration'
    db_session.commit()
    payload = dict(username=f'purpose-{uuid.uuid4().hex[:8]}', password='signup-password',
                   name='Purpose Test', email=email, verification_code=code, school_code=DEFAULT_SCHOOL_SLUG)
    assert client.post('/api/auth/signup', json=payload).status_code == 400
    assert_no_account(payload)


def test_resend_cooldown_and_replacement(client, applicant, email_outbox, monkeypatch):
    codes = iter(['123456', '654321'])
    monkeypatch.setattr(email_service, 'generate_verification_code', lambda: next(codes))
    challenge_id, old_code, _ = send_code(client, applicant)
    assert client.post(SEND_CODE, json={key: applicant[key] for key in ('email', 'school_code', 'invite_code') if key in applicant}).status_code == 429
    assert len(email_outbox) == 1
    record = db_session.get(EmailVerification, challenge_id)
    record.created_at = _now_utc() - timedelta(seconds=61)
    db_session.commit()
    _, new_code, _ = send_code(client, applicant)
    applicant['verification_code'] = old_code
    assert client.post('/api/auth/signup', json=applicant).status_code == 400
    applicant['verification_code'] = new_code
    assert client.post('/api/auth/signup', json=applicant).status_code == 201


def test_delivery_failure_reports_error_without_a_usable_challenge(client, applicant, monkeypatch, email_outbox):
    monkeypatch.setattr(auth_routes, 'send_verification_email', lambda *args, **kwargs: {'success': False})
    assert client.post(SEND_CODE, json={key: applicant[key] for key in ('email', 'school_code', 'invite_code') if key in applicant}).status_code == 503
    with client.session_transaction() as session:
        assert 'signup_email_challenge' not in session
    assert db_session.query(EmailVerification).filter_by(email=applicant['email'].lower(), purpose='account_signup').first() is None
    assert_no_account(applicant)
    assert email_outbox == []


def test_failed_account_save_does_not_consume_code(client, applicant, monkeypatch):
    challenge_id, code, _ = send_code(client, applicant)
    applicant['verification_code'] = code
    with monkeypatch.context() as patch:
        def fail_hash(_):
            raise RuntimeError('Simulated account save failure')
        patch.setattr(auth_routes, 'hash_password', fail_hash)
        assert client.post('/api/auth/signup', json=applicant).status_code == 500
    assert db_session.get(EmailVerification, challenge_id).verified_at is None
    assert_no_account(applicant)
    assert client.post('/api/auth/signup', json=applicant).status_code == 201


@pytest.mark.parametrize('email', [None, '', [], 'invalid', 'a@example.com,b@example.com'])
def test_send_code_rejects_invalid_emails(client, email, email_outbox):
    assert client.post(SEND_CODE, json={'email': email}).status_code == 400
    assert email_outbox == []


def test_signed_in_and_guest_sessions_cannot_request_codes(client, login, email_outbox):
    login()
    assert client.post(SEND_CODE, json={'email': 'blocked@example.com'}).status_code == 409
    client.post('/api/auth/logout')
    client.post('/api/auth/guest', json={'school_slug': DEFAULT_SCHOOL_SLUG})
    assert client.post(SEND_CODE, json={'email': 'blocked@example.com'}).status_code == 409
    assert email_outbox == []
