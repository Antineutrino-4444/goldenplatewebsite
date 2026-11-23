"""Stable provider files, retries, grants and inter-worker fencing for assembly decks."""

import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from io import BytesIO
from types import SimpleNamespace

import pytest
from flask import Flask
from pptx import Presentation

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
    original_upload = cloud.upsert_deck
    monkeypatch.setattr(cloud, 'upsert_deck', upload)

    def lunch(clean, *, name=None, **fields):
        with SessionFactory() as store:
            session = Session(school_id=school_id, session_name=name or 'Lunch ' + uuid.uuid4().hex,
                              created_by=owner_id, clean_number=clean, status='active', is_public=0, **fields)
            store.add(session)
            store.commit()
            return session.id

    yield SimpleNamespace(school=school_id, owner=owner_id, token=token, lunch=lunch,
                          calls=calls, grants=grants, upload=upload, original_upload=original_upload)
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


def test_existing_deck_table_gains_nullable_label_without_losing_rows(monkeypatch):
    from sqlalchemy import create_engine
    from src.routes.golden_plate_recorder_db import db

    legacy = create_engine('sqlite://')
    monkeypatch.setattr(db, 'engine', legacy)
    with legacy.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE assembly_decks (id VARCHAR PRIMARY KEY, web_url VARCHAR)')
        connection.exec_driver_sql("INSERT INTO assembly_decks VALUES ('original', 'https://example.test/deck')")
    db._migrate_schema()
    db._migrate_schema()
    with legacy.connect() as connection:
        assert connection.exec_driver_sql('SELECT id, web_url, school_label FROM assembly_decks').one() == (
            'original', 'https://example.test/deck', None)
    legacy.dispose()


def test_label_edited_during_upload_preserves_cloud_file_and_schedules_latest_label(setup, monkeypatch):
    key = (setup.school, setup.owner, 'google', 'light')
    deck = sync.bind_deck(*key, setup.token, school_label='First name')
    seen = []

    def upload(provider, access, binding, file_id, snapshot, theme):
        seen.append((file_id, snapshot['school_label']))
        if len(seen) == 1:
            assert sync.set_school_label(*key, 'Final name')['status'] == 'pending'
        return setup.upload(provider, access, binding, file_id, snapshot, theme)

    monkeypatch.setattr(cloud, 'upsert_deck', upload)
    first = sync.sync_deck(deck['id'], force=True)
    assert first['status'] == 'pending' and first['school_label'] == 'Final name'
    sync.run_due_decks()
    last = sync.get_deck(*key)
    assert last['status'] == 'ready' and last['url'] == first['url']
    assert seen == [(None, 'First name'), ('one-file-' + deck['id'], 'Final name')]
    assert setup.grants == [setup.token, setup.token + '-rotated']


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


def test_new_design_refreshes_the_same_deck_once_with_unchanged_results(setup, monkeypatch):
    key = (setup.school, setup.owner, 'google', 'dark')
    deck_id = sync.bind_deck(*key, setup.token)['id']
    setup.lunch(12)
    with monkeypatch.context() as previous:
        previous.setattr(sync, 'ASSEMBLY_DESIGN_REVISION', sync.ASSEMBLY_DESIGN_REVISION - 1)
        original = sync.sync_deck(deck_id, force=True)

    make_due(deck_id)
    sync.run_due_decks()
    refreshed = sync.get_deck(*key)
    assert refreshed['status'] == 'ready' and refreshed['url'] == original['url']
    make_due(deck_id)
    sync.run_due_decks()
    assert setup.calls == [(deck_id, None, 12), (deck_id, 'one-file-' + deck_id, 12)]
    assert len(setup.grants) == 2


@pytest.mark.parametrize(('provider', 'theme'), [('google', 'dark'), ('microsoft', 'light')])
def test_connected_file_rebuilds_edited_lunch_chart_goal_and_type(setup, monkeypatch, provider, theme):
    file_id = 'linked-assembly'
    writes = []

    def store_file(method, url, *, headers, **options):
        if method == 'GET':
            return {'files': []} if provider == 'google' else {'id': 'app-folder'}
        blob = options['data']
        if provider == 'google':
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {headers['Content-Type']}\r\n\r\n".encode() + blob)
            blob, = (part.get_payload(decode=True) for part in message.iter_parts()
                     if part.get_content_type() == cloud.PPTX_MIME)
        writes.append((method, url, Presentation(BytesIO(blob))))
        return {'id': file_id, 'mimeType': cloud.SLIDES_MIME, 'webUrl': 'https://example.test/' + file_id}

    monkeypatch.setattr(cloud, 'upsert_deck', setup.original_upload)
    monkeypatch.setattr(cloud, '_request', store_file)
    with SessionFactory.begin() as store:
        store.get(School, setup.school).live_counter_settings = '{"milestone": 200}'
    first_lunch = datetime(2026, 11, 16, 17, tzinfo=timezone.utc)
    setup.lunch(45, name='Monday Lunch', dirty_number=15, created_at=first_lunch)
    key = (setup.school, setup.owner, provider, theme)
    deck_id = sync.bind_deck(*key, setup.token)['id']
    sync.run_due_decks()
    original_url = sync.get_deck(*key)['url']
    latest_id = setup.lunch(90, name='Friday Lunch', dirty_number=10, created_at=first_lunch + timedelta(days=4))

    def refresh():
        make_due(deck_id)
        sync.run_due_decks()
        current = sync.get_deck(*key)
        assert current['status'] == 'ready' and current['url'] == original_url

    refresh()
    with SessionFactory.begin() as store:
        store.get(Session, latest_id).clean_number = 91
    refresh()
    refresh()  # An unchanged snapshot must not cause a fourth upload.

    assert [len(deck.slides) for _, _, deck in writes] == [4, 6, 6]
    update = ('PATCH', cloud.UPLOAD + '/' + file_id) if provider == 'google' else (
        'PUT', cloud.ONEDRIVE + '/items/' + file_id + '/content')
    for (method, url, deck), clean, total, rate in zip(writes[1:], [90, 91], [100, 101], [90, 90.1]):
        assert (method, url) == update
        cover = {shape.name: shape for shape in deck.slides[0].shapes}
        chart = {shape.name: shape for shape in deck.slides[3].shapes}
        assert cover['all_clean'].text == f'{45 + clean} clean plates'
        assert cover['latest_date'].text == 'Nov 20, 2026'
        assert cover['latest_date'].text_frame.paragraphs[0].runs[0].font.italic
        assert cover['goal_label'].text == f'{200 - 45 - clean} to the 200-plate goal'
        assert cover['goal_label'].text_frame.paragraphs[0].runs[0].font.bold
        assert cover['Clean plates toward milestone'].width / cover['progress_track'].width == pytest.approx(
            (45 + clean) / 200, abs=1e-6)
        assert chart['curr_counts'].text == f'{clean} of {total} plates were clean'
        assert chart['curr_fill'].width / chart['curr_track'].width == pytest.approx(rate / 100, abs=1e-6)
        assert chart['rate_comparison'].text == f'{rate - 75:g} percentage points higher'
        assert chart['rate_comparison'].text_frame.paragraphs[0].runs[0].font.bold
        assert f'{clean} of {total} recorded plates' in deck.slides[1].notes_slide.notes_text_frame.text


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
