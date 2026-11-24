"""Exercise the teacher flow through consent, unattended refresh and disconnect."""
import hashlib
import base64
import secrets
import io
import threading
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from src.routes.golden_plate_recorder_db import assembly_sync as sync
from src.routes.golden_plate_recorder_db.db import AssemblyDeck, School, Session, SessionFactory, User, _now_utc, db_session
from src.routes.golden_plate_recorder_db.users import create_user_record
from src.services import assembly_cloud as cloud

BASE = '/api/resources/presentations/live'


@pytest.fixture
def classroom(client, monkeypatch):
    private_key = secrets.token_urlsafe()
    monkeypatch.setenv('SECRET_KEY', private_key)
    monkeypatch.setitem(client.application.config, 'SECRET_KEY', private_key)
    client.get('/api/auth/status')
    tag = uuid4().hex[:10]
    school = School(id='assembly-' + tag, name='Assembly School', slug='assembly-' + tag)
    db_session.add(school)
    db_session.commit()
    user = create_user_record('teacher-' + tag, 'teacher-password', 'Classroom teacher', school_id=school.id)
    identity = (user.id, user.username, school.id, school.slug)
    monkeypatch.setenv('ASSEMBLY_SYNC_ENCRYPTION_KEY', Fernet.generate_key().decode())
    for provider in ('GOOGLE', 'MICROSOFT'):
        monkeypatch.setenv(provider + '_SLIDES_CLIENT_ID', uuid4().hex)
        monkeypatch.setenv(provider + '_SLIDES_CLIENT_SECRET', secrets.token_urlsafe())
    monkeypatch.setenv('ASSEMBLY_SYNC_BASE_URL', 'http://localhost')
    return identity


def sign_in(client, classroom):
    assert client.post('/api/auth/login', json={'username': classroom[1], 'password': 'teacher-password'}).status_code == 200


def begin(client, body):
    response = client.post(BASE + '/connect', json=body)
    assert response.status_code == 200, response.get_json()
    return parse_qs(urlsplit(response.json['authorization_url']).query)


@pytest.mark.parametrize('provider', ('google', 'microsoft'))
def test_same_native_link_updates_after_a_lunch_without_reopening_site(client, monkeypatch, classroom, provider):
    owner, _, school, slug = classroom
    details = {'school_code': slug, 'provider': provider, 'theme': 'dark'}
    assert client.post(BASE + '/connect', json=details).status_code == 401
    sign_in(client, classroom)
    args = begin(client, {**details, 'school_label': '  Student\n Council  '})
    callback = BASE + '/callback/' + provider
    assert args['redirect_uri'] == ['http://localhost' + callback]
    refresh = secrets.token_urlsafe()
    writes, labels = [], []
    def exchange(received_provider, uri, code, verifier):
        assert received_provider == provider and uri == 'http://localhost' + callback and code == 'from-provider'
        assert base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=') == args['code_challenge'][0]
        return {'refresh_token': refresh, 'access_token': 'initial-access'}

    def update(received_provider, token, binding, file_id, data, theme):
        assert received_provider == provider and token == 'fresh-access' and theme == 'dark'
        writes.append((binding, file_id, data['totals']['clean']))
        labels.append((data['school_name'], data['school_label']))
        return 'dedicated-id', 'https://example.test/assembly/dedicated-id'

    monkeypatch.setattr(cloud, 'exchange_code', exchange)
    monkeypatch.setattr(cloud, 'refresh_access', lambda name, value: {'access_token': 'fresh-access'} if value == refresh else pytest.fail('wrong grant'))
    monkeypatch.setattr(cloud, 'upsert_deck', update)
    params = {'state': args['state'][0], 'code': 'from-provider'}
    response = client.get(callback, query_string=params)
    assert response.status_code == 303 and response.location == 'https://example.test/assembly/dedicated-id'
    assert 'authorization' in client.get(callback, query_string=params).location  # consumed
    assert writes[0][1:] == (None, 0)
    unchanged = client.post(BASE + '/connect', json=details).json
    assert unchanged['url'] == response.location and unchanged['school_label'] == 'Student Council'
    assert len(writes) == 1
    with SessionFactory.begin() as store:
        row = store.query(AssemblyDeck).filter_by(owner_id=owner, provider=provider).one()
        assert refresh not in row.encrypted_refresh_token
        store.add(Session(school_id=school, session_name='New lunch', created_by=owner, clean_number=34,
                          created_at=_now_utc(), status='active', is_public=0))
        row.next_check_at = _now_utc() - timedelta(seconds=1)
    sync.run_due_decks()
    assert writes == [(writes[0][0], None, 0), (writes[0][0], 'dedicated-id', 34)]
    listing = client.get(BASE, query_string=details).json
    link = listing['links'][provider]
    assert {field: link[field] for field in ('url', 'status', 'school_label')} == {
        'url': response.location, 'status': 'ready', 'school_label': 'Student Council'}
    assert link['message'] is None and link['attempts'] == 0 and link['lease_until'] is None
    assert link['last_synced_at'] and link['next_check_at']
    registered = listing['school_name']
    assert registered and labels == [(registered, 'Student Council')] * 2
    renamed = client.post(BASE + '/connect', json={**details, 'school_label': 'Campus North'}).json
    assert renamed == {'url': response.location, 'status': 'ready', 'school_label': 'Campus North'}
    assert client.post(BASE + '/connect', json={**details, 'school_label': ' '}).json['school_label'] is None
    assert client.post(BASE + '/connect', json=details).json['url'] == response.location
    assert labels[-2:] == [(registered, 'Campus North'), (registered, None)]
    assert all(binding == writes[0][0] and file_id == 'dedicated-id' for binding, file_id, _ in writes[1:])
    assert client.delete(BASE, json=details).status_code == 200
    assert client.get(BASE, query_string=details).json['links'] == {}
    sync.run_due_decks()
    assert len(writes) == 4


@pytest.mark.parametrize('target', ['student', 'faculty'])
def test_finalizing_winner_queues_both_cloud_decks_and_updates_without_poll_delay(client, monkeypatch, classroom, target):
    owner, _, school, slug = classroom
    with SessionFactory.begin() as store:
        store.get(User, owner).role = 'superadmin'
    sign_in(client, classroom)
    session_id = client.post('/api/session/create', json={'session_name': uuid4().hex}).json['session_id']
    if target == 'student':
        csv = b'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n123,Winner,Alex,9,Advisor,House,Clan\n'
        assert client.post('/api/csv/upload', data={'file': (io.BytesIO(csv), 'roster.csv')}).status_code == 200
        assert client.post('/api/record/clean', json={'input_value': '123'}).status_code == 200
        assert client.post(f'/api/session/{session_id}/draw/start').status_code == 200
        finalize = f'/api/session/{session_id}/draw/finalize'
    else:
        assert client.post('/api/record/faculty', json={'input_value': 'Alex Winner'}).status_code == 200
        assert client.post(f'/api/session/{session_id}/faculty/pick').status_code == 200
        finalize = f'/api/session/{session_id}/faculty/finalize'
    sent = []
    def upload(provider, token, binding, file_id, snapshot, theme):
        sent.append((provider, file_id, snapshot.get('winner_names', {})))
        return 'file-' + binding, 'https://example.test/' + binding
    monkeypatch.setattr(cloud, 'refresh_access', lambda *args: {'access_token': 'test-access'})
    monkeypatch.setattr(cloud, 'upsert_deck', upload)
    keys = [(school, owner, provider, 'dark') for provider in ('google', 'microsoft')]
    decks = [sync.bind_deck(*key, 'test-refresh') for key in keys]
    for deck in decks:
        assert sync.sync_deck(deck['id'], force=True)['status'] == 'ready'
    assert all(not winners for _, _, winners in sent)
    wake = threading.Event()
    monkeypatch.setitem(client.application.extensions, 'assembly_sync_wake', wake)
    assert client.post(finalize).status_code == 200
    assert wake.is_set()
    assert all(sync.get_deck(*key)['status'] == 'pending' for key in keys)
    sync.run_due_decks()  # No forced refresh, clock change or make_due call.
    assert all(sync.get_deck(*key)['status'] == 'ready' for key in keys)
    assert sent[2:] == [(provider, 'file-' + deck['id'], {target: 'Alex Winner'})
                        for provider, deck in zip(('google', 'microsoft'), decks)]


def test_consent_stays_with_initiating_teacher_school_and_origin(client, classroom, monkeypatch):
    _, _, _, slug = classroom
    sign_in(client, classroom)
    body = {'school_code': slug, 'provider': 'google', 'theme': 'light'}
    assert client.post(BASE + '/connect', json=body, headers={'Origin': 'https://another.example'}).status_code == 403
    assert client.get(BASE, headers={'Origin': 'https://another.example'}).status_code == 403
    other = 'other-' + slug
    with SessionFactory.begin() as store:
        store.add(School(id=other, name='Another school', slug=other))
    assert client.post(BASE + '/connect', json={**body, 'school_code': other}).status_code == 403
    args = begin(client, body)
    monkeypatch.setattr(cloud, 'exchange_code', lambda *a: pytest.fail('unexpected token exchange'))
    for provider, state in [('google', 'wrong'), ('microsoft', args['state'][0])]:
        response = client.get(BASE + '/callback/' + provider, query_string={'state': state, 'code': 'example'})
        location = urlsplit(response.location)
        assert response.status_code == 303 and location.path == '/export'
        assert parse_qs(location.query) == {
            'format': ['pptx' if provider == 'microsoft' else 'google-slides'], 'live_error': ['authorization'],
        }
    response = client.get(BASE + '/callback/google', query_string={'state': args['state'][0], 'error': 'access_denied'})
    location = urlsplit(response.location)
    assert location.path == '/export' and not location.fragment
    assert parse_qs(location.query) == {'format': ['google-slides'], 'live_error': ['authorization'],
                                        'school': [slug], 'theme': ['light']}
    args = begin(client, body)
    client.post('/api/auth/logout')
    assert 'live_error=' in client.get(BASE + '/callback/google', query_string={'state': args['state'][0], 'code': 'example'}).location
    assert client.get(BASE, query_string=body).json['links'] == {}


def test_missing_configuration_only_disables_that_provider(client, monkeypatch, classroom):
    monkeypatch.delenv('MICROSOFT_SLIDES_CLIENT_SECRET')
    assert client.get(BASE).json == {'providers': {'google': True, 'microsoft': False}, 'links': {}}
    sign_in(client, classroom)
    assert client.post(BASE + '/connect', json={'school_code': classroom[3], 'theme': 'light', 'provider': 'microsoft'}).status_code == 503


def test_failed_sync_diagnostics_are_visible_only_with_the_owners_deck(client, monkeypatch, classroom):
    owner, _, school, slug = classroom
    sign_in(client, classroom)
    secret = secrets.token_urlsafe()
    deck = sync.bind_deck(school, owner, 'microsoft', 'dark', secret)
    message = 'OneDrive did not confirm the saved file version. The presentation was kept.'
    def unavailable(*args):
        raise cloud.CloudDeckError(message)
    monkeypatch.setattr(cloud, 'refresh_access', unavailable)
    sync.sync_deck(deck['id'], force=True)
    response = client.get(BASE, query_string={'school_code': slug, 'theme': 'dark'})
    details = response.json['links']['microsoft']
    assert details['status'] == 'retry' and details['message'] == message
    assert details['attempts'] == 1 and details['next_check_at']
    assert details['last_synced_at'] is None and details['lease_until'] is None
    assert secret not in response.get_data(as_text=True)
    with client.application.test_client() as visitor:
        public = visitor.get(BASE, query_string={'school_code': slug, 'theme': 'dark'})
        assert public.json['links'] == {} and message not in public.get_data(as_text=True)


def test_school_code_lookup_lists_both_services_and_themes_only_for_the_owner(client, classroom):
    owner, _, school, slug = classroom
    sign_in(client, classroom)
    expected = []
    for provider, theme in [('google', 'dark'), ('microsoft', 'light')]:
        expected.append(sync.bind_deck(school, owner, provider, theme, 'private-refresh')['id'])
    another = create_user_record('other-' + uuid4().hex, 'password', 'Other member', school_id=school)
    other = sync.bind_deck(school, another.id, 'google', 'dark', 'another-private-refresh')
    response = client.get(BASE, query_string={'school_code': slug, 'theme': 'dark'})
    assert {d['id'] for d in response.json['connections']} == set(expected)
    assert other['id'] not in response.get_data(as_text=True)
    assert 'private-refresh' not in response.get_data(as_text=True)
    assert 'microsoft' not in response.json['links']  # The primary form remains theme-specific.


def test_manual_sync_queues_existing_deck_without_cloud_calls_or_redirect(client, monkeypatch, classroom):
    owner, _, school, slug = classroom
    sign_in(client, classroom)
    deck = sync.bind_deck(school, owner, 'microsoft', 'dark', 'private-refresh', school_label='Campus')
    lease = _now_utc() + timedelta(minutes=2)
    with SessionFactory.begin() as store:
        row = store.get(AssemblyDeck, deck['id'])
        row.status = 'retry'
        row.message = 'Previous failure'
        row.snapshot_hash = 'old-snapshot'
        row.next_check_at = _now_utc() + timedelta(hours=1)
        row.file_id, row.web_url = 'existing-file', 'https://example.test/existing'
        row.lease_owner, row.lease_until = 'existing-operation', lease
        original_grant = row.encrypted_refresh_token
    monkeypatch.setattr(cloud, 'refresh_access', lambda *args: pytest.fail('Sync requests must not contact the provider'))
    wake = threading.Event()
    monkeypatch.setitem(client.application.extensions, 'assembly_sync_wake', wake)
    response = client.post(BASE + '/sync', json={'school_code': slug, 'provider': 'microsoft', 'theme': 'dark'})
    assert response.status_code == 202 and 'Location' not in response.headers
    assert response.json['connection']['status'] == 'pending' and wake.is_set()
    assert response.json['connection']['url'] == 'https://example.test/existing'
    with SessionFactory() as store:
        row = store.get(AssemblyDeck, deck['id'])
        assert row.snapshot_hash is None and row.message is None
        assert row.next_check_at.replace(tzinfo=lease.tzinfo) <= _now_utc()
        assert row.lease_owner == 'existing-operation' and row.encrypted_refresh_token == original_grant
        assert row.file_id == 'existing-file' and row.school_label == 'Campus'
    assert client.post(BASE + '/sync', json={'school_code': slug, 'provider': 'google', 'theme': 'dark'}).status_code == 404
    assert client.post(BASE + '/sync', json={'school_code': slug, 'provider': 'microsoft', 'theme': 'dark'},
                       headers={'Origin': 'https://another.example'}).status_code == 403


@pytest.mark.parametrize('role', ['admin', 'superadmin'])
def test_admin_connections_include_school_owners_and_can_sync_without_crossing_schools(client, monkeypatch, classroom, role):
    owner, _, school, slug = classroom
    assert client.get('/api/admin/presentations/live').status_code == 401
    sign_in(client, classroom)
    assert client.get('/api/admin/presentations/live').status_code == 403
    another = create_user_record('other-' + uuid4().hex, 'password', 'Other member', school_id=school)
    own = sync.bind_deck(school, owner, 'google', 'dark', 'private-owner-refresh')
    shared = sync.bind_deck(school, another.id, 'microsoft', 'light', 'private-member-refresh')
    foreign_school = 'foreign-' + uuid4().hex
    with SessionFactory.begin() as store:
        store.add(School(id=foreign_school, name='Another school', slug=foreign_school))
        store.get(User, owner).role = role
    foreign = sync.bind_deck(foreign_school, another.id, 'google', 'dark', 'private-foreign-refresh')
    response = client.get('/api/admin/presentations/live', query_string={'school_id': foreign_school})
    assert {d['id'] for d in response.json['connections']} == {own['id'], shared['id']}
    assert next(d for d in response.json['connections'] if d['id'] == shared['id'])['owner_name'] == 'Other member'
    assert 'private-' not in response.get_data(as_text=True) and foreign['id'] not in response.get_data(as_text=True)
    monkeypatch.setattr(cloud, 'refresh_access', lambda *args: pytest.fail('Admin sync must be queued'))
    assert client.post('/api/admin/presentations/live/sync', json={'deck_id': shared['id']}).status_code == 202
    assert client.post('/api/admin/presentations/live/sync', json={'deck_id': foreign['id']}).status_code == 404
    assert client.post('/api/admin/presentations/live/sync', json={'deck_id': shared['id']},
                       headers={'Origin': 'https://another.example'}).status_code == 403
    assert client.get('/api/admin/presentations/live', headers={'Origin': 'https://another.example'}).status_code == 403


def test_manual_sync_does_not_reconnect_a_revoked_account(client, classroom):
    owner, _, school, slug = classroom
    sign_in(client, classroom)
    deck = sync.bind_deck(school, owner, 'google', 'dark', 'private-refresh')
    with SessionFactory.begin() as store:
        row = store.get(AssemblyDeck, deck['id'])
        row.status, row.encrypted_refresh_token = 'reconnect', None
    response = client.post(BASE + '/sync', json={'school_code': slug, 'provider': 'google', 'theme': 'dark'})
    assert response.status_code == 409 and response.json['code'] == 'RECONNECT_REQUIRED'
    assert sync.get_deck(school, owner, 'google', 'dark')['status'] == 'reconnect'


@pytest.mark.parametrize('configuration,expected', [(True, 'config'), (False, 'authorization')])
def test_microsoft_token_failure_return_identifies_configuration_without_binding_deck(client, monkeypatch, classroom, configuration, expected):
    sign_in(client, classroom)
    args = begin(client, {'school_code': classroom[3], 'theme': 'dark', 'provider': 'microsoft'})
    def reject(*args):
        raise cloud.CloudDeckError('private-error-message', configuration=configuration)
    monkeypatch.setattr(cloud, 'exchange_code', reject)
    response = client.get(BASE + '/callback/microsoft', query_string={'state': args['state'][0], 'code': 'private-code'})
    query = parse_qs(urlsplit(response.location).query)
    assert response.status_code == 303 and query['live_error'] == [expected]
    assert query['school'] == [classroom[3]] and query['format'] == ['pptx']
    assert 'private-' not in response.location
    assert client.get(BASE, query_string={'school_code': classroom[3], 'theme': 'dark'}).json['links'] == {}


def test_provider_denial_logs_only_known_category(client, monkeypatch, classroom, caplog):
    sign_in(client, classroom)
    body = {'school_code': classroom[3], 'theme': 'dark', 'provider': 'microsoft'}
    monkeypatch.setattr(cloud, 'exchange_code', lambda *args: pytest.fail('Provider denial must not exchange a token'))
    for provider_error, logged in [('access_denied', 'access_denied'), ('private-unknown-error', 'unknown')]:
        args = begin(client, body)
        response = client.get(BASE + '/callback/microsoft', query_string={
            'state': args['state'][0], 'error': provider_error, 'error_description': 'private-provider-description',
        })
        assert parse_qs(urlsplit(response.location).query)['live_error'] == ['authorization']
        assert f'provider=microsoft error={logged}' in caplog.text
    assert 'private-' not in caplog.text


def test_registered_name_lookup_respects_school_result_privacy(client, classroom):
    owner, _, school, slug = classroom
    options = {'school_code': slug, 'theme': 'dark'}
    assert client.get(BASE, query_string=options).json['school_name'] is None
    with SessionFactory.begin() as store:
        row = store.get(School, school)
        registered = row.name
        row.guest_privacy_enabled = 0
    assert client.get(BASE, query_string=options).json['school_name'] == registered
    with SessionFactory.begin() as store:
        store.add(Session(school_id=school, session_name='Private lunch', created_by=owner,
                          clean_number=7, status='active', is_public=0))
    assert client.get(BASE, query_string=options).json['school_name'] is None
    sign_in(client, classroom)
    assert client.get(BASE, query_string=options).json['school_name'] == registered
    for label in [4, 'bad\x00name', 'a' * 201]:
        response = client.post(BASE + '/connect', json={**options, 'provider': 'google', 'school_label': label})
        assert response.status_code == 400
    assert client.get(BASE, query_string=options).json['links'] == {}


def test_grants_require_a_private_signing_key_even_with_separate_encryption(client, monkeypatch, classroom):
    monkeypatch.setenv('SECRET_KEY', 'dev-only-change-me')
    assert client.get(BASE).json['providers'] == {'google': False, 'microsoft': False}


def test_preview_uses_its_own_callback_on_a_local_install(client, monkeypatch, classroom):
    monkeypatch.delenv('ASSEMBLY_SYNC_BASE_URL')
    monkeypatch.setenv('WEBSITE_PUBLIC_URL', 'https://goldenplate.ca')
    sign_in(client, classroom)
    args = begin(client, {'school_code': classroom[3], 'provider': 'google', 'theme': 'light'})
    assert args['redirect_uri'] == ['http://localhost' + BASE + '/callback/google']
