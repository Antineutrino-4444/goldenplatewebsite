import hashlib
import re
import uuid
from datetime import timedelta

import pytest
from src.main import app
from src.routes.golden_plate_recorder_db import password_recovery_routes as recovery_routes
from src.routes.golden_plate_recorder_db.db import PasswordRecovery, User, _now_utc, db_session
from src.routes.golden_plate_recorder_db.passwords import verify_password
from src.routes.golden_plate_recorder_db.users import create_user_record, get_user_by_id

OLD = 'before-recovery-password'
NEW = 'after-recovery-password'
REQUEST = '/api/auth/password-recovery/request'
INSPECT = '/api/auth/password-recovery/inspect'
RESET = '/api/auth/password-recovery/reset'


@pytest.fixture(autouse=True)
def initialize_accounts(client):
    client.get('/api/auth/status')


def account(*, verified=True, role='user', email=None):
    user = create_user_record('recover-' + uuid.uuid4().hex, OLD, 'Recovery test', role=role,
        email=email or f'{uuid.uuid4().hex}@personal.example', email_verified_at=_now_utc() if verified else None)
    db_session.refresh(user)
    db_session.expunge(user)
    return user


def request_link(client, user, outbox, **kwargs):
    response = client.post(REQUEST, json={'identifier': user.username, 'confirmed': True, **kwargs})
    assert response.status_code == 200
    return re.search(r'/reset-password#token=([^"<]+)', outbox[-1]['htmlContent']).group(1)


@pytest.mark.parametrize('role', ['user', 'admin', 'superadmin', 'inter_school'])
def test_verified_email_login_requires_password_and_uses_real_username(client, role):
    user = account(role=role)
    email, username = user.email, user.username
    for payload in [{'username': email}, {'username': email, 'verification_code': '123456'},
                    {'username': email, 'password': 'incorrect'}]:
        assert client.post('/api/auth/login', json=payload).status_code == 401
    response = client.post('/api/auth/login', json={'username': f' {email.upper()} ', 'password': OLD})
    assert response.status_code == 200
    assert response.json['user']['username'] == username
    with client.session_transaction() as state:
        assert state['username'] == state['user_id'] == username
    assert client.get('/api/auth/status').json['authenticated']


def test_unverified_shared_and_disabled_emails_cannot_login(client):
    first = account(verified=False)
    assert client.post('/api/auth/login', json={'username': first.email, 'password': OLD}).status_code == 401
    email = f'{uuid.uuid4().hex}@shared.example'
    first, second = account(email=email), account(email=email)
    assert client.post('/api/auth/login', json={'username': email, 'password': OLD}).status_code == 401
    assert client.post('/api/auth/login', json={'username': second.username, 'password': OLD}).status_code == 200
    client.post('/api/auth/logout')
    first = get_user_by_id(first.id)
    first.email = f'{uuid.uuid4().hex}@unique.example'; first.status = 'disabled'; db_session.commit()
    assert client.post('/api/auth/login', json={'username': first.email, 'password': OLD}).status_code == 403


@pytest.mark.parametrize('payload', [None, [], {'username': []}, {'username': 'abc', 'password': []}])
def test_invalid_login_payload_is_rejected(client, payload):
    assert client.post('/api/auth/login', json=payload).status_code in {400, 401}


def test_recovery_confirmation_required_and_unverified_unknown_disabled_are_private(client, email_outbox):
    user = account(verified=False)
    assert client.post(REQUEST, json={'identifier': user.username}).status_code == 400
    replies = []
    for identifier in [user.username, 'missing-' + uuid.uuid4().hex]:
        replies.append(client.post(REQUEST, json={'identifier': identifier, 'confirmed': True}).json)
    user = get_user_by_id(user.id)
    user.email_verified_at = _now_utc(); user.status = 'disabled'; db_session.commit()
    replies.append(client.post(REQUEST, json={'identifier': user.username, 'confirmed': True}).json)
    assert all(reply == replies[0] for reply in replies)
    assert email_outbox == []


@pytest.mark.parametrize('role', ['user', 'admin', 'superadmin', 'inter_school'])
def test_recovery_is_single_use_revokes_sessions_and_never_logs_in(client, email_outbox, role):
    user = account(role=role)
    user_id, email = user.id, user.email
    other = app.test_client()
    assert other.post('/api/auth/login', json={'username': user.username, 'password': OLD}).status_code == 200
    token = request_link(client, user, email_outbox)
    saved = db_session.get(PasswordRecovery, user_id)
    assert saved.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in saved.token_hash
    assert OLD not in email_outbox[-1]['htmlContent'] and NEW not in email_outbox[-1]['htmlContent']
    assert client.post(INSPECT, json={'token': token}).status_code == 200
    assert client.get('/api/auth/status').json['authenticated'] is False
    assert client.post(RESET, json={'token': token, 'verification_code': '123456'}).status_code == 400
    assert client.post(RESET, json={'token': token, 'new_password': NEW}).status_code == 200
    assert verify_password(get_user_by_id(user_id).password_hash, NEW)
    assert client.get('/api/auth/status').json['authenticated'] is False
    assert other.get('/api/auth/status').json['authenticated'] is False
    assert client.post(RESET, json={'token': token, 'new_password': OLD}).status_code == 400
    assert client.post('/api/auth/login', json={'username': email, 'password': OLD}).status_code == 401
    assert client.post('/api/auth/login', json={'username': email, 'password': NEW}).status_code == 200


def test_recovery_supports_case_insensitive_email_and_throttles_mail(client, email_outbox):
    user = account()
    token = request_link(client, user, email_outbox, identifier=user.email.upper())
    user_id = user.id
    assert client.post(REQUEST, json={'identifier': user.username, 'confirmed': True}).status_code == 200
    assert len(email_outbox) == 1
    for count in [2, 3]:
        saved = db_session.get(PasswordRecovery, user_id)
        saved.created_at = _now_utc() - timedelta(minutes=2); db_session.commit()
        request_link(client, user, email_outbox)
        assert len(email_outbox) == count
    saved = db_session.get(PasswordRecovery, user_id)
    saved.created_at = _now_utc() - timedelta(minutes=2); db_session.commit()
    client.post(REQUEST, json={'identifier': user.username, 'confirmed': True})
    assert len(email_outbox) == 3
    assert client.post(INSPECT, json={'token': token}).status_code == 400


@pytest.mark.parametrize('change', ['expired', 'password', 'email', 'unverified', 'disabled', 'record_actor', 'deleted'])
def test_stale_links_cannot_change_accounts(client, email_outbox, change):
    user = account()
    user_id = user.id
    token = request_link(client, user, email_outbox)
    user = get_user_by_id(user_id)
    if change == 'expired': db_session.get(PasswordRecovery, user_id).expires_at = _now_utc() - timedelta(seconds=1)
    if change == 'password': user.password_hash = 'changed-by-superadmin'
    if change == 'email': user.email = 'changed@example.com'
    if change == 'unverified': user.email_verified_at = None
    if change == 'disabled': user.status = 'disabled'
    if change == 'record_actor': user.is_record_actor = 1
    if change == 'deleted': db_session.delete(user)
    db_session.commit()
    assert client.post(INSPECT, json={'token': token}).status_code == 400
    assert client.post(RESET, json={'token': token, 'new_password': NEW}).status_code == 400


@pytest.mark.parametrize('password', [None, [], 'short', ' ' * 6, 'x' * 257, OLD])
def test_invalid_new_password_does_not_consume_recovery(client, email_outbox, password):
    user = account()
    token = request_link(client, user, email_outbox)
    assert client.post(RESET, json={'token': token, 'new_password': password}).status_code == 400
    assert client.post(INSPECT, json={'token': token}).status_code == 200
    assert verify_password(get_user_by_id(user.id).password_hash, OLD)


def test_delivery_failure_does_not_change_password(client, email_outbox, monkeypatch):
    user = account(); user_id = user.id
    monkeypatch.setattr(recovery_routes, 'send_email_via_brevo', lambda *a, **kw: {'success': False})
    assert client.post(REQUEST, json={'identifier': user.username, 'confirmed': True}).status_code == 503
    assert db_session.get(PasswordRecovery, user_id).used_at is not None
    assert verify_password(get_user_by_id(user_id).password_hash, OLD)


def test_request_checks_captcha_before_sending(client, email_outbox, monkeypatch):
    user = account()
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', 'configured-test-secret')
    assert client.post(REQUEST, json={'identifier': user.username, 'confirmed': True}).status_code == 400
    assert email_outbox == []


def test_default_development_password_cannot_bypass_production_policy_via_email(client, monkeypatch):
    from src.routes.golden_plate_recorder_db.users import ensure_default_superadmin, DEVELOPMENT_SUPERADMIN_CREDENTIALS
    monkeypatch.setenv('APP_ENV', 'development')
    client.get('/api/auth/status')
    user = ensure_default_superadmin()
    user.email = f'{uuid.uuid4().hex}@personal.example'; user.email_verified_at = _now_utc()
    user.password_hash = DEVELOPMENT_SUPERADMIN_CREDENTIALS[0]['password_hash']; db_session.commit()
    email, username = user.email, user.username
    monkeypatch.setenv('APP_ENV', 'production')
    # Seed credentials are rejected before password verification by the same policy
    # whether entered through the username or verified-email alias.
    monkeypatch.setattr('src.routes.golden_plate_recorder_db.auth_routes._is_default_superadmin_login_attempt', lambda candidate, password: candidate == username)
    monkeypatch.setattr('src.routes.golden_plate_recorder_db.auth_routes.default_admin_credentials_enabled', lambda: False)
    assert client.post('/api/auth/login', json={'username': email, 'password': OLD}).status_code == 401


def test_shared_email_recovery_needs_username_and_uses_configured_origin(client, email_outbox, monkeypatch):
    email = f'{uuid.uuid4().hex}@shared.example'
    first, second = account(email=email), account(email=email)
    monkeypatch.setenv('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca')
    assert client.post(REQUEST, json={'identifier': email, 'confirmed': True}).status_code == 200
    assert email_outbox == []
    response = client.post(REQUEST, json={'identifier': first.username, 'confirmed': True}, headers={'Host': 'untrusted.example'})
    assert response.status_code == 200
    body = email_outbox[-1]['htmlContent']
    assert 'https://goldenplate.ca/reset-password#token=' in body
    assert 'untrusted.example' not in body
    assert db_session.get(PasswordRecovery, second.id) is None


@pytest.mark.parametrize('token', [None, '', 123, [], 'x' * 43, 'x' * 129])
def test_invalid_reset_links_never_authenticate(client, token):
    assert client.post(INSPECT, json={'token': token}).status_code == 400
    assert client.post(RESET, json={'token': token, 'new_password': NEW}).status_code == 400
    assert client.get('/api/auth/status').json['authenticated'] is False


def test_recovery_race_does_not_overwrite_a_concurrent_password_change(client, email_outbox, monkeypatch):
    from src.routes.golden_plate_recorder_db.db import SessionFactory
    from src.routes.golden_plate_recorder_db.passwords import hash_password
    user = account(); token = request_link(client, user, email_outbox)
    valid = recovery_routes._valid_recovery
    def race(data):
        result = valid(data)
        with SessionFactory() as concurrent:
            concurrent.query(User).filter_by(id=user.id).update({'password_hash': hash_password('superadmin-reset-password')})
            concurrent.commit()
        return result
    monkeypatch.setattr(recovery_routes, '_valid_recovery', race)
    assert client.post(RESET, json={'token': token, 'new_password': NEW}).status_code == 400
    assert verify_password(get_user_by_id(user.id).password_hash, 'superadmin-reset-password')


def test_failed_password_commit_keeps_link_and_old_password(client, email_outbox, monkeypatch):
    user = account(); token = request_link(client, user, email_outbox)
    def fail():
        raise RuntimeError('synthetic commit failure')
    with monkeypatch.context() as patch:
        patch.setattr(db_session, 'commit', fail)
        assert client.post(RESET, json={'token': token, 'new_password': NEW}).status_code == 500
    assert verify_password(get_user_by_id(user.id).password_hash, OLD)
    assert client.post(INSPECT, json={'token': token}).status_code == 200


def test_email_login_uses_the_same_international_domain_normalization_as_verification(client):
    user = account(email=f'{uuid.uuid4().hex}@xn--bcher-kva.example')
    identifier = user.email.replace('xn--bcher-kva', 'bücher')
    assert client.post('/api/auth/login', json={'username': identifier, 'password': OLD}).status_code == 200
