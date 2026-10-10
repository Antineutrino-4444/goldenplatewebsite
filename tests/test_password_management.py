import uuid

import pytest

from conftest import TEST_INTERSCHOOL_PASSWORD, TEST_SUPERADMIN_PASSWORD, ensure_test_account_passwords
from src.main import app
from src.routes.golden_plate_recorder_db import password_routes
from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, School, db_session
from src.routes.golden_plate_recorder_db.passwords import is_password_hash, verify_password
from src.routes.golden_plate_recorder_db.users import (
    create_user_record, ensure_default_superadmin, ensure_interschool_user,
    get_user_by_id, get_user_by_username,
)

OLD_PASSWORD = 'original-password'
NEW_PASSWORD = 'updated-password'


def make_user(role='user', school_id=DEFAULT_SCHOOL_ID):
    return create_user_record(
        f'pwd-{uuid.uuid4().hex[:10]}', OLD_PASSWORD, 'Password Test',
        role=role, school_id=school_id,
    )


def sign_in(client, user, password=OLD_PASSWORD):
    return client.post('/api/auth/login', json={'username': user.username, 'password': password})


@pytest.mark.parametrize('role', ['user', 'admin', 'superadmin', 'inter_school'])
def test_all_roles_change_only_their_own_password(client, role, email_outbox):
    client.get('/api/auth/status')
    actor = make_user(role)
    other = make_user()
    actor_id, other_id = actor.id, other.id
    other_session = app.test_client()
    assert sign_in(client, actor).status_code == 200
    assert sign_in(other_session, actor).status_code == 200
    response = client.post('/api/auth/change-password', json={
        'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD,
        'user_id': other_id,  # Cannot redirect the self-service endpoint.
    })
    assert response.status_code == 200
    assert 'password_hash' not in response.get_json()
    changed = get_user_by_id(actor_id)
    assert is_password_hash(changed.password_hash)
    assert verify_password(changed.password_hash, NEW_PASSWORD)
    assert not verify_password(changed.password_hash, OLD_PASSWORD)
    assert verify_password(get_user_by_id(other_id).password_hash, OLD_PASSWORD)
    assert client.get('/api/auth/status').get_json()['authenticated'] is True
    assert other_session.get('/api/auth/status').get_json()['authenticated'] is False
    assert other_session.get('/api/admin/users').status_code == 403
    client.post('/api/auth/logout')
    assert sign_in(client, changed).status_code == 401
    assert sign_in(client, changed, NEW_PASSWORD).status_code == 200
    assert email_outbox == []  # Account passwords never enter notification emails.


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_non_reset_roles_cannot_list_or_reset_accounts(client, role):
    client.get('/api/auth/status')
    actor, other = make_user(role), make_user()
    other_id = other.id
    sign_in(client, actor)
    assert client.get('/api/auth/password-accounts').status_code == 403
    assert client.post('/api/auth/reset-password', json={
        'user_id': other_id, 'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD,
    }).status_code == 403
    assert verify_password(get_user_by_id(other_id).password_hash, OLD_PASSWORD)


@pytest.mark.parametrize('guest', [False, True])
def test_password_routes_require_real_login(client, guest):
    if guest:
        assert client.post('/api/auth/guest', json={'school_slug': 'SAC'}).status_code == 200
    assert client.get('/api/auth/password-accounts').status_code == 401
    for endpoint in ['change-password', 'reset-password']:
        assert client.post(f'/api/auth/{endpoint}', json={
            'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD,
        }).status_code == 401


@pytest.fixture
def reset_accounts(client):
    client.get('/api/auth/status')
    ensure_test_account_passwords()
    school = School(id=f'pwd-school-{uuid.uuid4().hex[:8]}', name='Other School', slug='pwd-school', status='active')
    db_session.add(school)
    db_session.commit()
    users = {
        'user': make_user(), 'admin': make_user('admin'),
        'superadmin': make_user('superadmin'),
        'outside': make_user('superadmin', school.id),
        'controller': make_user('inter_school'),
    }
    return {key: {'id': user.id, 'username': user.username} for key, user in users.items()}


@pytest.mark.parametrize('actor_name', ['greenguys', 'inter-school-admin'])
def test_reset_account_list_matches_school_permissions(client, reset_accounts, actor_name):
    password = TEST_SUPERADMIN_PASSWORD if actor_name == 'greenguys' else TEST_INTERSCHOOL_PASSWORD
    assert sign_in(client, get_user_by_username(actor_name), password).status_code == 200
    response = client.get('/api/auth/password-accounts')
    assert response.status_code == 200
    accounts = response.get_json()['users']
    ids = {user['id'] for user in accounts}
    for key in ['user', 'admin']:
        assert reset_accounts[key]['id'] in ids
    for key in ['superadmin', 'outside', 'controller']:
        assert (reset_accounts[key]['id'] in ids) == (actor_name == 'inter-school-admin')
    assert actor_name not in {user['username'] for user in accounts}
    assert all('password' not in user and 'password_hash' not in user for user in accounts)


@pytest.mark.parametrize('actor_name,target_key', [
    ('greenguys', 'user'), ('greenguys', 'admin'),
    ('inter-school-admin', 'outside'), ('inter-school-admin', 'controller'),
])
def test_administrator_reset_revokes_target_sessions_and_preserves_actor(client, reset_accounts, actor_name, target_key):
    actor_password = TEST_SUPERADMIN_PASSWORD if actor_name == 'greenguys' else TEST_INTERSCHOOL_PASSWORD
    target_id = reset_accounts[target_key]['id']
    target = get_user_by_id(target_id)
    target_session = app.test_client()
    assert sign_in(target_session, target).status_code == 200
    assert sign_in(client, get_user_by_username(actor_name), actor_password).status_code == 200
    response = client.post('/api/auth/reset-password', json={
        'user_id': target_id, 'current_password': actor_password, 'new_password': NEW_PASSWORD,
    })
    assert response.status_code == 200
    assert client.get('/api/auth/status').get_json()['authenticated'] is True
    assert target_session.get('/api/auth/status').get_json()['authenticated'] is False
    target = get_user_by_id(target_id)
    assert sign_in(target_session, target).status_code == 401
    assert sign_in(target_session, target, NEW_PASSWORD).status_code == 200


@pytest.mark.parametrize('reset_to_default', [False, True])
@pytest.mark.parametrize('target_key', ['superadmin', 'outside', 'controller', 'self', 'missing'])
def test_superadmin_cannot_reset_outside_scope_or_bypass_own_change(client, reset_accounts, target_key, reset_to_default):
    actor = get_user_by_username('greenguys')
    actor_id = actor.id
    sign_in(client, actor, TEST_SUPERADMIN_PASSWORD)
    target_id = actor_id if target_key == 'self' else 'missing' if target_key == 'missing' else reset_accounts[target_key]['id']
    response = client.post('/api/auth/reset-password', json={
        'user_id': target_id, 'current_password': TEST_SUPERADMIN_PASSWORD, 'new_password': NEW_PASSWORD,
        'reset_to_default': reset_to_default,
    })
    assert response.status_code == 404
    if target_key != 'missing':
        expected = TEST_SUPERADMIN_PASSWORD if target_key == 'self' else OLD_PASSWORD
        assert verify_password(get_user_by_id(target_id).password_hash, expected)


@pytest.mark.parametrize('actor_name,target_key', [
    ('greenguys', 'user'), ('greenguys', 'admin'), ('inter-school-admin', 'outside'),
])
def test_default_reset_uses_fixed_password_and_revokes_sessions(client, reset_accounts, actor_name, target_key, email_outbox):
    target_id = reset_accounts[target_key]['id']
    target_session = app.test_client()
    assert sign_in(target_session, get_user_by_id(target_id)).status_code == 200
    actor_password = TEST_SUPERADMIN_PASSWORD if actor_name == 'greenguys' else TEST_INTERSCHOOL_PASSWORD
    assert sign_in(client, get_user_by_username(actor_name), actor_password).status_code == 200
    response = client.post('/api/auth/reset-password', json={
        'user_id': target_id, 'current_password': actor_password,
        'reset_to_default': True, 'new_password': 'ignored-client-override',
    })
    assert response.status_code == 200
    target = get_user_by_id(target_id)
    assert is_password_hash(target.password_hash)
    assert target.password_hash != '114514'
    assert verify_password(target.password_hash, '114514')
    assert not verify_password(target.password_hash, 'ignored-client-override')
    assert client.get('/api/auth/status').get_json()['authenticated'] is True
    assert target_session.get('/api/auth/status').get_json()['authenticated'] is False
    assert sign_in(target_session, get_user_by_id(target_id)).status_code == 401
    assert sign_in(target_session, get_user_by_id(target_id), '114514').status_code == 200
    assert email_outbox == []


def test_default_reset_without_new_password_requires_actor_password(client):
    client.get('/api/auth/status')
    actor, target = make_user('superadmin'), make_user()
    target_id = target.id
    sign_in(client, actor)
    for password, status in [('wrong', 403), ('', 400)]:
        response = client.post('/api/auth/reset-password', json={
            'user_id': target_id, 'current_password': password, 'reset_to_default': True,
        })
        assert response.status_code == status
        assert verify_password(get_user_by_id(target_id).password_hash, OLD_PASSWORD)
    assert client.post('/api/auth/reset-password', json={
        'user_id': target_id, 'current_password': OLD_PASSWORD, 'reset_to_default': True,
    }).status_code == 200
    assert verify_password(get_user_by_id(target_id).password_hash, '114514')


@pytest.mark.parametrize('role', ['user', 'admin'])
def test_default_reset_cannot_be_used_by_normal_accounts(client, role):
    client.get('/api/auth/status')
    actor, target = make_user(role), make_user()
    target_id = target.id
    sign_in(client, actor)
    assert client.post('/api/auth/reset-password', json={
        'user_id': target_id, 'current_password': OLD_PASSWORD, 'reset_to_default': True,
    }).status_code == 403
    assert verify_password(get_user_by_id(target_id).password_hash, OLD_PASSWORD)


@pytest.mark.parametrize('reset_flag', ['true', 1, None])
def test_invalid_reset_flags_cannot_change_passwords(client, reset_flag):
    client.get('/api/auth/status')
    actor, target = make_user('superadmin'), make_user()
    target_id = target.id
    sign_in(client, actor)
    assert client.post('/api/auth/reset-password', json={
        'user_id': target_id, 'current_password': OLD_PASSWORD,
        'new_password': NEW_PASSWORD, 'reset_to_default': reset_flag,
    }).status_code == 400
    assert verify_password(get_user_by_id(target_id).password_hash, OLD_PASSWORD)


@pytest.mark.parametrize('endpoint', ['change-password', 'reset-password'])
@pytest.mark.parametrize('current,new,status', [
    ('incorrect', NEW_PASSWORD, 403), ('', NEW_PASSWORD, 400),
    (None, NEW_PASSWORD, 400), (123, NEW_PASSWORD, 400),
    (OLD_PASSWORD, 'short', 400), (OLD_PASSWORD, ' ' * 6, 400),
    (OLD_PASSWORD, 'x' * 257, 400), (OLD_PASSWORD, None, 400),
    (OLD_PASSWORD, ['invalid'], 400),
])
def test_invalid_password_input_never_changes_accounts(client, endpoint, current, new, status):
    client.get('/api/auth/status')
    actor, target = make_user('superadmin'), make_user()
    actor_id, target_id = actor.id, target.id
    sign_in(client, actor)
    response = client.post(f'/api/auth/{endpoint}', json={
        'current_password': current, 'new_password': new, 'user_id': target_id,
    })
    assert response.status_code == status
    for user_id in [actor_id, target_id]:
        assert verify_password(get_user_by_id(user_id).password_hash, OLD_PASSWORD)


@pytest.mark.parametrize('new_password', [' password with spaces ', 'pbkdf2:sha256:1000000$salt$value'])
def test_password_whitespace_and_hash_like_text_are_preserved(client, new_password):
    client.get('/api/auth/status')
    actor = make_user()
    actor_id = actor.id
    sign_in(client, actor)
    assert client.post('/api/auth/change-password', json={
        'current_password': OLD_PASSWORD, 'new_password': new_password,
    }).status_code == 200
    changed = get_user_by_id(actor_id)
    assert changed.password_hash != new_password
    assert verify_password(changed.password_hash, new_password)
    client.post('/api/auth/logout')
    assert sign_in(client, changed, new_password).status_code == 200
    if new_password != new_password.strip():
        assert sign_in(client, changed, new_password.strip()).status_code == 401


def test_password_save_failure_preserves_password_and_session(client, monkeypatch):
    client.get('/api/auth/status')
    actor = make_user()
    actor_id = actor.id
    sign_in(client, actor)
    def fail(*args):
        raise RuntimeError('test database unavailable')
    monkeypatch.setattr(password_routes, '_save_password', fail)
    assert client.post('/api/auth/change-password', json={
        'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD,
    }).status_code == 500
    assert verify_password(get_user_by_id(actor_id).password_hash, OLD_PASSWORD)
    assert client.get('/api/auth/status').get_json()['authenticated'] is True


@pytest.mark.parametrize('username,password,ensure_account', [
    ('greenguys', TEST_SUPERADMIN_PASSWORD, ensure_default_superadmin),
    ('inter-school-admin', TEST_INTERSCHOOL_PASSWORD, ensure_interschool_user),
])
def test_seed_account_password_changes_survive_startup(client, username, password, ensure_account, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    client.get('/api/auth/status')
    ensure_test_account_passwords()
    actor = get_user_by_username(username)
    sign_in(client, actor, password)
    assert client.post('/api/auth/change-password', json={
        'current_password': password, 'new_password': NEW_PASSWORD,
    }).status_code == 200
    assert verify_password(ensure_account().password_hash, NEW_PASSWORD)
    assert client.get('/api/auth/status').get_json()['authenticated'] is True


def test_pre_feature_and_disabled_sessions_cannot_change_passwords(client):
    client.get('/api/auth/status')
    actor = make_user()
    actor_id = actor.id
    sign_in(client, actor)
    with client.session_transaction() as session:
        session.pop('password_token')
    assert client.post('/api/auth/change-password', json={
        'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD,
    }).status_code == 401
    assert sign_in(client, get_user_by_id(actor_id)).status_code == 200
    actor = get_user_by_id(actor_id)
    actor.status = 'disabled'
    db_session.commit()
    assert client.post('/api/auth/change-password', json={
        'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD,
    }).status_code == 401
