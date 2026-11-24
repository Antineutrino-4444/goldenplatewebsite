"""Offline authorization and same-file updates for school-managed assembly decks."""
import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import logging
import os
import re
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

import requests

from .assembly_google_merge import GoogleMergeError, initialize_native_pages, notes_after_creation, plan_update
from .assembly_powerpoint_merge import MergeError, mark_new_deck, merge_deck
from .presentation_exports import generate_deck


DRIVE = 'https://www.googleapis.com/drive/v3/files'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
GOOGLE_SLIDES = 'https://slides.googleapis.com/v1/presentations/'
ONEDRIVE = 'https://graph.microsoft.com/v1.0/me/drive'
SLIDES_MIME = 'application/vnd.google-apps.presentation'
PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
SCOPES = {
    'google': 'https://www.googleapis.com/auth/drive.file',
    'microsoft': 'https://graph.microsoft.com/Files.ReadWrite.AppFolder offline_access',
}
logger = logging.getLogger(__name__)
OAUTH_ERRORS = frozenset(('invalid_client', 'unauthorized_client', 'invalid_scope', 'invalid_request',
                          'invalid_grant', 'interaction_required', 'consent_required', 'access_denied',
                          'temporarily_unavailable', 'server_error'))


def _token_provider(url):
    if url == 'https://oauth2.googleapis.com/token':
        return 'google'
    if re.fullmatch(r'https://login\.microsoftonline\.com/[a-zA-Z0-9.-]+/oauth2/v2\.0/token', url):
        return 'microsoft'


def _log_token_failure(provider, status, result):
    # Log machine categories only: provider descriptions can contain credentials,
    # account details or request URLs. Unknown strings must not reach the log.
    error = result.get('error')
    category = error if isinstance(error, str) and error in OAUTH_ERRORS else 'unknown'
    codes = result.get('error_codes')
    codes = [n for n in codes if type(n) is int and 0 <= n <= 999999999][:5] if isinstance(codes, list) else []
    logger.warning('Assembly OAuth token request failed (provider=%s status=%s error=%s codes=%s)',
                   provider, status, category, codes)


class CloudDeckError(Exception):
    """A displayable provider error. Never attach a raw token, URL, or HTTP response."""

    def __init__(self, message, *, reconnect=False, configuration=False):
        super().__init__(message)
        self.reconnect = reconnect
        self.configuration = configuration


def _credentials(provider):
    if provider not in SCOPES:
        raise CloudDeckError('Choose Google Slides or PowerPoint.')
    prefix = provider.upper() + '_SLIDES_CLIENT_'
    return os.getenv(prefix + 'ID', '').strip(), os.getenv(prefix + 'SECRET', '').strip()


def provider_configured(provider):
    return provider in SCOPES and all(_credentials(provider))


def _oauth_endpoint(provider, authorize=False):
    if provider == 'google':
        return 'https://accounts.google.com/o/oauth2/v2/auth' if authorize else 'https://oauth2.googleapis.com/token'
    tenant = os.getenv('MICROSOFT_SLIDES_TENANT', 'common').strip() or 'common'
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', tenant) or tenant in ('.', '..'):
        raise CloudDeckError('Check the Microsoft application tenant setting.')
    return f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/' + ('authorize' if authorize else 'token')


def authorization_url(provider, redirect_uri, state, verifier):
    client_id, secret = _credentials(provider)
    if not client_id or not secret:
        raise CloudDeckError('This presentation connection has not been configured.')
    challenge = base64.urlsafe_b64encode(sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    params = dict(client_id=client_id, redirect_uri=redirect_uri, state=state, scope=SCOPES[provider],
                  response_type='code', code_challenge=challenge, code_challenge_method='S256')
    if provider == 'google':
        params.update(access_type='offline', prompt='consent select_account')
    else:
        params.update(response_mode='query', prompt='select_account')
    return _oauth_endpoint(provider, authorize=True) + '?' + urlencode(params)


def _request(method, url, *, missing_ok=False, binary=False, download_redirect=False, **kwargs):
    token_provider = _token_provider(url)
    try:
        timeout = kwargs.pop('timeout', (5, 15))
        response = requests.request(method, url, timeout=timeout, allow_redirects=False, **kwargs)
    except requests.RequestException:
        if token_provider:
            _log_token_failure(token_provider, 'network', {})
        raise CloudDeckError('The presentation service could not be reached. Try again shortly.') from None
    if response.status_code == 404 and missing_ok:
        return None
    if response.status_code == 302 and download_redirect:
        return response.headers.get('Location')
    if 200 <= response.status_code < 300 and binary:
        return response.content
    if response.status_code == 412:
        raise CloudDeckError('The presentation changed since it was read. The next sync will read the latest saved file.')
    if response.status_code == 423:
        raise CloudDeckError('The presentation is locked for editing. Close its editors, then try syncing again.')
    try:
        result = response.json()
    except ValueError:
        result = {}
    if not isinstance(result, dict):
        result = {}
    if not 200 <= response.status_code < 300:
        error = result.get('error')
        if response.status_code == 409:
            if isinstance(error, dict) and error.get('code') == 'nameAlreadyExists':
                raise CloudDeckError('The presentation service reported a file-name conflict. The saved presentation was kept.')
            raise CloudDeckError('The presentation service reported an update conflict. The next sync will read the latest saved file.')
        if token_provider:
            _log_token_failure(token_provider, response.status_code, result)
            if error in ('invalid_client', 'unauthorized_client', 'invalid_scope'):
                raise CloudDeckError('The cloud presentation app credentials or permissions need to be checked by the site administrator.',
                                     configuration=True)
        if error in ('invalid_grant', 'interaction_required', 'consent_required', 'access_denied') or response.status_code == 401:
            raise CloudDeckError('Reconnect the cloud account to continue updating this presentation.', reconnect=True)
        if response.status_code == 404:
            raise CloudDeckError('The presentation is unavailable. Restore it or reconnect its original account.', reconnect=True)
        if response.status_code == 403 and isinstance(error, dict):
            reasons = {e.get('reason') for e in error.get('errors', []) if isinstance(e, dict)}
            details = error.get('details', [])
            if 'accessNotConfigured' in reasons or any(d.get('reason') == 'SERVICE_DISABLED' for d in details if isinstance(d, dict)):
                raise CloudDeckError('Enable the Google Drive API and Google Slides API in the connected OAuth project, then retry.',
                                     configuration=True)
            if error.get('code') in ('accessDenied', 'Authorization_RequestDenied') or 'insufficientFilePermissions' in reasons:
                raise CloudDeckError('Reconnect an account with permission to edit this presentation.', reconnect=True)
        if response.status_code == 400 and isinstance(error, dict) and 'revision' in str(error.get('message', '')).lower():
            raise CloudDeckError('The presentation changed while syncing. The next sync will read the latest saved copy.')
        if response.status_code == 429:
            raise CloudDeckError('The presentation service reached its rate limit. The next sync will retry.')
        raise CloudDeckError('The presentation service could not complete the request. Check the connection and try again.')
    return result


def _tokens(provider, form):
    client_id, secret = _credentials(provider)
    if not client_id or not secret:
        raise CloudDeckError('This presentation connection has not been configured.')
    form.update(client_id=client_id, client_secret=secret)
    result = _request('POST', _oauth_endpoint(provider), data=form)
    if not isinstance(result.get('access_token'), str) or not result['access_token']:
        logger.warning('Assembly OAuth token response did not include an access token (provider=%s)', provider)
        raise CloudDeckError('The cloud account could not authorize presentation updates.', reconnect=True)
    tokens = {'access_token': result['access_token']}
    if isinstance(result.get('refresh_token'), str) and result['refresh_token']:
        tokens['refresh_token'] = result['refresh_token']
    return tokens


def exchange_code(provider, redirect_uri, code, verifier):
    tokens = _tokens(provider, dict(grant_type='authorization_code', code=code, code_verifier=verifier,
                                     redirect_uri=redirect_uri))
    if 'refresh_token' not in tokens:
        logger.warning('Assembly OAuth connection did not receive an offline grant (provider=%s)', provider)
        raise CloudDeckError('Reconnect the cloud account and allow offline presentation updates.', reconnect=True)
    return tokens


def refresh_access(provider, refresh_token):
    return _tokens(provider, dict(grant_type='refresh_token', refresh_token=refresh_token))


def _import_google(headers, meta, blob, *, file_id=None):
    boundary = 'gp-' + uuid4().hex
    body = b''.join([
        f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode(),
        json.dumps({**meta, 'mimeType': SLIDES_MIME}).encode(),
        f'\r\n--{boundary}\r\nContent-Type: {PPTX_MIME}\r\n\r\n'.encode(),
        blob, f'\r\n--{boundary}--\r\n'.encode(),
    ])
    endpoint = UPLOAD + '/' + quote(file_id, safe='') if file_id else UPLOAD
    params = {'uploadType': 'multipart', 'fields': 'id,mimeType,trashed'}
    if not file_id:
        params['ignoreDefaultVisibility'] = 'true'
    result = _request('PATCH' if file_id else 'POST', endpoint,
                      headers={**headers, 'Content-Type': 'multipart/related; boundary=' + boundary}, params=params,
                      data=body, timeout=(5, 75))
    ident = result.get('id')
    if (not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident)
            or (file_id and ident != file_id)
            or result.get('mimeType') != SLIDES_MIME or result.get('trashed')):
        raise CloudDeckError('Google Drive did not confirm the native presentation import.')
    return ident


def _file_matches(headers, key, binding, *, older_than=None):
    query = (f"trashed=false and mimeType='{SLIDES_MIME}' and "
             f"appProperties has {{ key='{key}' and value='{binding}' }}")
    if older_than:
        query += f" and createdTime < '{older_than}'"
    response = _request('GET', DRIVE, headers=headers, params={
        'q': query, 'spaces': 'drive', 'fields': 'incompleteSearch,files(id)', 'orderBy': 'createdTime',
        'pageSize': 100 if older_than else 1,
    })
    if not isinstance(response.get('files'), list) or response.get('incompleteSearch'):
        raise CloudDeckError('Google Drive could not check the saved assembly files.')
    ids = [entry.get('id') for entry in response['files']]
    if not all(isinstance(ident, str) and re.fullmatch(r'[A-Za-z0-9_-]+', ident) for ident in ids):
        raise CloudDeckError('Google Drive could not identify a saved assembly file.')
    return ids


def _delete_scratch(headers, ident):
    # Only a private conversion created by this binding is passed here. A
    # direct delete avoids storing another copy of student data in Drive Trash.
    _request('DELETE', DRIVE + '/' + quote(ident, safe=''), headers=headers, missing_ok=True)


def _google_write(headers, url, operations):
    if not operations:
        return
    # Automatic results take precedence over edits made since the last read.
    _request('POST', url + ':batchUpdate', headers=headers, timeout=(5, 75), json={'requests': operations})


def _replace_google(headers, file_id, blob):
    # Drive's conversion update replaces the contents of this native file while
    # retaining its ID, sharing settings, name and assembly binding metadata.
    _import_google(headers, {}, blob, file_id=file_id)
    url = GOOGLE_SLIDES + quote(file_id, safe='')
    saved = _request('GET', url, headers=headers)
    try:
        _google_write(headers, url, initialize_native_pages(saved))
    except GoogleMergeError as error:
        raise CloudDeckError(str(error)) from None


def _refresh_google(headers, binding, file_id, blob):
    url = GOOGLE_SLIDES + quote(file_id, safe='')
    scratch = None
    try:
        saved = _request('GET', url, headers=headers)
        # Reap only abandoned private conversions belonging to this binding.
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        for orphan in _file_matches(headers, 'gpAssemblyScratch', binding, older_than=cutoff):
            if orphan != file_id:
                _delete_scratch(headers, orphan)
        scratch = _import_google(headers, {'name': 'Golden Plate assembly refresh',
                                           'appProperties': {'gpAssemblyScratch': binding}}, blob)
        if scratch == file_id:
            raise CloudDeckError('Google returned an invalid temporary presentation ID.')
        fresh = _request('GET', GOOGLE_SLIDES + quote(scratch, safe=''), headers=headers)
        operations, pending_notes = plan_update(saved, fresh)
        _google_write(headers, url, operations)
        if pending_notes:
            saved = _request('GET', url, headers=headers)
            _google_write(headers, url, notes_after_creation(saved, pending_notes))
    except GoogleMergeError:
        _replace_google(headers, file_id, blob)
    except CloudDeckError as error:
        if error.reconnect or error.configuration:
            raise
        _replace_google(headers, file_id, blob)
    finally:
        if scratch and scratch != file_id:
            _delete_scratch(headers, scratch)


def _google_deck(headers, binding, file_id, snapshot, blob):
    if not file_id:
        # A conversion can succeed after the create request times out. Search
        # the binding before creating again; converted files cannot reserve IDs.
        matches = _file_matches(headers, 'gpAssembly', binding)
        file_id = matches[0] if matches else None
    if not file_id:
        file_id = _import_google(headers, {
            'name': f"{snapshot['school_name']} — Golden Plate assembly",
            'appProperties': {'gpAssembly': binding},
        }, blob)
        url = GOOGLE_SLIDES + quote(file_id, safe='')
        saved = _request('GET', url, headers=headers)
        try:
            _google_write(headers, url, initialize_native_pages(saved))
        except GoogleMergeError as error:
            raise CloudDeckError(str(error)) from None
    else:
        url = GOOGLE_SLIDES + quote(file_id, safe='')
        info = _request('GET', DRIVE + '/' + quote(file_id, safe=''), headers=headers,
                        params={'fields': 'id,mimeType,trashed,appProperties', 'supportsAllDrives': 'true'})
        if info.get('trashed'):
            raise CloudDeckError('Restore the presentation in Google Drive to resume updates.', reconnect=True)
        if (info.get('id') != file_id or info.get('mimeType') != SLIDES_MIME
                or info.get('appProperties', {}).get('gpAssembly') != binding):
            raise CloudDeckError('Google did not confirm this assembly connection. The presentation was kept.')
        _refresh_google(headers, binding, file_id, blob)
    return file_id, 'https://docs.google.com/presentation/d/' + file_id + '/edit'


def _https_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def _download_existing_powerpoint(headers, item, info):
    url = info.get('@microsoft.graph.downloadUrl')
    if url is None or url == '':
        # Some driveItem responses omit the annotation. Graph's /content API
        # provides the same short-lived URL in a 302 Location header. Read it
        # explicitly so the OAuth grant never follows the redirect to storage.
        download = _request('GET', item + '/content', headers=headers,
                            binary=True, download_redirect=True)
        if isinstance(download, bytes):
            return download
        url = download
    if not _https_url(url):
        raise CloudDeckError('OneDrive did not return a secure download link for the saved presentation. The presentation was kept.')
    return _request('GET', url, binary=True)


def _save_existing_powerpoint(headers, info, file_id, blob, snapshot):
    item = f'{ONEDRIVE}/items/{quote(file_id, safe="")}'
    if info.get('id') != file_id:
        raise CloudDeckError('OneDrive did not confirm the original presentation identity. The presentation was kept.')
    # Graph's short-lived download and upload URLs are already authenticated.
    # Keep the Graph OAuth grant on graph.microsoft.com.
    try:
        saved = _download_existing_powerpoint(headers, item, info)
        merged = merge_deck(saved, blob, snapshot)
    except MergeError:
        merged = mark_new_deck(blob, snapshot)
    except CloudDeckError as error:
        if error.reconnect or error.configuration:
            raise
        merged = mark_new_deck(blob, snapshot)
    # Automatic results take precedence over edits made during this upload.
    # Preserve additions when merging works, otherwise replace with a fresh deck.
    # Do not send version conditions or recheck an eTag before committing.
    session = _request('POST', item + '/createUploadSession', headers=headers,
                       json={'item': {'@microsoft.graph.conflictBehavior': 'replace'}})
    upload = session.get('uploadUrl')
    if not _https_url(upload):
        raise CloudDeckError('OneDrive did not return a secure upload session.')
    chunk_size = 10 * 1024 * 1024  # A multiple of the required 320 KiB.
    total = len(merged)
    for start in range(0, total, chunk_size):
        stop = min(start + chunk_size, total)
        result = _request('PUT', upload, headers={'Content-Range': f'bytes {start}-{stop - 1}/{total}',
                          'Content-Type': 'application/octet-stream'}, data=merged[start:stop])
    return result


def _powerpoint_deck(headers, binding, file_id, blob, snapshot):
    metadata = {'$select': 'id,webUrl,@microsoft.graph.downloadUrl'}
    if file_id:
        item = f'{ONEDRIVE}/items/{quote(file_id, safe="")}'
        info = _request('GET', item, headers=headers, params=metadata)
    else:
        folder = _request('GET', ONEDRIVE + '/special/approot', headers=headers, params={'$select': 'id'})
        if not folder.get('id'):
            raise CloudDeckError('OneDrive did not return the assembly folder.')
        filename = f'Golden Plate assembly {binding[:20]}.pptx'
        item = f'{ONEDRIVE}/items/{quote(folder["id"], safe="")}:/{quote(filename)}'
        info = _request('GET', item, headers=headers, params=metadata, missing_ok=True)
        if info is not None:
            file_id = info.get('id')
            if not file_id:
                raise CloudDeckError('OneDrive could not identify the existing presentation.')
    if info is None:
        result = _request('PUT', item + ':/content',
                          headers={**headers, 'Content-Type': PPTX_MIME, 'If-None-Match': '*'},
                          params={'@microsoft.graph.conflictBehavior': 'fail'}, data=mark_new_deck(blob, snapshot))
    else:
        result = _save_existing_powerpoint(headers, info, file_id, blob, snapshot)
    ident, link = result.get('id'), result.get('webUrl')
    if not isinstance(ident, str) or not ident or (file_id and ident != file_id):
        raise CloudDeckError('OneDrive did not confirm the presentation update.')
    if not link and info:
        link = info.get('webUrl')
    if not link:
        # Some upload responses omit the browser URL from their driveItem.
        info = _request('GET', f'{ONEDRIVE}/items/{quote(ident, safe="")}', headers=headers,
                        params={'$select': 'webUrl'})
        link = info.get('webUrl')
    if not isinstance(link, str) or urlsplit(link).scheme != 'https' or not urlsplit(link).hostname:
        raise CloudDeckError('OneDrive did not return the presentation link.')
    return ident, link


def upsert_deck(provider, access_token, binding_key, file_id, snapshot, theme):
    """Create or replace app-managed content, retaining the same provider file ID."""
    if provider not in SCOPES:
        raise CloudDeckError('Choose Google Slides or PowerPoint.')
    binding = sha256(str(binding_key).encode()).hexdigest()
    headers = {'Authorization': 'Bearer ' + access_token}
    platform = 'google-slides' if provider == 'google' else 'powerpoint'
    export_snapshot = {**snapshot, 'seed_google_session_slides': True} if provider == 'google' else snapshot
    blob = generate_deck('assembly', theme, export_snapshot, platform=platform)
    if provider == 'google':
        return _google_deck(headers, binding, file_id, snapshot, blob)
    return _powerpoint_deck(headers, binding, file_id, blob, snapshot)
