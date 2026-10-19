import json
import uuid
from datetime import timedelta

import pytest
from flask import Flask
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from conftest import TEST_SUPERADMIN_PASSWORD, TEST_SUPERADMIN_PASSWORD_HASH
from src.main import app
from src.routes.golden_plate_recorder_db.db import (
    AccountDeletionGrant, AccountLifecycleControl, AccountLifecycleNotice, Base,
    School, Session, SessionRecord, User, _now_utc, db_session,
)
from src.routes.golden_plate_recorder_db.users import create_user_record
from src.services import account_lifecycle as lifecycle


@pytest.fixture
def lifecycle_school(client, monkeypatch):
    client.get('/api/auth/status')
    db_session.query(AccountLifecycleNotice).delete()
    db_session.query(AccountDeletionGrant).delete()
    control = db_session.get(AccountLifecycleControl, 'default')
    control.lease_until = None
    control.lease_owner = None
    control.next_run_at = None
    suffix = uuid.uuid4().hex[:10]
    school = School(id=f'life-{suffix}', name='Lifecycle School', slug=f'life-{suffix}')
    db_session.add(school)
    db_session.commit()
    school_id, slug = school.id, school.slug
    supervisor = create_user_record(f'life-super-{suffix}', TEST_SUPERADMIN_PASSWORD_HASH, 'School Superadmin',
                                    role='superadmin', school_id=school_id, password_is_hash=True,
                                    email='supervisor@example.com', email_verified_at=_now_utc())
    supervisor_id, supervisor_name = supervisor.id, supervisor.username
    baseline = lifecycle.policy_start(db_session)
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', 'website@example.com')
    def member(*, verified=False, role='user'):
        user = create_user_record(f'life-{uuid.uuid4().hex[:10]}', TEST_SUPERADMIN_PASSWORD_HASH, 'School Member',
                                  role=role, school_id=school_id, password_is_hash=True,
                                  email='member@example.com' if verified else None,
                                  email_verified_at=baseline if verified else None)
        user.created_at = baseline - timedelta(days=300)
        user.last_login_at = baseline - timedelta(days=100)
        db_session.commit()
        return user.id
    yield {'school_id': school_id, 'slug': slug, 'super_id': supervisor_id, 'super_name': supervisor_name,
           'baseline': baseline, 'member': member}
    db_session.query(AccountLifecycleNotice).delete()
    db_session.query(AccountDeletionGrant).delete()
    db_session.commit()


def run(now):
    assert lifecycle.run_account_lifecycle(app.secret_key, now, force=True)
    db_session.expire_all()


def signin(client, username):
    return client.post('/api/auth/login', json={'username': username, 'password': TEST_SUPERADMIN_PASSWORD})


def owner_token(user_id):
    user = db_session.get(User, user_id)
    grant = AccountDeletionGrant(id=str(uuid.uuid4()), user_id=user.id, school_id=user.school_id,
                                 cycle=lifecycle.cycle_key(user, lifecycle.policy_start(db_session)),
                                 recipient=user.email or '', permission='owner',
                                 expires_at=_now_utc() + timedelta(days=10))
    db_session.add(grant)
    db_session.commit()
    return lifecycle.grant_token(grant.id, app.secret_key)


def confirmation_flow(client, token, username):
    authorized = client.post('/api/account-deletion/authorize', json={
        'token': token, 'username': username, 'password': TEST_SUPERADMIN_PASSWORD,
    })
    assert authorized.status_code == 200, authorized.get_json()
    prepared = client.post('/api/account-deletion/prepare', json={'token': token, 'nonce': authorized.get_json()['nonce']})
    assert prepared.status_code == 200
    return prepared.get_json()['nonce']


@pytest.mark.parametrize('verified,days', [(False, 60), (True, 120)])
def test_exact_fixed_thresholds_and_fresh_baseline(lifecycle_school, verified, days):
    user_id = lifecycle_school['member'](verified=verified)
    baseline = lifecycle_school['baseline']
    run(baseline + timedelta(days=days) - timedelta(seconds=1))
    assert db_session.get(User, user_id).status == 'active'
    run(baseline + timedelta(days=days))
    user = db_session.get(User, user_id)
    assert user.status == 'disabled'
    assert lifecycle.aware(user.inactivity_delete_at) == baseline + timedelta(days=days + 30)


def test_repeated_checks_do_not_shift_archive_or_delete_deadline(lifecycle_school):
    user_id = lifecycle_school['member']()
    baseline = lifecycle_school['baseline']
    run(baseline + timedelta(days=60))
    deadline = db_session.get(User, user_id).inactivity_delete_at
    run(baseline + timedelta(days=61))
    assert db_session.get(User, user_id).inactivity_delete_at == deadline
    run(baseline + timedelta(days=90) - timedelta(seconds=1))
    assert db_session.get(User, user_id) is not None
    run(baseline + timedelta(days=90))
    assert db_session.get(User, user_id) is None


def test_offline_server_gives_full_thirty_days_in_box(lifecycle_school):
    user_id = lifecycle_school['member']()
    now = lifecycle_school['baseline'] + timedelta(days=200)
    run(now)
    assert lifecycle.aware(db_session.get(User, user_id).inactivity_delete_at) == now + timedelta(days=30)


def test_admin_never_automatically_deleted_and_superadmin_exempt(lifecycle_school):
    user_id = lifecycle_school['member'](role='admin')
    baseline = lifecycle_school['baseline']
    run(baseline + timedelta(days=60))
    run(baseline + timedelta(days=500))
    assert db_session.get(User, user_id).status == 'disabled'
    assert db_session.get(User, lifecycle_school['super_id']).status == 'active'


def test_historically_disabled_accounts_get_a_fresh_full_thirty_days(lifecycle_school):
    user_id = lifecycle_school['member']()
    db_session.get(User, user_id).status = 'disabled'
    db_session.commit()
    now = lifecycle_school['baseline'] + timedelta(days=500)
    run(now)
    assert db_session.get(User, user_id) is not None
    assert lifecycle.aware(db_session.get(User, user_id).inactivity_delete_at) == now + timedelta(days=30)
    run(now + timedelta(days=30))
    assert db_session.get(User, user_id) is None


def test_manual_disable_gets_thirty_days_and_repeat_does_not_extend_it(client, lifecycle_school):
    user_id = lifecycle_school['member']()
    name = db_session.get(User, user_id).username
    assert signin(client, lifecycle_school['super_name']).status_code == 200
    assert client.post('/api/admin/manage-account-status', json={'username': name, 'status': 'disabled'}).status_code == 200
    user = db_session.get(User, user_id)
    assert user.disabled_reason == 'manual'
    assert lifecycle.aware(user.inactivity_delete_at) - lifecycle.aware(user.inactivity_disabled_at) == timedelta(days=30)
    original = user.inactivity_delete_at
    assert client.post('/api/admin/manage-account-status', json={'username': name, 'status': 'disabled'}).status_code == 200
    assert db_session.get(User, user_id).inactivity_delete_at == original
    assert client.post('/api/admin/manage-account-status', json={'username': name, 'status': 'invalid'}).status_code == 400


def test_stale_inactivity_check_cannot_disable_a_fresh_login(lifecycle_school):
    user_id = lifecycle_school['member']()
    user = db_session.get(User, user_id)
    now = lifecycle_school['baseline'] + timedelta(days=60)
    with lifecycle.SessionFactory() as other:
        fresh = other.get(User, user_id)
        fresh.last_login_at = now
        fresh.updated_at = now
        other.commit()
    assert lifecycle.enforce_inactivity_for_login(db_session, user, now) is False
    assert user.status == 'active'


def test_password_change_invalidates_deletion_confirmation(client, lifecycle_school):
    user_id = lifecycle_school['member']()
    name = db_session.get(User, user_id).username
    token = owner_token(user_id)
    nonce = confirmation_flow(client, token, name)
    db_session.get(User, user_id).password_hash = 'changed-password-hash'
    db_session.commit()
    assert client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': nonce}).status_code == 403
    assert db_session.get(User, user_id) is not None


def test_unverified_alerts_only_three_events_and_correct_recipients(lifecycle_school, email_outbox):
    user_id = lifecycle_school['member']()
    baseline = lifecycle_school['baseline']
    for days in [46, 57, 60, 83, 89, 90]:
        run(baseline + timedelta(days=days))
    notices = db_session.query(AccountLifecycleNotice).filter_by(user_id=user_id).all()
    assert sorted(notice.event for notice in notices) == ['delete_1', 'delete_1', 'deleted', 'deleted', 'disabled', 'disabled']
    assert {message['to'][0]['email'] for message in email_outbox} == {'supervisor@example.com', 'website@example.com'}
    assert len(email_outbox) == 6
    assert all('/account-deletion#token=' in message['htmlContent'] for message in email_outbox)
    assert all(TEST_SUPERADMIN_PASSWORD not in message['htmlContent'] for message in email_outbox)


def test_verified_owner_milestones_do_not_notify_staff(lifecycle_school, email_outbox):
    user_id = lifecycle_school['member'](verified=True)
    baseline = lifecycle_school['baseline']
    for days in [106, 117, 120, 143, 149, 150]:
        run(baseline + timedelta(days=days))
    assert len(email_outbox) == 6
    assert all(message['to'] == [{'email': 'member@example.com'}] for message in email_outbox)
    assert {row.event for row in db_session.query(AccountLifecycleNotice).filter_by(user_id=user_id)} == {
        'disable_14', 'disable_3', 'disabled', 'delete_7', 'delete_1', 'deleted',
    }


def test_milestones_are_deduplicated_and_configured_addresses_removed(lifecycle_school, email_outbox, monkeypatch):
    lifecycle_school['member']()
    now = lifecycle_school['baseline'] + timedelta(days=60)
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    run(now)
    run(now + timedelta(hours=1))
    assert len(email_outbox) == 1
    assert email_outbox[0]['to'] == [{'email': 'supervisor@example.com'}]


def test_mail_failure_does_not_reverse_archiving_and_is_retried(lifecycle_school, monkeypatch):
    user_id = lifecycle_school['member'](verified=True)
    now = lifecycle_school['baseline'] + timedelta(days=120)
    monkeypatch.setattr(lifecycle, 'send_email_via_brevo', lambda *args, **kwargs: {'success': False})
    run(now)
    assert db_session.get(User, user_id).status == 'disabled'
    notice = db_session.query(AccountLifecycleNotice).filter_by(user_id=user_id).one()
    assert notice.status == 'failed'
    monkeypatch.setattr(lifecycle, 'send_email_via_brevo', lambda *args, **kwargs: {'success': True})
    run(now + timedelta(minutes=3))
    assert db_session.query(AccountLifecycleNotice).filter_by(user_id=user_id).one().status == 'sent'


def test_recipient_removed_from_environment_is_not_sent_a_queued_notice(lifecycle_school, email_outbox, monkeypatch):
    user_id = lifecycle_school['member']()
    now = lifecycle_school['baseline'] + timedelta(days=60)
    lifecycle.plan_lifecycle(db_session, now)
    db_session.commit()
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    lifecycle.deliver_pending_notices(app.secret_key, now)
    assert [message['to'] for message in email_outbox] == [[{'email': 'supervisor@example.com'}]]
    assert db_session.query(AccountLifecycleNotice).filter_by(user_id=user_id, recipient='website@example.com').one().status == 'cancelled'


def test_admin_can_recover_an_admin_but_not_other_schools(client, lifecycle_school):
    target_id = lifecycle_school['member'](role='admin')
    helper_id = lifecycle_school['member'](role='admin', verified=True)
    helper = db_session.get(User, helper_id)
    helper.last_login_at = _now_utc()
    helper_name = helper.username
    db_session.commit()
    # Archive only the target without moving the helper into the future.
    target = db_session.get(User, target_id)
    target.status = 'disabled'
    target.inactivity_disabled_at = _now_utc()
    target.inactivity_delete_at = _now_utc() + timedelta(days=30)
    db_session.commit()
    token = owner_token(target_id)
    assert signin(client, helper_name).status_code == 200
    response = client.post(f'/api/admin/disabled-accounts/{target_id}/restore')
    assert response.status_code == 200
    restored = db_session.get(User, target_id)
    assert restored.status == 'active'
    assert restored.inactivity_delete_at is None
    assert restored.inactivity_restored_at is not None
    assert client.post('/api/account-deletion/inspect', json={'token': token}).status_code == 410
    assert client.post('/api/admin/disabled-accounts/not-this-school/restore').status_code == 404


def test_disabled_owner_cannot_login_but_can_delete_after_credentials_and_two_clicks(client, lifecycle_school):
    user_id = lifecycle_school['member']()
    user = db_session.get(User, user_id)
    name = user.username
    user.status = 'disabled'
    db_session.commit()
    token = owner_token(user_id)
    assert signin(client, name).status_code == 403
    assert client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': 'forged'}).status_code == 403
    nonce = confirmation_flow(client, token, name)
    assert client.get('/api/auth/status').get_json()['authenticated'] is False
    response = client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': nonce})
    assert response.status_code == 200
    assert db_session.get(User, user_id) is None
    assert client.post('/api/account-deletion/inspect', json={'token': token}).get_json()['deleted'] is True


def test_normal_user_can_start_self_deletion_without_approval(client, lifecycle_school):
    user_id = lifecycle_school['member'](verified=True)
    name = db_session.get(User, user_id).username
    assert signin(client, name).status_code == 200
    token = client.post('/api/account-deletion/self').get_json()['token']
    nonce = confirmation_flow(client, token, name)
    assert client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': nonce}).status_code == 200
    assert client.get('/api/auth/status').get_json()['authenticated'] is False


def test_email_link_requires_owner_even_for_a_signed_in_superadmin(client, lifecycle_school):
    user_id = lifecycle_school['member']()
    token = owner_token(user_id)
    assert signin(client, lifecycle_school['super_name']).status_code == 200
    response = client.post('/api/account-deletion/authorize', json={
        'token': token, 'username': lifecycle_school['super_name'], 'password': TEST_SUPERADMIN_PASSWORD,
    })
    assert response.status_code == 403
    assert db_session.get(User, user_id) is not None


@pytest.mark.parametrize('owner', [True, False])
def test_admin_deletion_requires_self_or_explicit_school_superadmin(client, lifecycle_school, owner):
    user_id = lifecycle_school['member'](role='admin')
    user = db_session.get(User, user_id)
    name = user.username
    user.status = 'disabled'
    db_session.commit()
    if owner:
        token = owner_token(user_id)
    else:
        assert signin(client, lifecycle_school['super_name']).status_code == 200
        token = client.post(f'/api/admin/disabled-accounts/{user_id}/deletion-link').get_json()['token']
        name = lifecycle_school['super_name']
    nonce = confirmation_flow(client, token, name)
    assert client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': nonce}).status_code == 200
    assert db_session.get(User, user_id) is None


def test_wrong_password_and_confirmation_order_cannot_delete(client, lifecycle_school):
    user_id = lifecycle_school['member']()
    name = db_session.get(User, user_id).username
    token = owner_token(user_id)
    for _ in range(5):
        assert client.post('/api/account-deletion/authorize', json={'token': token, 'username': name, 'password': 'wrong'}).status_code == 403
    assert client.post('/api/account-deletion/authorize', json={'token': token, 'username': name, 'password': TEST_SUPERADMIN_PASSWORD}).status_code == 429
    assert db_session.get(User, user_id) is not None


def test_first_confirmation_is_not_final_and_cannot_be_replayed(client, lifecycle_school):
    user_id = lifecycle_school['member']()
    name = db_session.get(User, user_id).username
    token = owner_token(user_id)
    auth = client.post('/api/account-deletion/authorize', json={'token': token, 'username': name, 'password': TEST_SUPERADMIN_PASSWORD}).get_json()
    assert client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': auth['nonce']}).status_code == 403
    prepared = client.post('/api/account-deletion/prepare', json={'token': token, 'nonce': auth['nonce']})
    assert prepared.status_code == 200
    assert db_session.get(User, user_id) is not None
    assert client.post('/api/account-deletion/confirm', json={'token': token, 'nonce': auth['nonce']}).status_code == 403


def test_login_cancels_old_notices_and_links(client, lifecycle_school):
    user_id = lifecycle_school['member'](verified=True)
    name = db_session.get(User, user_id).username
    token = owner_token(user_id)
    assert signin(client, name).status_code == 200
    assert client.post('/api/account-deletion/inspect', json={'token': token}).status_code == 410


def test_database_lease_prevents_overlapping_sweeps(lifecycle_school):
    now = _now_utc()
    control = db_session.get(AccountLifecycleControl, 'default')
    control.lease_owner = 'another-process'
    control.lease_until = now + timedelta(minutes=5)
    db_session.commit()
    assert lifecycle.run_account_lifecycle(app.secret_key, now, force=True) is False


def test_record_history_survives_real_foreign_keys(monkeypatch):
    engine = create_engine('sqlite://')
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    now = _now_utc()
    monkeypatch.setenv('WEBSITE_UPDATE_NOTIFY_EMAILS', '')
    with factory() as store:
        store.add(AccountLifecycleControl(id='default', started_at=now))
        store.add(School(id='school', name='School', slug='school'))
        store.flush()
        user = User(id='owner', school_id='school', username='owner', password_hash='test',
                    display_name='Original Owner', role='user', status='disabled', created_at=now, updated_at=now)
        store.add(user)
        store.flush()
        store.add(Session(id='session', school_id='school', created_by='owner', session_name='Historical Session'))
        store.flush()
        store.add(SessionRecord(id='record', school_id='school', session_id='session', recorded_by='owner',
                                category='clean', dedupe_key='historical-record'))
        store.commit()
        lifecycle.permanently_delete_account(store, user, now, explicit=True)
        store.commit()
        assert store.get(User, 'owner') is None
        assert store.get(SessionRecord, 'record').category == 'clean'
        session = store.get(Session, 'session')
        assert session.session_name == 'Historical Session'
        assert store.get(User, session.created_by).display_name == 'Original Owner (deleted)'
        assert store.get(User, session.created_by).is_record_actor == 1
    engine.dispose()


def test_worker_starts_automatically_and_skips_test_or_reloader_processes(monkeypatch):
    monkeypatch.setenv('ACCOUNT_LIFECYCLE_WORKER_ENABLED', 'true')
    calls = []
    monkeypatch.setattr(lifecycle, 'run_account_lifecycle', lambda secret: calls.append(secret))
    test_app = Flask(__name__)
    test_app.secret_key = 'test-key'
    worker = lifecycle.start_account_lifecycle(test_app)
    test_app.extensions['account_lifecycle_stop'].set()
    worker.join(timeout=2)
    assert calls == ['test-key']
    assert lifecycle.start_account_lifecycle(test_app) is None
    assert lifecycle.start_account_lifecycle(Flask('reloader'), reloader_parent=True) is None
    test_app.testing = True
    assert lifecycle.start_account_lifecycle(test_app) is None


def test_schema_upgrade_preserves_accounts_and_the_original_tracking_baseline(monkeypatch):
    from sqlalchemy import text
    from src.routes.golden_plate_recorder_db import db as database
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(School.__table__.insert().values(id='existing', name='Existing', slug='existing'))
        connection.execute(User.__table__.insert().values(
            id='existing-user', school_id='existing', username='existing', password_hash='unchanged',
            display_name='Existing User', role='user', email='existing@example.com',
        ))
        for column in ['inactivity_disabled_at', 'inactivity_delete_at', 'inactivity_restored_at', 'disabled_reason', 'is_record_actor']:
            connection.execute(text(f'ALTER TABLE users DROP COLUMN {column}'))
        AccountLifecycleControl.__table__.drop(connection)
    monkeypatch.setattr(database, 'engine', engine)
    database._bootstrap_database()
    with engine.begin() as connection:
        original = connection.execute(text("SELECT started_at FROM account_lifecycle_control WHERE id='default'")).scalar_one()
        assert original.startswith('2026-11-01 04:00:00')
        connection.execute(text("UPDATE account_lifecycle_control SET started_at='2026-10-18 04:00:00', next_run_at='2026-12-01 04:00:00' WHERE id='default'"))
    database._bootstrap_database()
    with engine.begin() as connection:
        row = connection.execute(text("SELECT started_at, next_run_at FROM account_lifecycle_control WHERE id='default'")).one()
        assert row.started_at.startswith('2026-11-01 04:00:00')
        assert row.next_run_at is None
        connection.execute(text("UPDATE account_lifecycle_control SET started_at='2026-11-02 05:00:00' WHERE id='default'"))
    database._bootstrap_database()
    with engine.connect() as connection:
        row = connection.execute(text("SELECT password_hash, email, is_record_actor, inactivity_delete_at FROM users WHERE id='existing-user'")).one()
        assert tuple(row) == ('unchanged', 'existing@example.com', 0, None)
        assert connection.execute(text("SELECT started_at FROM account_lifecycle_control WHERE id='default'")).scalar_one().startswith('2026-11-02 05:00:00')
    engine.dispose()
