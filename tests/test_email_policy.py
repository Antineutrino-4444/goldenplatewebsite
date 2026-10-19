import json
import uuid
from datetime import timedelta

import pytest

from conftest import TEST_SUPERADMIN_PASSWORD, TEST_SUPERADMIN_PASSWORD_HASH
from src.main import app
from src.routes.golden_plate_recorder_db import account_email_routes, db as database
from src.routes.golden_plate_recorder_db.db import AccountCreationRequest, EmailVerification, School, User, _now_utc, db_session
from src.routes.golden_plate_recorder_db.email_policy import email_allowed, validate_policy
from src.routes.golden_plate_recorder_db.users import create_user_record, create_invite_code_record

POLICY_URL = '/api/school/email-policy'
SEND_SIGNUP = '/api/auth/signup/send-verification-code'
SEND_OWN = '/api/auth/account-email/send-verification-code'
SAVE_OWN = '/api/auth/account-email'
POLICY = {'enabled': True, 'allowed_domains': ['school.edu'],
          'exceptions': ['coach@example.com', 'partner.edu']}


@pytest.fixture
def email_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex[:10]
    school = School(id=f'email-{suffix}', name='Email Rules School', slug=f'email-{suffix}', contact_email='school-contact@example.com')
    db_session.add(school)
    db_session.commit()
    result = {'school_id': school.id, 'slug': school.slug}
    for role in ('user', 'admin', 'superadmin'):
        user = create_user_record(f'email-{role}-{suffix}', TEST_SUPERADMIN_PASSWORD_HASH, role.title(),
                                  role=role, school_id=school.id, password_is_hash=True)
        result[role] = {'id': user.id, 'username': user.username}
    return result


def sign_in(client, school, role):
    response = client.post('/api/auth/login', json={
        'username': school[role]['username'], 'password': TEST_SUPERADMIN_PASSWORD,
    })
    assert response.status_code == 200
    return response.get_json()['user']


def set_policy(school, policy=POLICY):
    db_session.get(School, school['school_id']).signup_email_policy = json.dumps(policy)
    db_session.commit()


def payload(school, email='new@school.edu'):
    return {'email': email, 'school_code': school['slug'], 'username': f'new-{uuid.uuid4().hex[:10]}',
            'password': 'signup-password', 'name': 'New Member'}


def challenge(client, endpoint, data):
    response = client.post(endpoint, json=data)
    assert response.status_code == 200, response.get_json()
    key = 'signup_email_challenge' if endpoint == SEND_SIGNUP else 'account_email_challenge'
    with client.session_transaction() as session:
        challenge_id = session[key]
    return challenge_id, db_session.get(EmailVerification, challenge_id).code


@pytest.mark.parametrize('email,allowed', [
    ('member@school.edu', True), ('MEMBER@SCHOOL.EDU', True), ('coach@example.com', True),
    ('anyone@partner.edu', True), ('someone@example.com', False),
    ('member@students.school.edu', False), ('member@evilschool.edu', False),
    ('member@school.edu.evil.com', False), ('coach+other@example.com', False),
])
def test_exact_domains_and_exceptions(email_school, email, allowed):
    set_policy(email_school)
    assert email_allowed(db_session.get(School, email_school['school_id']), email) is allowed


@pytest.mark.parametrize('role', ['admin', 'superadmin'])
def test_admins_manage_only_own_school_rules(client, email_school, role):
    other = School(id=str(uuid.uuid4()), name='Other School', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.commit()
    other_id = other.id
    sign_in(client, email_school, role)
    response = client.put(POLICY_URL, json=dict(POLICY, school_id=other_id,
        allowed_domains=['@SCHOOL.EDU', 'school.edu'], exceptions=['COACH@Example.com', '@PARTNER.EDU']))
    assert response.status_code == 200
    assert response.get_json() == POLICY
    assert client.get(POLICY_URL).get_json() == POLICY
    assert db_session.get(School, other_id).signup_email_policy is None


@pytest.mark.parametrize('bad', [
    {}, dict(POLICY, enabled='true'), dict(POLICY, allowed_domains='school.edu'),
    dict(POLICY, allowed_domains=['https://school.edu']), dict(POLICY, allowed_domains=['*.school.edu']),
    dict(POLICY, allowed_domains=[], exceptions=[]), dict(POLICY, exceptions=['bad@@school.edu']),
])
def test_invalid_policy_does_not_overwrite_settings(client, email_school, bad):
    sign_in(client, email_school, 'superadmin')
    set_policy(email_school)
    assert client.put(POLICY_URL, json=bad).status_code == 400
    assert client.get(POLICY_URL).get_json() == POLICY


def test_members_and_guests_cannot_manage_rules(client, email_school):
    assert client.get(POLICY_URL).status_code == 401
    sign_in(client, email_school, 'user')
    assert client.put(POLICY_URL, json=POLICY).status_code == 403
    client.post('/api/auth/logout')
    client.post('/api/auth/guest', json={'school_slug': email_school['slug']})
    assert client.get(POLICY_URL).status_code == 401


@pytest.mark.parametrize('invited', [False, True])
def test_disallowed_signup_is_rejected_before_email_delivery(client, email_school, email_outbox, invited):
    set_policy(email_school)
    data = payload(email_school, 'outsider@example.com')
    if invited:
        admin = db_session.get(User, email_school['superadmin']['id'])
        data['invite_code'] = create_invite_code_record(admin, admin).code
        data.pop('school_code')
    response = client.post(SEND_SIGNUP, json=data)
    assert response.status_code == 400
    assert response.get_json()['code'] == 'SCHOOL_EMAIL_NOT_ALLOWED'
    assert email_outbox == []
    assert db_session.query(EmailVerification).filter_by(email=data['email']).first() is None


@pytest.mark.parametrize('email', ['new@school.edu', 'coach@example.com', 'new@partner.edu'])
def test_allowed_signup_and_exceptions_still_require_code(client, email_school, email, email_outbox):
    set_policy(email_school)
    data = payload(email_school, email)
    assert client.post('/api/auth/signup', json=data).status_code == 400
    _, code = challenge(client, SEND_SIGNUP, data)
    data['verification_code'] = code
    assert client.post('/api/auth/signup', json=data).status_code == 201
    saved = db_session.query(AccountCreationRequest).filter_by(username=data['username']).one()
    assert saved.email_verified_at is not None


def test_signup_rechecks_policy_after_code_was_sent(client, email_school):
    data = payload(email_school, 'outsider@example.com')
    _, code = challenge(client, SEND_SIGNUP, data)
    set_policy(email_school)
    data['verification_code'] = code
    response = client.post('/api/auth/signup', json=data)
    assert response.status_code == 400
    assert response.get_json()['code'] == 'SCHOOL_EMAIL_NOT_ALLOWED'


def test_code_is_bound_to_school(client, email_school):
    data = payload(email_school)
    _, code = challenge(client, SEND_SIGNUP, data)
    other = School(id=str(uuid.uuid4()), name='Other School', slug=uuid.uuid4().hex)
    db_session.add(other)
    db_session.commit()
    data.update(school_code=other.slug, verification_code=code)
    assert client.post('/api/auth/signup', json=data).status_code == 400


def test_normalization_matches_international_domains_consistently():
    policy = validate_policy({'enabled': True, 'allowed_domains': ['BÜCHER.edu'],
                              'exceptions': ['COACH@BÜCHER.edu']})
    assert policy['allowed_domains'] == ['xn--bcher-kva.edu']
    assert policy['exceptions'] == ['coach@xn--bcher-kva.edu']
    school = School(signup_email_policy=json.dumps(policy))
    assert email_allowed(school, 'Member@bücher.edu')
    assert not email_allowed(school, 'Member@bücher.edu.evil.com')


def test_school_required_before_sending_signup_code(client, email_outbox):
    assert client.post(SEND_SIGNUP, json={'email': 'member@school.edu'}).status_code == 400
    assert email_outbox == []


def test_existing_member_must_verify_or_logout(client, email_school, email_outbox):
    # Existing users remain unrestricted until the school enables rules.
    assert sign_in(client, email_school, 'user')['email_required'] is False
    assert client.get('/api/session/list').status_code == 200
    set_policy(email_school)
    status = client.get('/api/auth/status').get_json()['user']
    assert status['email_required'] is True
    assert client.get('/api/session/list').get_json()['code'] == 'ACCOUNT_EMAIL_REQUIRED'
    assert client.post('/api/session/create', json={'name': 'Blocked'}).status_code == 403
    assert client.post(SEND_OWN, json={'email': 'member@outside.com'}).status_code == 400
    assert email_outbox == []
    _, code = challenge(client, SEND_OWN, {'email': ' MEMBER@SCHOOL.EDU '})
    assert client.put(SAVE_OWN, json={'email': 'member@school.edu', 'verification_code': 'wrong'}).status_code == 400
    assert client.get('/api/session/list').status_code == 403
    response = client.put(SAVE_OWN, json={'email': 'member@school.edu', 'verification_code': code})
    assert response.status_code == 200
    assert response.get_json()['user']['email_required'] is False
    assert response.get_json()['user']['email_verified'] is True
    assert client.get('/api/session/list').status_code == 200
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/status').get_json()['authenticated'] is False


def test_member_can_decline_and_logout_without_email(client, email_school):
    set_policy(email_school)
    assert sign_in(client, email_school, 'user')['email_required'] is True
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/status').get_json()['authenticated'] is False
    assert db_session.get(User, email_school['user']['id']).email is None


def test_existing_verified_member_and_policy_changes(client, email_school):
    user = db_session.get(User, email_school['user']['id'])
    user.email = 'member@school.edu'
    user.email_verified_at = _now_utc()
    db_session.commit()
    set_policy(email_school)
    assert sign_in(client, email_school, 'user')['email_required'] is False
    set_policy(email_school, dict(POLICY, allowed_domains=['different.edu']))
    assert client.get('/api/auth/status').get_json()['user']['email_required'] is True
    set_policy(email_school, dict(POLICY, enabled=False))
    assert client.get('/api/auth/status').get_json()['user']['email_required'] is False


@pytest.mark.parametrize('role', ['admin', 'superadmin'])
def test_staff_exempt_and_can_verify_own_email(client, email_school, role):
    set_policy(email_school)
    assert sign_in(client, email_school, role)['email_required'] is False
    assert client.get('/api/session/list').status_code == 200
    _, code = challenge(client, SEND_OWN, {'email': 'staff@personal.com'})
    response = client.put(SAVE_OWN, json={'email': 'staff@personal.com', 'verification_code': code,
                                        'user_id': email_school['user']['id']})
    assert response.status_code == 200
    assert response.get_json()['user']['email'] == 'staff@personal.com'
    assert db_session.get(User, email_school['user']['id']).email is None
    assert db_session.get(School, email_school['school_id']).contact_email == 'school-contact@example.com'


def test_superadmin_requires_fresh_admin_verification_at_next_login(client, email_school):
    admin = db_session.get(User, email_school['admin']['id'])
    admin.email = 'old@personal.com'
    admin.email_verified_at = _now_utc() - timedelta(days=1)
    db_session.commit()
    sign_in(client, email_school, 'admin')
    with app.test_client() as supervisor:
        sign_in(supervisor, email_school, 'superadmin')
        assert supervisor.post(f"/api/superadmin/users/{email_school['admin']['id']}/require-email").status_code == 200
    # An already-open admin session is exempt until another login.
    assert client.get('/api/auth/status').get_json()['user']['email_required'] is False
    assert client.get('/api/session/list').status_code == 200
    client.post('/api/auth/logout')
    assert sign_in(client, email_school, 'admin')['email_required'] is True
    assert client.get('/api/admin/users').status_code == 403
    _, code = challenge(client, SEND_OWN, {'email': 'new@personal.com'})
    response = client.put(SAVE_OWN, json={'email': 'new@personal.com', 'verification_code': code})
    assert response.status_code == 200
    assert response.get_json()['user']['email_required'] is False
    assert client.get('/api/admin/users').status_code == 200


def test_only_superadmin_can_require_same_school_admin(client, email_school):
    target = f"/api/superadmin/users/{email_school['admin']['id']}/require-email"
    sign_in(client, email_school, 'admin')
    assert client.post(target).status_code == 403
    client.post('/api/auth/logout')
    sign_in(client, email_school, 'superadmin')
    assert client.post(f"/api/superadmin/users/{email_school['superadmin']['id']}/require-email").status_code == 403
    assert client.post(f"/api/superadmin/users/{email_school['user']['id']}/require-email").status_code == 403
    other_school = School(id=str(uuid.uuid4()), name='Other', slug=uuid.uuid4().hex)
    db_session.add(other_school)
    db_session.commit()
    other = create_user_record(uuid.uuid4().hex, TEST_SUPERADMIN_PASSWORD_HASH, 'Other Admin', role='admin',
                                school_id=other_school.id, password_is_hash=True)
    assert client.post(f'/api/superadmin/users/{other.id}/require-email').status_code == 404


def test_account_verification_rechecks_rules_and_preserves_old_email(client, email_school):
    sign_in(client, email_school, 'user')
    _, code = challenge(client, SEND_OWN, {'email': 'outside@example.com'})
    set_policy(email_school)
    assert client.put(SAVE_OWN, json={'email': 'outside@example.com', 'verification_code': code}).status_code == 400
    assert db_session.get(User, email_school['user']['id']).email is None


def test_personal_delivery_failure_preserves_account(client, email_school, monkeypatch):
    sign_in(client, email_school, 'user')
    monkeypatch.setattr(account_email_routes, 'send_verification_email', lambda *args, **kwargs: {'success': False})
    assert client.post(SEND_OWN, json={'email': 'member@school.edu'}).status_code == 503
    assert db_session.get(User, email_school['user']['id']).email is None
    with client.session_transaction() as session:
        assert 'account_email_challenge' not in session


def test_personal_verification_cannot_be_used_by_another_account(client, email_school):
    sign_in(client, email_school, 'user')
    _, code = challenge(client, SEND_OWN, {'email': 'member@school.edu'})
    # Signing in as another account without logout retains the browser session,
    # but must not transfer ownership of the email challenge.
    sign_in(client, email_school, 'admin')
    assert client.put(SAVE_OWN, json={'email': 'member@school.edu', 'verification_code': code}).status_code == 400
    assert db_session.get(User, email_school['admin']['id']).email is None


def test_policy_upgrade_preserves_existing_data_and_defaults_disabled(monkeypatch):
    from sqlalchemy import create_engine, text
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(id='existing', name='Existing', slug='existing'))
        connection.execute(User.__table__.insert().values(id='existing-user', school_id='existing', username='existing',
                                                          password_hash='unchanged', display_name='Existing', role='user', email='old@example.com'))
        for table, columns in [('schools', ['signup_email_policy']), ('users', ['email_verified_at', 'admin_email_required_at']),
                               ('account_creation_requests', ['email_verified_at']), ('email_verifications', ['school_id', 'user_id'])]:
            for column in columns:
                connection.execute(text(f'ALTER TABLE {table} DROP COLUMN {column}'))
    monkeypatch.setattr(database, 'engine', engine)
    database._bootstrap_database()
    database._bootstrap_database()
    with engine.connect() as connection:
        row = connection.execute(text("SELECT email, email_verified_at FROM users WHERE id='existing-user'")).one()
        assert tuple(row) == ('old@example.com', None)
        assert connection.execute(text("SELECT signup_email_policy FROM schools WHERE id='existing'")).scalar_one() is None
    engine.dispose()
