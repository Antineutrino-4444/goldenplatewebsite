"""Offline authorization and same-file updates for school-managed assembly decks."""
import base64
from hashlib import sha256
import json
import os
import re
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

import requests

from .assembly_powerpoint_merge import MergeError, mark_new_deck, merge_deck
from .presentation_exports import generate_deck


DRIVE = 'https://www.googleapis.com/drive/v3/files'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
ONEDRIVE = 'https://graph.microsoft.com/v1.0/me/drive'
SLIDES_MIME = 'application/vnd.google-apps.presentation'
PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
SCOPES = {
    'google': 'https://www.googleapis.com/auth/drive.file',
    'microsoft': 'https://graph.microsoft.com/Files.ReadWrite.AppFolder offline_access',
}


class CloudDeckError(Exception):
    """A displayable provider error. Never attach a raw token, URL, or HTTP response."""

    def __init__(self, message, *, reconnect=False):
        super().__init__(message)
        self.reconnect = reconnect


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


def _request(method, url, *, missing_ok=False, binary=False, **kwargs):
    try:
        response = requests.request(method, url, timeout=(5, 15), allow_redirects=False, **kwargs)
    except requests.RequestException:
        raise CloudDeckError('The presentation service could not be reached. Try again shortly.') from None
    if response.status_code == 404 and missing_ok:
        return None
    if 200 <= response.status_code < 300 and binary:
        return response.content
    if response.status_code in (409, 412, 423):
        raise CloudDeckError('The presentation changed or is being edited. The next sync will read the latest saved file.')
    try:
        result = response.json()
    except ValueError:
        result = {}
    if not isinstance(result, dict):
        result = {}
    if not 200 <= response.status_code < 300:
        error = result.get('error')
        if error in ('invalid_grant', 'interaction_required', 'consent_required', 'access_denied') or response.status_code == 401:
            raise CloudDeckError('Reconnect the cloud account to continue updating this presentation.', reconnect=True)
        if response.status_code == 404:
            raise CloudDeckError('The presentation is unavailable. Restore it or reconnect its original account.', reconnect=True)
        if response.status_code == 403 and isinstance(error, dict):
            reasons = {e.get('reason') for e in error.get('errors', []) if isinstance(e, dict)}
            if error.get('code') in ('accessDenied', 'Authorization_RequestDenied') or 'insufficientFilePermissions' in reasons:
                raise CloudDeckError('Reconnect an account with permission to edit this presentation.', reconnect=True)
        raise CloudDeckError('The presentation service could not complete the request. Check the connection and try again.')
    return result


def _tokens(provider, form):
    client_id, secret = _credentials(provider)
    if not client_id or not secret:
        raise CloudDeckError('This presentation connection has not been configured.')
    form.update(client_id=client_id, client_secret=secret)
    result = _request('POST', _oauth_endpoint(provider), data=form)
    if not isinstance(result.get('access_token'), str) or not result['access_token']:
        raise CloudDeckError('The cloud account could not authorize presentation updates.', reconnect=True)
    tokens = {'access_token': result['access_token']}
    if isinstance(result.get('refresh_token'), str) and result['refresh_token']:
        tokens['refresh_token'] = result['refresh_token']
    return tokens


def exchange_code(provider, redirect_uri, code, verifier):
    tokens = _tokens(provider, dict(grant_type='authorization_code', code=code, code_verifier=verifier,
                                     redirect_uri=redirect_uri))
    if 'refresh_token' not in tokens:
        raise CloudDeckError('Reconnect the cloud account and allow offline presentation updates.', reconnect=True)
    return tokens


def refresh_access(provider, refresh_token):
    return _tokens(provider, dict(grant_type='refresh_token', refresh_token=refresh_token))


def _google_deck(headers, binding, file_id, snapshot, blob):
    if not file_id:
        # A create may have succeeded even if the worker never received its response.
        # Recover that file before considering a second create. Google does not
        # support pre-generated Drive IDs when converting uploads into native Slides.
        matches = _request('GET', DRIVE, headers=headers, params={
            'q': f"trashed=false and mimeType='{SLIDES_MIME}' and appProperties has {{ key='gpAssembly' and value='{binding}' }}",
            'spaces': 'drive', 'fields': 'incompleteSearch,files(id)', 'orderBy': 'createdTime', 'pageSize': 1,
        })
        if not isinstance(matches.get('files'), list) or matches.get('incompleteSearch'):
            raise CloudDeckError('Google Drive could not check for an existing assembly presentation.')
        if matches['files']:
            file_id = matches['files'][0].get('id')
            if not file_id:
                raise CloudDeckError('Google Drive could not identify the existing presentation.')
    meta = {'mimeType': SLIDES_MIME}
    method, url = 'POST', UPLOAD
    if file_id:
        # Drive converts a PowerPoint upload on files.update into new contents
        # of the existing native Slides file, preserving the presentation ID.
        method, url = 'PATCH', UPLOAD + '/' + quote(file_id, safe='')
    else:
        meta.update(name=f"{snapshot['school_name']} — Golden Plate assembly", appProperties={'gpAssembly': binding})
    boundary = 'gp-' + uuid4().hex
    body = b''.join([
        f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode(),
        json.dumps(meta).encode(),
        f'\r\n--{boundary}\r\nContent-Type: {PPTX_MIME}\r\n\r\n'.encode(),
        blob, f'\r\n--{boundary}--\r\n'.encode(),
    ])
    result = _request(method, url, headers={**headers, 'Content-Type': 'multipart/related; boundary=' + boundary},
                      params={'uploadType': 'multipart', 'fields': 'id,mimeType,trashed'}, data=body)
    if result.get('trashed'):
        raise CloudDeckError('Restore the presentation in Google Drive and reconnect to resume updates.', reconnect=True)
    ident = result.get('id')
    if (not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident)
            or result.get('mimeType') != SLIDES_MIME or (file_id and ident != file_id)):
        raise CloudDeckError('Google Drive did not confirm the presentation update.')
    return ident, 'https://docs.google.com/presentation/d/' + ident + '/edit'


def _https_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


def _save_existing_powerpoint(headers, info, file_id, blob, snapshot):
    item = f'{ONEDRIVE}/items/{quote(file_id, safe="")}'
    etag = info.get('eTag')
    url = info.get('@microsoft.graph.downloadUrl')
    if (info.get('id') != file_id or not _https_url(url) or not isinstance(etag, str)
            or not re.fullmatch(r'"[^"\r\n]+"', etag)):
        raise CloudDeckError('OneDrive did not confirm the saved file version. The presentation was kept.')
    # Graph's short-lived download and upload URLs are already authenticated.
    # Keep the Graph OAuth grant on graph.microsoft.com.
    saved = _request('GET', url, binary=True)
    try:
        merged = merge_deck(saved, blob, snapshot)
    except MergeError as error:
        raise CloudDeckError(str(error)) from None
    # Graph documents If-Match on createUploadSession. The explicit conflict
    # behavior prevents a conflicting final transfer from replacing another file.
    conditional = {**headers, 'If-Match': etag}
    session = _request('POST', item + '/createUploadSession', headers=conditional,
                       json={'item': {'@microsoft.graph.conflictBehavior': 'fail'}})
    upload = session.get('uploadUrl')
    if not _https_url(upload):
        raise CloudDeckError('OneDrive did not return a secure upload session.')
    chunk_size = 10 * 1024 * 1024  # A multiple of the required 320 KiB.
    total = len(merged)
    for start in range(0, total, chunk_size):
        stop = min(start + chunk_size, total)
        if stop == total:
            latest = _request('GET', item, headers=headers, params={'$select': 'id,eTag'})
            if latest.get('id') != file_id or latest.get('eTag') != etag:
                raise CloudDeckError('The presentation changed while syncing. The next sync will use the newer copy.')
        result = _request('PUT', upload, headers={'Content-Range': f'bytes {start}-{stop - 1}/{total}',
                          'Content-Type': 'application/octet-stream', 'If-Match': etag}, data=merged[start:stop])
    return result


def _powerpoint_deck(headers, binding, file_id, blob, snapshot):
    metadata = {'$select': 'id,eTag,webUrl,@microsoft.graph.downloadUrl'}
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
    blob = generate_deck('assembly', theme, snapshot, platform=platform)
    if provider == 'google':
        return _google_deck(headers, binding, file_id, snapshot, blob)
    return _powerpoint_deck(headers, binding, file_id, blob, snapshot)
