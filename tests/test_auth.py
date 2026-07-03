import uuid

from conftest import TEST_SUPERADMIN_PASSWORD, ensure_test_account_passwords
from src.routes.golden_plate_recorder_db.db import (
    AccountCreationRequest,
    DEFAULT_SCHOOL_ID,
    DEFAULT_SCHOOL_SLUG,
    User,
    _now_utc,
    db_session,
)
from src.routes.golden_plate_recorder_db.passwords import is_password_hash, verify_password
from src.routes.golden_plate_recorder_db.users import DEFAULT_SUPERADMIN, get_user_by_username


def test_login_logout_status(client, login):
    resp = login()
    assert resp.status_code == 200

    status = client.get('/api/auth/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['authenticated'] is True

    client.post('/api/auth/logout')
    status = client.get('/api/auth/status')
    assert status.status_code == 200
    data = status.get_json()
    assert data['authenticated'] is False


def test_login_failure(client):
    resp = client.post('/api/auth/login', json={'username': 'antineutrino', 'password': 'wrong'})
    assert resp.status_code == 401


def test_default_superadmin_stores_hash():
    ensure_test_account_passwords()
    user = get_user_by_username(
        DEFAULT_SUPERADMIN['username'],
        school_id=DEFAULT_SUPERADMIN['school_id'],
    )
    assert user is not None
    assert is_password_hash(user.password_hash)
    assert user.password_hash != TEST_SUPERADMIN_PASSWORD


def test_login_accepts_stored_hash(client):
    ensure_test_account_passwords()
    resp = client.post('/api/auth/login', json={
        'username': DEFAULT_SUPERADMIN['username'],
        'password': TEST_SUPERADMIN_PASSWORD,
    })
    assert resp.status_code == 200


def test_login_upgrades_legacy_plaintext_password(client):
    client.get('/api/auth/status')
    username = f'legacy-{uuid.uuid4().hex[:8]}'
    password = 'legacy-pass'
    user = User(
        id=str(uuid.uuid4()),
        school_id=DEFAULT_SCHOOL_ID,
        username=username,
        password_hash=password,
        display_name='Legacy User',
        role='user',
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert resp.status_code == 200

    db_session.expire_all()
    upgraded = db_session.query(User).filter_by(username=username).first()
    assert is_password_hash(upgraded.password_hash)
    assert upgraded.password_hash != password
    assert verify_password(upgraded.password_hash, password)


def test_school_code_signup_request_and_approval_store_hashes(client, login):
    username = f'request-{uuid.uuid4().hex[:8]}'
    password = 'request-pass'

    signup = client.post('/api/auth/signup', json={
        'username': username,
        'password': password,
        'name': 'Request User',
        'school_code': DEFAULT_SCHOOL_SLUG,
    })
    assert signup.status_code == 201

    account_request = (
        db_session.query(AccountCreationRequest)
        .filter_by(username=username, status='pending')
        .first()
    )
    assert account_request is not None
    assert is_password_hash(account_request.password_hash)
    assert verify_password(account_request.password_hash, password)

    login()
    approved = client.post(f'/api/superadmin/account-requests/{account_request.id}/approve')
    assert approved.status_code == 200

    created = db_session.query(User).filter_by(username=username).first()
    assert created is not None
    assert is_password_hash(created.password_hash)
    assert verify_password(created.password_hash, password)


def test_guest_login_requires_slug(client):
    resp = client.post('/api/auth/guest')
    assert resp.status_code == 400


def test_guest_login_with_slug(client):
    resp = client.post('/api/auth/guest', json={'school_slug': DEFAULT_SCHOOL_SLUG})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['user']['school']['slug'] == DEFAULT_SCHOOL_SLUG
    assert payload['user']['school_id'] == DEFAULT_SCHOOL_ID

    status = client.get('/api/auth/status')
    data = status.get_json()
    assert status.status_code == 200
    assert data['authenticated'] is True
    assert data['user']['role'] == 'guest'
    assert data['user']['school_id'] == DEFAULT_SCHOOL_ID
    assert data['user']['school']['slug'] == DEFAULT_SCHOOL_SLUG


def test_guest_login_invalid_slug(client):
    resp = client.post('/api/auth/guest', json={'school_slug': 'missing-school'})
    assert resp.status_code == 404
