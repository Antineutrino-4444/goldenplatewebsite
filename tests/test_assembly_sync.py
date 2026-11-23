"""Stable provider files, retries, grants and inter-worker fencing for assembly decks."""

import secrets
import threading
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from src.routes.golden_plate_recorder_db import assembly_sync as sync
from src.routes.golden_plate_recorder_db.db import AssemblyDeck, School, Session, SessionFactory, User, db_session, _now_utc
from src.services import assembly_cloud as cloud


@pytest.fixture
def setup(monkeypatch):
    ident = uuid.uuid4().hex
    school_id, owner_id = 'school-' + ident, 'teacher-' + ident
    with SessionFactory() as store:
        store.add(School(id=school_id, slug=ident, name='Assembly School'))
        store.flush()
        store.add(User(id=owner_id, school_id=school_id, username=owner_id, display_name='Teacher',
                       role='user', password_hash='unused', status='active'))
        store.commit()
    token = secrets.token_urlsafe()
    monkeypatch.delenv('ASSEMBLY_SYNC_ENCRYPTION_KEY', raising=False)
    monkeypatch.setenv('SECRET_KEY', secrets.token_urlsafe())
    monkeypatch.setattr(cloud, 'provider_configured', lambda provider: True)
    calls, grants = [], []

    def refresh(provider, refresh_token):
        grants.append(refresh_token)
        return {'access_token': 'access', 'refresh_token': refresh_token + '-rotated'}

    def upload(provider, access_token, binding_key, file_id, snapshot, theme):
        calls.append((binding_key, file_id, snapshot['totals']['clean']))
        return 'one-file-' + binding_key, 'https://example.com/one-file-' + binding_key

    monkeypatch.setattr(cloud, 'refresh_access', refresh)
    monkeypatch.setattr(cloud, 'upsert_deck', upload)

    def lunch(clean):
        with SessionFactory() as store:
            store.add(Session(school_id=school_id, session_name='Lunch ' + uuid.uuid4().hex, created_by=owner_id,
                              clean_number=clean, status='active', is_public=0))
            store.commit()

    yield SimpleNamespace(school=school_id, owner=owner_id, token=token, lunch=lunch,
                          calls=calls, grants=grants, upload=upload)
    db_session.remove()
    with SessionFactory() as store:
        store.query(AssemblyDeck).filter_by(school_id=school_id).delete()
        store.query(Session).filter_by(school_id=school_id).delete()
        store.query(User).filter_by(school_id=school_id).delete()
        store.query(School).filter_by(id=school_id).delete()
        store.commit()


def make_due(deck_id):
    with SessionFactory() as store:
        store.get(AssemblyDeck, deck_id).next_check_at = _now_utc() - timedelta(seconds=1)
        store.commit()


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_worker_updates_same_remote_file_after_lunch_and_skips_unchanged_results(setup, provider):
    key = (setup.school, setup.owner, provider, 'light')
    deck = sync.bind_deck(*key, setup.token)
    assert deck['status'] == 'pending'
    setup.lunch(12)
    sync.run_due_decks()
    ready = sync.get_deck(*key)
    assert ready['status'] == 'ready'
    assert sync.list_decks(setup.school, 'another-teacher') == []
    assert [c[-1] for c in setup.calls] == [12]
    # generated_at changes with each query but does not imply the lunch changed.
    assert sync.sync_deck(deck['id'], force=True)['last_synced_at'] == ready['last_synced_at']
    setup.lunch(9)
    make_due(deck['id'])
    sync.run_due_decks()
    latest = sync.get_deck(*key)
    assert latest['id'] == deck['id'] and latest['url'] == ready['url']
    assert setup.calls == [(deck['id'], None, 12), (deck['id'], 'one-file-' + deck['id'], 21)]
    assert setup.grants == [setup.token, setup.token + '-rotated']
    with SessionFactory() as store:
        saved = store.get(AssemblyDeck, deck['id'])
        assert setup.token not in saved.encrypted_refresh_token
        assert sync._cipher().decrypt(saved.encrypted_refresh_token.encode()).decode() == setup.token + '-rotated-rotated'


def test_write_failure_reuses_rotated_grant_and_guarded_claim(setup, monkeypatch):
    deck = sync.bind_deck(setup.school, setup.owner, 'google', 'dark', setup.token)

    def unavailable(*args):
        # A simultaneous on-open check cannot start a second upload.
        assert sync.sync_deck(deck['id'], force=True)['status'] == 'pending'
        raise cloud.CloudDeckError('Cloud service temporarily unavailable.')

    monkeypatch.setattr(cloud, 'upsert_deck', unavailable)
    assert sync.sync_deck(deck['id'], force=True)['status'] == 'retry'
    sync.run_due_decks()
    assert setup.grants == [setup.token]  # retry backoff applies to workers
    monkeypatch.setattr(cloud, 'upsert_deck', setup.upload)
    assert sync.sync_deck(deck['id'], force=True)['status'] == 'ready'
    assert setup.grants[-1] == setup.token + '-rotated'


def test_losing_school_access_drops_grant_before_contacting_cloud(setup):
    deck = sync.bind_deck(setup.school, setup.owner, 'microsoft', 'light', setup.token)
    with SessionFactory() as store:
        store.get(User, setup.owner).status = 'disabled'
        store.commit()
    assert sync.sync_deck(deck['id'], force=True)['status'] == 'reconnect'
    with SessionFactory() as store:
        assert store.get(AssemblyDeck, deck['id']).encrypted_refresh_token is None
    assert not setup.calls and not setup.grants


def test_disconnect_during_refresh_fences_external_write_and_can_resume_existing_link(setup, monkeypatch):
    key = (setup.school, setup.owner, 'google', 'light')
    deck_id = sync.bind_deck(*key, setup.token)['id']
    original = sync.sync_deck(deck_id, force=True)
    setup.lunch(8)
    refresh = cloud.refresh_access

    def disconnect(*args):
        assert sync.disconnect_deck(*key)
        return refresh(*args)

    monkeypatch.setattr(cloud, 'refresh_access', disconnect)
    assert sync.sync_deck(deck_id, force=True) is None
    assert sync.list_decks(setup.school, setup.owner) == []
    assert len(setup.calls) == 1
    monkeypatch.setattr(cloud, 'refresh_access', refresh)
    assert sync.bind_deck(*key, setup.token)['id'] == deck_id
    assert sync.sync_deck(deck_id, force=True)['url'] == original['url']
    assert setup.calls[-1] == (deck_id, 'one-file-' + deck_id, 8)


def test_revoked_provider_access_pauses_until_reconnect(setup, monkeypatch):
    deck_id = sync.bind_deck(setup.school, setup.owner, 'google', 'light', setup.token)['id']

    def revoked(*args):
        raise cloud.CloudDeckError('Reconnect to Google Drive.', reconnect=True)

    monkeypatch.setattr(cloud, 'refresh_access', revoked)
    assert sync.sync_deck(deck_id, force=True)['status'] == 'reconnect'
    with SessionFactory() as store:
        row = store.get(AssemblyDeck, deck_id)
        assert row.encrypted_refresh_token is None and row.next_check_at is None
    assert not setup.calls


def test_worker_resumes_an_expired_claim_without_creating_a_second_binding(setup):
    deck_id = sync.bind_deck(setup.school, setup.owner, 'google', 'dark', setup.token)['id']
    with SessionFactory() as store:
        row = store.get(AssemblyDeck, deck_id)
        row.lease_owner = 'interrupted-process'
        row.lease_until = _now_utc() + timedelta(minutes=5)
        store.commit()
    sync.run_due_decks()
    assert not setup.grants
    with SessionFactory() as store:
        store.get(AssemblyDeck, deck_id).lease_until = _now_utc() - timedelta(seconds=1)
        store.commit()
    sync.run_due_decks()
    assert setup.calls == [(deck_id, None, 0)]


def test_background_thread_catches_up_existing_decks_on_startup_without_a_site_visit(setup, monkeypatch):
    setup.lunch(8)
    decks = [sync.bind_deck(setup.school, setup.owner, provider, 'light', setup.token)
             for provider in ('google', 'microsoft')]
    initial = [sync.sync_deck(deck['id'], force=True) for deck in decks]
    setup.lunch(12)
    with SessionFactory.begin() as store:
        store.query(AssemblyDeck).filter_by(owner_id=setup.owner).update({'next_check_at': _now_utc()})

    app = Flask(__name__)
    done = threading.Event()
    check_due = sync.run_due_decks
    def complete_cycle():
        try:
            check_due()
        finally:
            db_session.remove()
            done.set()
    monkeypatch.setattr(sync, 'run_due_decks', complete_cycle)
    monkeypatch.setenv('ASSEMBLY_SYNC_WORKER_ENABLED', 'true')
    sync.start_assembly_sync(app)
    try:
        assert done.wait(6)
        last = {key: (file_id, count) for key, file_id, count in setup.calls}
        for deck in initial:
            assert last[deck['id']] == ('one-file-' + deck['id'], 20)
            assert sync.get_deck(setup.school, setup.owner, deck['provider'], 'light')['url'] == deck['url']
    finally:
        app.extensions['assembly_sync_stop'].set()


def test_account_deletion_erases_the_stored_cloud_grant(setup):
    from src.services.account_lifecycle import permanently_delete_account

    deck_id = sync.bind_deck(setup.school, setup.owner, 'microsoft', 'light', setup.token)['id']
    with SessionFactory() as store:
        permanently_delete_account(store, store.get(User, setup.owner), _now_utc(), explicit=True)
        store.commit()
        assert store.get(AssemblyDeck, deck_id) is None
