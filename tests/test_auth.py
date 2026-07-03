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
from src.routes.golden_plate_recorder_db.users import (
    DEFAULT_SUPERADMIN,
    LEGACY_DEFAULT_SUPERADMINS,
    ensure_default_superadmin,
    get_user_by_username,
    update_user_credentials,
)

DEFAULT_DEVELOPMENT_PASSWORD = 'begreendogood'
LEGACY_DEVELOPMENT_PASSWORD = 'b-decay'


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
    resp = client.post('/api/auth/login', json={'username': DEFAULT_SUPERADMIN['username'], 'password': 'wrong'})
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
    client.get('/api/auth/status')
    ensure_test_account_passwords()
    resp = client.post('/api/auth/login', json={
        'username': DEFAULT_SUPERADMIN['username'],
        'password': TEST_SUPERADMIN_PASSWORD,
    })
    assert resp.status_code == 200


def test_default_development_login_works_in_development(client, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    client.get('/api/auth/status')
    ensure_default_superadmin()

    resp = client.post('/api/auth/login', json={
        'username': DEFAULT_SUPERADMIN['username'],
        'password': DEFAULT_DEVELOPMENT_PASSWORD,
    })
    assert resp.status_code == 200


def test_default_development_login_is_disabled_in_production(client, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    client.get('/api/auth/status')
    user = ensure_default_superadmin()
    update_user_credentials(
        user,
        password=DEFAULT_SUPERADMIN['password_hash'],
        password_is_hash=True,
    )

    monkeypatch.setenv('APP_ENV', 'production')
    resp = client.post('/api/auth/login', json={
        'username': DEFAULT_SUPERADMIN['username'],
        'password': DEFAULT_DEVELOPMENT_PASSWORD,
    })
    assert resp.status_code == 401
    assert resp.get_json()['error'] == 'Default development admin credentials are disabled'


def test_legacy_default_development_login_is_disabled_in_production(client, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    client.get('/api/auth/status')
    legacy_default = LEGACY_DEFAULT_SUPERADMINS[0]
    legacy_user = User(
        id=str(uuid.uuid4()),
        school_id=DEFAULT_SUPERADMIN['school_id'],
        username=legacy_default['username'],
        password_hash=legacy_default['password_hash'],
        display_name='Legacy Default Admin',
        role='superadmin',
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )
    db_session.add(legacy_user)
    db_session.commit()

    monkeypatch.setenv('APP_ENV', 'production')
    resp = client.post('/api/auth/login', json={
        'username': legacy_default['username'],
        'password': LEGACY_DEVELOPMENT_PASSWORD,
    })
    assert resp.status_code == 401
    assert resp.get_json()['error'] == 'Default development admin credentials are disabled'


def test_legacy_default_superadmin_migrates_to_current_default(client, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    client.get('/api/auth/status')

    current = get_user_by_username(
        DEFAULT_SUPERADMIN['username'],
        school_id=DEFAULT_SUPERADMIN['school_id'],
    )
    if current:
        db_session.delete(current)
        db_session.commit()

    legacy_default = LEGACY_DEFAULT_SUPERADMINS[0]
    legacy_user = User(
        id=str(uuid.uuid4()),
        school_id=DEFAULT_SUPERADMIN['school_id'],
        username=legacy_default['username'],
        password_hash=legacy_default['password_hash'],
        display_name='Legacy Default Admin',
        role='superadmin',
        status='active',
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )
    db_session.add(legacy_user)
    db_session.commit()

    migrated = ensure_default_superadmin()

    assert migrated.username == DEFAULT_SUPERADMIN['username']
    assert get_user_by_username(legacy_default['username'], school_id=DEFAULT_SUPERADMIN['school_id']) is None
    assert verify_password(migrated.password_hash, DEFAULT_DEVELOPMENT_PASSWORD)


def test_app_environment_endpoint_reflects_environment(client, monkeypatch):
    client.get('/api/auth/status')
    monkeypatch.setenv('APP_ENV', 'production')
    resp = client.get('/api/app/environment')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['environment'] == 'production'
    assert data['is_production'] is True
    assert data['is_development'] is False
    assert data['default_admin_credentials_enabled'] is False


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
