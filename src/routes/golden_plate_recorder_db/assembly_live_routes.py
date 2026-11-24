"""Connect a school member's cloud account to a dedicated assembly deck."""
import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit

from flask import current_app, jsonify, redirect, request, session

from src.services import assembly_cloud as cloud
from . import recorder_bp, assembly_sync as sync
from .db import INTERSCHOOL_SCHOOL_ID
from .presentation_routes import _error, public_presentation_school_name, school_label_from
from .security import get_current_user
from .users import get_school_by_slug, get_school_by_id

PROVIDERS = ('google', 'microsoft')
FLOW_TTL = 600
PREFIX = '/api/resources/presentations/live'
logger = logging.getLogger(__name__)


def _site_origin():
    configured = os.environ.get('ASSEMBLY_SYNC_BASE_URL')
    host = urlsplit(request.host_url)
    if not configured and host.hostname not in ('localhost', '127.0.0.1', '::1'):
        configured = os.environ.get('WEBSITE_PUBLIC_URL') or 'https://goldenplate.ca'
    parts = urlsplit(configured) if configured else host
    local = parts.hostname in ('localhost', '127.0.0.1', '::1')
    if ((parts.scheme != 'https' and not (local and parts.scheme == 'http')) or not parts.hostname
            or parts.username is not None or parts.password is not None or parts.path not in ('/', '')
            or parts.query or parts.fragment):
        raise ValueError('Invalid assembly site origin')
    return f'{parts.scheme}://{parts.netloc}'


def _origin_error():
    origin = request.headers.get('Origin')
    if origin and origin != _site_origin():
        return _error('Open this request from the Golden Plate website.', 403)


def _json(data, status=200):
    return jsonify(data), status, {'Cache-Control': 'no-store'}


def _provider_enabled(provider):
    return cloud.provider_configured(provider) and sync.credentials_configured()


def _selection():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, None, None, _error('Choose a school and presentation.', 400)
    provider, theme, code = data.get('provider'), data.get('theme'), data.get('school_code')
    if provider not in PROVIDERS or theme not in ('light', 'dark') or not isinstance(code, str) or not code.strip():
        return None, None, None, _error('Choose a school, provider and theme.', 400)
    school = get_school_by_slug(code)
    if not school or school.status != 'active' or school.id == INTERSCHOOL_SCHOOL_ID:
        return None, None, None, _error('No active school matches this code.', 404)
    return school, provider, theme, None


def _owner_error(actor, school, *, disconnect=False):
    if not actor:
        return _error('Sign in to your school to connect an assembly presentation.', 401, 'SCHOOL_LOGIN_REQUIRED')
    if actor['school_id'] != school.id or actor['role'] not in ('user', 'admin', 'superadmin'):
        return _error('Use an account belonging to this school.', 403, 'WRONG_SCHOOL_ACCOUNT')
    if actor['email_required'] and not disconnect:
        return _error('Verify your account email to connect your presentation.', 403, 'ACCOUNT_EMAIL_REQUIRED')


def _proof(state):
    # Keep the PKCE verifier out of the browser cookie and the authorization URL.
    key = current_app.secret_key
    if isinstance(key, str):
        key = key.encode()
    digest = hmac.digest(key, b'assembly-oauth-pkce:' + state.encode('ascii'), hashlib.sha256)
    return base64.urlsafe_b64encode(digest).decode().rstrip('=')


def _return_to_export(flow, provider, error):
    options = {'format': 'pptx' if provider == 'microsoft' else 'google-slides', 'live_error': error}
    if flow:
        options.update(school=flow['school_code'], theme=flow['theme'])
        if 'school_label' in flow:
            options['school_label'] = flow['school_label']
    return _redirect('/export?' + urlencode(options))


def _redirect(url):
    response = redirect(url, 303)
    response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
    return response


@recorder_bp.get('/resources/presentations/live')
def assembly_live_links():
    denied = _origin_error()
    if denied:
        return denied
    result = {'providers': {p: _provider_enabled(p) for p in PROVIDERS}, 'links': {}}
    code = request.args.get('school_code', '').strip()
    if code:
        theme = request.args.get('theme', 'light')
        if theme not in ('light', 'dark'):
            return _error('Choose a presentation theme.', 400)
        actor = get_current_user()
        school = get_school_by_slug(code)
        result['school_name'] = None
        if not school or school.status != 'active' or school.id == INTERSCHOOL_SCHOOL_ID:
            return _json(result)
        owns_school = actor and not _owner_error(actor, school, disconnect=True)
        result['connections'] = []
        if owns_school and not actor['email_required']:
            result['school_name'] = school.name
        elif school.guest_privacy_enabled == 0:
            result['school_name'] = public_presentation_school_name(school.id)
        if owns_school:
            for deck in sync.list_decks(school.id, actor['id']):
                if not actor['email_required']:
                    result['connections'].append(deck)
                if deck['theme'] == theme:
                    result['links'][deck['provider']] = {
                        'url': None if actor['email_required'] else deck['url'], 'status': deck['status'],
                        'school_label': deck['school_label'],
                        **{field: deck[field] for field in ('message', 'last_synced_at', 'next_check_at',
                                                          'lease_until', 'attempts')},
                    }
    return _json(result)


def _sync_response(deck):
    if not deck:
        return _error('No connected presentation was found.', 404)
    if deck['status'] == 'reconnect':
        return _error('The connection owner needs to reconnect this cloud account.', 409, 'RECONNECT_REQUIRED')
    if not _provider_enabled(deck['provider']):
        return _error('Automatic updates for this provider are unavailable.', 503)
    return None


@recorder_bp.post('/resources/presentations/live/sync')
def request_assembly_sync():
    denied = _origin_error()
    if denied:
        return denied
    school, provider, theme, error = _selection()
    if error:
        return error
    actor = get_current_user()
    denied = _owner_error(actor, school)
    if denied:
        return denied
    deck = sync.get_deck(school.id, actor['id'], provider, theme)
    denied = _sync_response(deck)
    if denied:
        return denied
    deck = sync.request_deck_sync(deck['id'], school.id, owner_id=actor['id'])
    denied = _sync_response(deck)
    return denied if denied else _json({'connection': deck}, 202)


def _school_admin():
    actor = get_current_user()
    if not actor:
        return None, _error('Sign in to manage connected presentations.', 401)
    if actor['role'] not in ('admin', 'superadmin'):
        return None, _error('School admin access required.', 403)
    school = get_school_by_id(actor['school_id'])
    if not school or school.status != 'active' or school.id == INTERSCHOOL_SCHOOL_ID:
        return None, _error('An active school is required.', 403)
    return actor, None


@recorder_bp.get('/admin/presentations/live')
def admin_assembly_connections():
    denied = _origin_error()
    if denied:
        return denied
    actor, denied = _school_admin()
    if denied:
        return denied
    return _json({'providers': {p: _provider_enabled(p) for p in PROVIDERS},
                  'connections': sync.list_school_decks(actor['school_id'])})


@recorder_bp.post('/admin/presentations/live/sync')
def admin_request_assembly_sync():
    denied = _origin_error()
    if denied:
        return denied
    actor, denied = _school_admin()
    if denied:
        return denied
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('deck_id'), str):
        return _error('Choose a connected presentation.', 400)
    deck = next((d for d in sync.list_school_decks(actor['school_id']) if d['id'] == data['deck_id']), None)
    denied = _sync_response(deck)
    if denied:
        return denied
    deck = sync.request_deck_sync(deck['id'], actor['school_id'])
    denied = _sync_response(deck)
    return denied if denied else _json({'connection': deck}, 202)


@recorder_bp.post('/resources/presentations/live/connect')
def connect_assembly_deck():
    denied = _origin_error()
    if denied:
        return denied
    school, provider, theme, error = _selection()
    if error:
        return error
    actor = get_current_user()
    denied = _owner_error(actor, school)
    if denied:
        return denied
    if not _provider_enabled(provider):
        return _error('Automatic updates for this provider are not configured on this site.', 503)

    data = request.get_json()
    try:
        label = school_label_from(data)
    except ValueError as error:
        return _error(str(error), 400)
    key = (school.id, actor['id'], provider, theme)
    deck = sync.set_school_label(*key, label) if 'school_label' in data else sync.get_deck(*key)
    if deck and deck['status'] != 'reconnect':
        deck = sync.sync_deck(deck['id'], force=True)
        if deck and deck['status'] != 'reconnect':
            payload = {field: deck[field] for field in ('status', 'url', 'school_label')}
            return _json(payload, 200 if deck['url'] and deck['status'] == 'ready' else 202)

    state = secrets.token_urlsafe(32)
    callback = _site_origin() + PREFIX + '/callback/' + provider
    session['assembly_connect_' + provider] = {
        'nonce': state, 'started': int(time.time()), 'owner': actor['id'], 'school_id': school.id,
        'school_code': school.slug, 'theme': theme, 'callback': callback,
        **({'school_label': label or ''} if 'school_label' in data else {}),
    }
    url = cloud.authorization_url(provider, callback, state, _proof(state))
    return _json({'authorization_url': url})


@recorder_bp.get('/resources/presentations/live/callback/<provider>')
def assembly_oauth_callback(provider):
    if provider not in PROVIDERS:
        return _error('Unknown presentation provider.', 404)
    key = 'assembly_connect_' + provider
    flow = session.get(key)
    state = request.args.get('state', '')
    if (not flow or not state.isascii() or not secrets.compare_digest(flow['nonce'], state)
            or not 0 <= time.time() - flow['started'] < FLOW_TTL):
        return _return_to_export(None, provider, 'authorization')
    session.pop(key, None)
    actor = get_current_user()
    school = get_school_by_slug(flow['school_code'])
    if (not school or school.id != flow['school_id'] or school.status != 'active' or not actor
            or actor['id'] != flow['owner'] or _owner_error(actor, school)):
        return _return_to_export(flow, provider, 'access')
    code = request.args.get('code')
    if request.args.get('error') or not code:
        provider_error = request.args.get('error')
        category = provider_error if provider_error in cloud.OAUTH_ERRORS else 'unknown' if provider_error else 'missing_code'
        logger.warning('Assembly OAuth provider returned no authorization code (provider=%s error=%s)', provider, category)
        return _return_to_export(flow, provider, 'authorization')
    if not _provider_enabled(provider):
        return _return_to_export(flow, provider, 'config')
    try:
        tokens = cloud.exchange_code(provider, flow['callback'], code, _proof(state))
    except cloud.CloudDeckError as error:
        return _return_to_export(flow, provider, 'config' if error.configuration else 'authorization')
    options = {'school_label': flow['school_label'] or None} if 'school_label' in flow else {}
    deck = sync.bind_deck(school.id, actor['id'], provider, flow['theme'], tokens['refresh_token'], **options)
    deck = sync.sync_deck(deck['id'], force=True)
    if deck and deck['status'] == 'ready' and deck['url']:
        return _redirect(deck['url'])
    return _return_to_export(flow, provider, 'sync')


@recorder_bp.delete('/resources/presentations/live')
def disconnect_assembly_deck():
    denied = _origin_error()
    if denied:
        return denied
    school, provider, theme, error = _selection()
    if error:
        return error
    actor = get_current_user()
    denied = _owner_error(actor, school, disconnect=True)
    if denied:
        return denied
    session.pop('assembly_connect_' + provider, None)
    sync.disconnect_deck(school.id, actor['id'], provider, theme)
    return _json({'ok': True})
