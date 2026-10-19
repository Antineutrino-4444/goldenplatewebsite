import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from src.routes.golden_plate_recorder_db import auth_routes, db as database
from src.routes.golden_plate_recorder_db.db import (
    AccountCreationRequest, School, SchoolRegistrationRequest, User, db_session,
)
from src.routes.golden_plate_recorder_db.users import create_user_record, create_invite_code_record


@pytest.fixture
def contact_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex[:10]
    school = School(id=f'contact-{suffix}', name=f'Contact Academy {suffix}', slug=f'contact-{suffix}')
    db_session.add(school)
    db_session.commit()
    admin = create_user_record(f'contact-admin-{suffix}', 'contact-password', 'School Superadmin',
                               role='superadmin', school_id=school.id)
    return school, admin


def sign_in(client, account):
    return client.post('/api/auth/login', json={
        'username': account.username, 'password': 'contact-password',
    })


def signup_payload(school, **kwargs):
    return dict(username=f'contact-signup-{uuid.uuid4().hex[:8]}', password='signup-secret-password',
                name='Applicant <script>unsafe</script>', email='Applicant@Example.com', school_code=school.slug, **kwargs)


def test_superadmin_reminder_and_contact_save_are_school_scoped(client, contact_school):
    school, admin = contact_school
    response = sign_in(client, admin)
    assert response.status_code == 200
    assert response.get_json()['user']['school_contact_email_required'] is True
    assert client.get('/api/auth/status').get_json()['user']['school_contact_email_required'] is True
    other = School(id=str(uuid.uuid4()), name='Other Academy', slug=uuid.uuid4().hex,
                   contact_email='other@example.com')
    db_session.add(other)
    db_session.commit()
    response = client.put('/api/school/contact-email', json={
        'email': ' SCHOOL@Example.COM ', 'school_id': other.id,
    })
    assert response.status_code == 200
    assert response.get_json()['contact_email'] == 'school@example.com'
    db_session.expire_all()
    assert db_session.get(School, school.id).contact_email == 'school@example.com'
    assert db_session.get(School, other.id).contact_email == 'other@example.com'
    status = client.get('/api/auth/status').get_json()['user']
    assert status['school_contact_email_required'] is False
    assert status['school_contact_email'] == 'school@example.com'
    assert 'contact_email' not in status['school']
    client.post('/api/auth/logout')
    assert sign_in(client, admin).get_json()['user']['school_contact_email_required'] is False
    assert client.put('/api/school/contact-email', json={'email': 'replacement@example.com'}).status_code == 200
    assert client.get('/api/auth/status').get_json()['user']['school_contact_email'] == 'replacement@example.com'


@pytest.mark.parametrize('role', ['user', 'admin', 'inter_school'])
def test_other_roles_do_not_see_reminder_or_manage_contacts(client, contact_school, role):
    school, _ = contact_school
    account = create_user_record(f'contact-{role}-{uuid.uuid4().hex[:8]}', 'contact-password', 'Other Role',
                                 role=role, school_id=school.id)
    payload = sign_in(client, account).get_json()['user']
    assert 'school_contact_email_required' not in payload
    assert 'school_contact_email' not in payload
    assert 'school_contact_email' not in client.get('/api/auth/status').get_json()['user']
    assert client.put('/api/school/contact-email', json={'email': 'denied@example.com'}).status_code == 403
    assert db_session.get(School, school.id).contact_email is None


@pytest.mark.parametrize('guest', [True, False])
def test_contact_update_requires_superadmin_login(client, contact_school, guest):
    school, _ = contact_school
    if guest:
        response = client.post('/api/auth/guest', json={'school_slug': school.slug})
        assert response.status_code == 200
        assert 'school_contact_email_required' not in response.get_json()['user']
    assert client.put('/api/school/contact-email', json={'email': 'denied@example.com'}).status_code == 401


@pytest.mark.parametrize('email', ['', 'invalid', 'a@example.com,b@example.com', 'a@example.com\nb@example.com', None, [], 'a' * 321 + '@example.com'])
def test_contact_update_rejects_invalid_email(client, contact_school, email):
    school, admin = contact_school
    sign_in(client, admin)
    assert client.put('/api/school/contact-email', json={'email': email}).status_code == 400
    assert db_session.get(School, school.id).contact_email is None


def test_pending_signup_notifies_only_school_contact_and_configured_recipients(client, contact_school, monkeypatch, email_outbox, signup_email_code):
    school, _ = contact_school
    school.contact_email = 'school@example.com'
    db_session.commit()
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'updates@example.com,SCHOOL@example.com')
    payload = signup_payload(school)
    school_name = school.name
    payload['verification_code'] = signup_email_code(payload['email'], school_id=school.id)
    response = client.post('/api/auth/signup', json=payload)
    assert response.status_code == 201
    assert len(email_outbox) == 2
    assert [email['to'] for email in email_outbox] == [
        [{'email': 'updates@example.com'}], [{'email': 'SCHOOL@example.com'}],
    ]
    for email in email_outbox:
        assert 'New account signup request' in email['subject']
        assert school_name in email['htmlContent']
        assert 'Account requests' in email['htmlContent']
        assert '&lt;script&gt;' in email['htmlContent']
        assert '<script>' not in email['htmlContent']
        assert payload['password'] not in email['htmlContent']
        assert payload['verification_code'] not in email['htmlContent']
        saved = db_session.query(AccountCreationRequest).filter_by(username=payload['username']).one()
        assert saved.password_hash not in email['htmlContent']
    assert client.post('/api/auth/signup', json=payload).status_code == 409
    assert len(email_outbox) == 2


def test_invite_signup_notifies_school_and_cannot_be_repeated(client, contact_school, monkeypatch, email_outbox, signup_email_code):
    school, admin = contact_school
    school.contact_email = 'school@example.com'
    db_session.commit()
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    invite = create_invite_code_record(admin, admin)
    payload = signup_payload(school, invite_code=invite.code)
    payload['verification_code'] = signup_email_code(payload['email'], school_id=school.id)
    response = client.post('/api/auth/signup', json=payload)
    assert response.status_code == 201
    assert len(email_outbox) == 1
    email = email_outbox[0]
    assert email['to'] == [{'email': 'school@example.com'}]
    assert 'invite' in email['subject']
    assert 'already active' in email['htmlContent']
    assert 'no approval is needed' in email['htmlContent']
    assert payload['password'] not in email['htmlContent']
    assert payload['invite_code'] not in email['htmlContent']
    assert payload['verification_code'] not in email['htmlContent']
    user = db_session.query(User).filter_by(username=payload['username']).one()
    assert user.status == 'active'
    assert user.email == 'applicant@example.com'
    assert client.post('/api/auth/signup', json=payload).status_code == 403
    assert len(email_outbox) == 1


@pytest.mark.parametrize('invited', [False, True])
@pytest.mark.parametrize('email', ['missing', None, '', '   ', 'invalid', 'missing@domain',
                                  'a@example.com,b@example.com', 'a@example.com\nb@example.com',
                                  [], 123, 'a' * 321 + '@example.com'])
def test_account_signup_requires_valid_email_before_saving(client, contact_school, email_outbox, invited, email):
    school, admin = contact_school
    payload = signup_payload(school)
    if invited:
        invite = create_invite_code_record(admin, admin)
        payload.pop('school_code')
        payload['invite_code'] = invite.code
    if email == 'missing':
        payload.pop('email')
    else:
        payload['email'] = email
    response = client.post('/api/auth/signup', json=payload)
    assert response.status_code == 400
    assert 'email' in response.get_json()['error'].lower()
    assert db_session.query(User).filter_by(username=payload['username']).first() is None
    assert db_session.query(AccountCreationRequest).filter_by(username=payload['username']).first() is None
    if invited:
        assert database.db_session.query(database.UserInviteCode).filter_by(code=payload['invite_code']).one().status == 'unused'
    assert email_outbox == []


@pytest.mark.parametrize('invited', [True, False])
def test_notification_failure_preserves_saved_signup(client, contact_school, monkeypatch, invited, signup_email_code):
    school, admin = contact_school
    monkeypatch.setattr(auth_routes, 'notify_school_signup', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('Mail unavailable')))
    payload = signup_payload(school)
    if invited:
        payload['invite_code'] = create_invite_code_record(admin, admin).code
    payload['verification_code'] = signup_email_code(payload['email'], school_id=school.id)
    assert client.post('/api/auth/signup', json=payload).status_code == 201
    model = User if invited else AccountCreationRequest
    assert db_session.query(model).filter_by(username=payload['username']).one() is not None


def test_no_configured_recipients_and_no_contact_skip_signup_alert(client, contact_school, monkeypatch, email_outbox, signup_email_code):
    school, _ = contact_school
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    payload = signup_payload(school)
    payload['verification_code'] = signup_email_code(payload['email'], school_id=school.id)
    assert client.post('/api/auth/signup', json=payload).status_code == 201
    assert email_outbox == []


def test_backfill_recovers_approved_signup_email_without_overwriting_contact(client, contact_school):
    school, admin = contact_school
    pending_school = School(id=str(uuid.uuid4()), name='Pending Backfill', slug=uuid.uuid4().hex)
    db_session.add(pending_school)
    db_session.add_all([
        SchoolRegistrationRequest(email='RECORDED@example.com', school_name=school.name,
                                  school_slug=school.slug, admin_username=admin.username,
                                  admin_password_hash=admin.password_hash, admin_display_name=admin.display_name,
                                  status='approved'),
        SchoolRegistrationRequest(email='pending@example.com', school_name=pending_school.name,
                                  school_slug=pending_school.slug, admin_username=uuid.uuid4().hex,
                                  admin_password_hash='unused', admin_display_name='Pending', status='pending'),
    ])
    db_session.commit()
    database._backfill_school_contact_emails()
    db_session.expire_all()
    assert db_session.get(School, school.id).contact_email == 'recorded@example.com'
    assert db_session.get(School, pending_school.id).contact_email is None
    school.contact_email = 'updated@example.com'
    db_session.commit()
    database._backfill_school_contact_emails()
    db_session.expire_all()
    assert db_session.get(School, school.id).contact_email == 'updated@example.com'


def test_existing_database_upgrade_adds_and_backfills_contact_once(monkeypatch):
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(
            id='historical-school', name='Historical Academy', slug='historical-academy',
        ))
        connection.execute(SchoolRegistrationRequest.__table__.insert().values(
            id='historical-request', email='historical@example.com',
            school_name='Historical Academy', school_slug='historical-academy',
            admin_username='old-admin', admin_password_hash='unused',
            admin_display_name='Old Admin', status='approved',
        ))
        connection.execute(text('ALTER TABLE schools DROP COLUMN contact_email'))
        connection.execute(User.__table__.insert().values(
            id='historical-user', school_id='historical-school', username='historical-user',
            password_hash='unchanged', display_name='Historical User', role='user',
        ))
        connection.execute(AccountCreationRequest.__table__.insert().values(
            id='historical-account-request', school_id='historical-school', username='historical-applicant',
            password_hash='unchanged', display_name='Historical Applicant',
        ))
        for table_name in ('users', 'account_creation_requests'):
            connection.execute(text(f'ALTER TABLE {table_name} DROP COLUMN email'))
    monkeypatch.setattr(database, 'engine', engine)
    database._bootstrap_database()
    for table_name in ('users', 'account_creation_requests'):
        assert 'email' in {column['name'] for column in inspect(engine).get_columns(table_name)}
    with engine.begin() as connection:
        assert connection.execute(text("SELECT email FROM users WHERE id = 'historical-user'")).scalar_one() is None
        assert connection.execute(text("SELECT email FROM account_creation_requests WHERE id = 'historical-account-request'")).scalar_one() is None
        connection.execute(text("UPDATE users SET email = 'saved@example.com' WHERE id = 'historical-user'"))
    assert 'contact_email' in {column['name'] for column in inspect(engine).get_columns('schools')}
    with engine.begin() as connection:
        email = connection.execute(text("SELECT contact_email FROM schools WHERE id = 'historical-school'")).scalar_one()
        assert email == 'historical@example.com'
        connection.execute(text("UPDATE schools SET contact_email = NULL WHERE id = 'historical-school'"))
    database._bootstrap_database()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT email FROM users WHERE id = 'historical-user'")).scalar_one() == 'saved@example.com'
        assert connection.execute(text("SELECT contact_email FROM schools WHERE id = 'historical-school'")).scalar_one() is None
    engine.dispose()


def test_backfill_leaves_ambiguous_historical_school_for_superadmin_to_resolve(client):
    name = f'Ambiguous Academy {uuid.uuid4().hex[:8]}'
    schools = [School(id=str(uuid.uuid4()), name=name, slug=uuid.uuid4().hex) for _ in range(2)]
    db_session.add_all(schools)
    db_session.add(SchoolRegistrationRequest(
        email='ambiguous@example.com', school_name=name,
        admin_username=uuid.uuid4().hex, admin_password_hash='unused',
        admin_display_name='Unknown Administrator', status='approved',
    ))
    db_session.commit()
    database._backfill_school_contact_emails()
    db_session.expire_all()
    assert all(db_session.get(School, school.id).contact_email is None for school in schools)
