"""Exercise the teacher flow through consent, unattended refresh and disconnect."""
import hashlib
import base64
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from src.routes.golden_plate_recorder_db import assembly_sync as sync
from src.routes.golden_plate_recorder_db.db import AssemblyDeck, School, Session, SessionFactory, _now_utc, db_session
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
    assert listing['links'][provider] == {'url': response.location, 'status': 'ready', 'school_label': 'Student Council'}
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
