"""Stable provider files, retries, grants and inter-worker fencing for assembly decks."""

import json
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
from src.routes.golden_plate_recorder_db.db import (
    AssemblyDeck, School, Session, SessionDrawEvent, SessionFactory, User, db_session, _now_utc,
)
from src.services import assembly_cloud as cloud
from assembly_google_fixtures import from_powerpoint, registered


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
def test_winner_finalized_during_upload_is_not_lost_and_reuses_rotated_token(setup, monkeypatch, provider):
    lunch_id = setup.lunch(12)
    key = (setup.school, setup.owner, provider, 'light')
    deck_id = sync.bind_deck(*key, setup.token)['id']
    winners = []

    def upload(provider, access, binding, file_id, snapshot, theme):
        winners.append(snapshot.get('winner_names', {}))
        if len(winners) == 1:
            with SessionFactory.begin() as store:
                meal = store.get(Session, lunch_id)
                meal.faculty_finalized = 1
                meal.faculty_pick_display_name = 'Morgan Ellis'
                sync.queue_school_decks(store, setup.school)
        return setup.upload(provider, access, binding, file_id, snapshot, theme)

    monkeypatch.setattr(cloud, 'upsert_deck', upload)
    first = sync.sync_deck(deck_id, force=True)
    assert first['status'] == 'pending'
    db_session.remove()  # The worker closes its app context between passes.
    sync.run_due_decks()
    final = sync.get_deck(*key)
    assert final['status'] == 'ready' and final['url'] == first['url']
    assert winners == [{}, {'faculty': 'Morgan Ellis'}]
    assert setup.grants == [setup.token, setup.token + '-rotated']


def test_winner_queue_respects_school_disconnected_grants_and_transaction_rollback(setup):
    keys = [(setup.school, setup.owner, p, t) for p, t in
            [('google', 'light'), ('google', 'dark'), ('microsoft', 'light'), ('microsoft', 'dark')]]
    decks = [sync.bind_deck(*key, setup.token) for key in keys]
    later = _now_utc() + timedelta(hours=1)
    with SessionFactory.begin() as store:
        for deck, status in zip(decks, ['ready', 'retry', 'reconnect', 'disconnected']):
            row = store.get(AssemblyDeck, deck['id'])
            row.status = status
            row.next_check_at = later
    with SessionFactory() as store:
        assert sync.queue_school_decks(store, 'another-school') == 0
        assert sync.queue_school_decks(store, setup.school) == 2
        store.rollback()
    assert sync.get_deck(*keys[0])['status'] == 'ready'
    with SessionFactory.begin() as store:
        assert sync.queue_school_decks(store, setup.school) == 2
    assert [sync.get_deck(*key)['status'] for key in keys[:3]] == ['pending', 'pending', 'reconnect']
    assert sync.get_deck(*keys[3]) is None


def test_finalization_wakes_sleeping_worker_without_waiting_for_poll_timer(setup, monkeypatch):
    app = Flask(__name__)
    idle, awakened = threading.Event(), threading.Event()
    passes = []
    def check():
        passes.append(True)
        (idle if len(passes) == 1 else awakened).set()
    monkeypatch.setattr(sync, 'run_due_decks', check)
    monkeypatch.setenv('ASSEMBLY_SYNC_WORKER_ENABLED', 'true')
    sync.start_assembly_sync(app)
    try:
        assert idle.wait(2)
        with app.app_context():
            sync.wake_assembly_sync()
        assert awakened.wait(2)
    finally:
        app.extensions['assembly_sync_stop'].set()
        app.extensions['assembly_sync_wake'].set()


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


def test_manual_sync_bypasses_backoff_and_refreshes_unchanged_results_in_original_file(setup):
    key = (setup.school, setup.owner, 'microsoft', 'dark')
    deck = sync.bind_deck(*key, setup.token)
    sync.run_due_decks()
    ready = sync.get_deck(*key)
    assert len(setup.calls) == 1
    assert sync.request_deck_sync(deck['id'], 'another-school') is None
    assert sync.request_deck_sync(deck['id'], setup.school, owner_id='another-owner') is None
    requested = sync.request_deck_sync(deck['id'], setup.school, owner_id=setup.owner)
    assert requested['status'] == 'pending' and requested['url'] == ready['url']
    assert len(setup.calls) == 1
    sync.run_due_decks()
    assert setup.calls == [(deck['id'], None, 0), (deck['id'], 'one-file-' + deck['id'], 0)]
    assert sync.get_deck(*key)['status'] == 'ready'


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_google_design_refreshes_only_the_connected_google_deck_once(setup, monkeypatch, provider):
    key = (setup.school, setup.owner, provider, 'dark')
    deck_id = sync.bind_deck(*key, setup.token)['id']
    setup.lunch(12)
    with monkeypatch.context() as previous:
        previous.setitem(sync.ASSEMBLY_DESIGN_REVISIONS, provider, 33 if provider == 'microsoft' else 14)
        original = sync.sync_deck(deck_id, force=True)

    make_due(deck_id)
    sync.run_due_decks()
    refreshed = sync.get_deck(*key)
    assert refreshed['status'] == 'ready' and refreshed['url'] == original['url']
    make_due(deck_id)
    sync.run_due_decks()
    expected = [(deck_id, None, 12)]
    if provider == 'google':
        expected.append((deck_id, 'one-file-' + deck_id, 12))
    assert setup.calls == expected
    assert len(setup.grants) == len(expected)


@pytest.mark.parametrize('provider', ['microsoft', 'google'])
def test_school_timezone_refreshes_the_managed_footer(setup, provider):
    key = (setup.school, setup.owner, provider, 'light')
    deck_id = sync.bind_deck(*key, setup.token)['id']
    before = sync.sync_deck(deck_id, force=True)
    with SessionFactory() as store:
        school = store.get(School, setup.school)
        school.live_counter_settings = '{"timezone":"America/Chicago"}'
        store.commit()
    after = sync.sync_deck(deck_id, force=True)
    assert after['status'] == 'ready' and after['url'] == before['url']
    assert len(setup.calls) == 2


def test_draw_ticket_correction_refreshes_both_decks_without_new_plates(setup, monkeypatch):
    lunch_id = setup.lunch(12, faculty_finalized=1, faculty_pick_display_name='Morgan Ellis')
    with SessionFactory.begin() as store:
        pick = SessionDrawEvent(school_id=setup.school, session_id=lunch_id, draw_target='faculty',
                                event_type='draw', faculty_name='Morgan Ellis', tickets_at_event=4,
                                probability_at_event=1250, eligible_pool_size=10, created_by=setup.owner)
        store.add(pick)
        store.flush()
        pick_id = pick.id
    sent = []

    def upload(provider, token, binding, file_id, snapshot, theme):
        details = snapshot.get('winner_details', {}).get('faculty', {})
        sent.append((provider, file_id, details.get('tickets')))
        return setup.upload(provider, token, binding, file_id, snapshot, theme)

    monkeypatch.setattr(cloud, 'upsert_deck', upload)
    decks = [sync.bind_deck(setup.school, setup.owner, provider, 'dark', setup.token)['id']
             for provider in ('microsoft', 'google')]
    for deck_id in decks:
        assert sync.sync_deck(deck_id, force=True)['status'] == 'ready'
    with SessionFactory.begin() as store:
        store.get(SessionDrawEvent, pick_id).tickets_at_event = 7
    for deck_id in decks:
        assert sync.sync_deck(deck_id, force=True)['status'] == 'ready'
        assert sync.sync_deck(deck_id, force=True)['status'] == 'ready'
    assert sent == [('microsoft', None, 4), ('google', None, 4),
                    ('microsoft', 'one-file-' + decks[0], 7), ('google', 'one-file-' + decks[1], 7)]


@pytest.mark.parametrize(('provider', 'theme'), [('google', 'dark'), ('microsoft', 'light')])
def test_connected_file_rebuilds_edited_lunch_chart_goal_and_type(setup, monkeypatch, provider, theme):
    file_id = 'linked-assembly'
    writes = []

    stored = None
    native, metadata, native_batches = {}, {}, []
    remote = {'id': file_id, 'webUrl': 'https://example.test/' + file_id,
              '@microsoft.graph.downloadUrl': 'https://files.example/download'}

    def store_file(method, url, *, headers=None, **options):
        nonlocal stored
        if provider == 'google':
            if method == 'GET' and url == cloud.DRIVE:
                return {'files': []}
            if method == 'GET' and url.startswith(cloud.GOOGLE_SLIDES):
                return native[url.rsplit('/', 1)[1]]
            if method == 'GET':
                return metadata[file_id]
            if method == 'DELETE':
                assert url == cloud.DRIVE + '/scratch'
                return {}
            if url.endswith(':batchUpdate'):
                assert url == cloud.GOOGLE_SLIDES + file_id + ':batchUpdate'
                body = options['json']
                assert 'writeControl' not in body
                if 'scratch' in native:
                    native_batches.append(body['requests'])
                    native[file_id] = registered(native['scratch'])
                else:
                    native[file_id] = registered(native[file_id])
                return {}
            assert (method, url) == ('POST', cloud.UPLOAD)
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {headers['Content-Type']}\r\n\r\n".encode() + options['data'])
            meta_part, media_part = message.iter_parts()
            meta = json.loads(meta_part.get_payload(decode=True))
            ident = 'scratch' if 'gpAssemblyScratch' in meta['appProperties'] else file_id
            deck = Presentation(BytesIO(media_part.get_payload(decode=True)))
            writes.append((method, url, deck))
            native[ident], metadata[ident] = from_powerpoint(deck), {**meta, 'id': ident}
            return metadata[ident]
        if method == 'GET':
            if url.endswith('/special/approot'):
                return {'id': 'app-folder'}
            if options.get('missing_ok') and stored is None:
                return None
            if options.get('binary'):
                return stored
            return {**remote, 'eTag': f'"version,{len(writes)}"'}
        if url.endswith('/createUploadSession'):
            assert 'If-Match' not in headers
            assert options['json']['item']['@microsoft.graph.conflictBehavior'] == 'replace'
            return {'uploadUrl': 'https://files.example/session'}
        stored = options['data']
        writes.append((method, url, Presentation(BytesIO(stored))))
        return remote

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

    assert [len(deck.slides) for _, _, deck in writes] == ([9, 9, 9] if provider == 'google' else [7, 9, 9])
    if provider == 'google':
        assert len(native_batches) == 2
        assert any(op.get('updateSlideProperties', {}).get('slideProperties') == {'isSkipped': False}
                   for op in native_batches[0])
    update = ('POST', cloud.UPLOAD) if provider == 'google' else (
        'PUT', 'https://files.example/session')
    for (method, url, deck), clean, total, rate in zip(writes[1:], [90, 91], [100, 101], [90, 90.1]):
        assert (method, url) == update
        overview = next(page for page in deck.slides if any(shape.name == 'all_clean' for shape in page.shapes))
        cover = {shape.name: shape for shape in overview.shapes}
        chart = {shape.name: shape for shape in deck.slides[4].shapes}
        assert cover['all_clean'].text == f'{45 + clean} clean plates'
        assert cover['latest_date'].text == 'Nov 20, 2026'
        assert cover['latest_date'].text_frame.paragraphs[0].runs[0].font.italic
        assert cover['goal_label'].text == f'{200 - 45 - clean} to the 200-plate goal'
        assert cover['goal_label'].text_frame.paragraphs[0].runs[0].font.bold
        assert cover['Clean plates toward milestone'].width / cover['progress_track'].width == pytest.approx(
            (45 + clean) / 200, abs=1e-6)
        # Refreshed school data can change the shape IDs. The PowerPoint float
        # must still target the live change figure in each uploaded file.
        motion_targets = overview._element.xpath('.//p:animMotion//p:spTgt/@spid')
        if provider == 'microsoft':
            assert str(cover['latest_change'].shape_id) in motion_targets
            assert str(cover['all_clean'].shape_id) in motion_targets
        assert chart['curr_counts'].text == f'{clean} of {total} plates were clean'
        assert chart['curr_fill'].width / chart['curr_track'].width == pytest.approx(rate / 100, abs=1e-6)
        assert chart['rate_comparison'].text == f'{rate - 75:g} percentage points higher'
        assert chart['rate_comparison'].text_frame.paragraphs[0].runs[0].font.bold
        assert f'{clean} of {total} recorded plates' in deck.slides[2].notes_slide.notes_text_frame.text


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
