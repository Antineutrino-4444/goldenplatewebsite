import base64
from hashlib import sha256
import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from assembly_google_fixtures import native_deck, registered
from src.services import assembly_cloud as cloud


@pytest.fixture
def api(monkeypatch):
    calls, replies = [], []

    def send(method, url, **kwargs):
        calls.append((method, url, kwargs))
        assert kwargs['allow_redirects'] is False
        status, body = replies.pop(0)
        response = requests.Response()
        response.status_code = status
        response._content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return response

    monkeypatch.setattr(cloud.requests, 'request', send)
    return calls, replies


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_offline_code_flow_and_refresh(monkeypatch, api, provider):
    calls, replies = api
    var = provider.upper() + '_SLIDES_CLIENT_'
    monkeypatch.delenv(var + 'SECRET', raising=False)
    assert not cloud.provider_configured(provider)
    monkeypatch.setenv(var + 'ID', 'test-client')
    monkeypatch.setenv(var + 'SECRET', 'fixture-secret')
    assert cloud.provider_configured(provider)
    redirect = 'https://school.example/auth/callback'
    verifier = 'v' * 64
    url = cloud.authorization_url(provider, redirect, 'state-value', verifier)
    params = parse_qs(urlsplit(url).query)
    assert params['client_id'] == ['test-client']
    assert params['redirect_uri'] == [redirect]
    assert params['state'] == ['state-value']
    assert params['code_challenge'] == [base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b'=').decode()]
    assert params['code_challenge_method'] == ['S256']
    assert verifier not in url and 'fixture-secret' not in url
    if provider == 'google':
        assert params['scope'] == ['https://www.googleapis.com/auth/drive.file']
        assert params['access_type'] == ['offline']
    else:
        assert set(params['scope'][0].split()) == {'https://graph.microsoft.com/Files.ReadWrite.AppFolder', 'offline_access'}
    replies.extend([(200, {'access_token': 'access', 'refresh_token': 'first'}),
                    (200, {'access_token': 'next', 'refresh_token': 'second'}),
                    (200, {'access_token': 'last'})])
    assert cloud.exchange_code(provider, redirect, 'code', verifier) == {'access_token': 'access', 'refresh_token': 'first'}
    form = calls[0][2]['data']
    assert form['code'] == 'code' and form['code_verifier'] == verifier and form['redirect_uri'] == redirect
    assert form['client_secret'] == 'fixture-secret'
    assert cloud.refresh_access(provider, 'first') == {'access_token': 'next', 'refresh_token': 'second'}
    assert cloud.refresh_access(provider, 'second') == {'access_token': 'last'}
    assert calls[1][2]['data']['grant_type'] == 'refresh_token'
    assert calls[2][2]['data']['refresh_token'] == 'second'


def test_revocation_and_missing_offline_grant_are_safe(monkeypatch, api):
    _, replies = api
    monkeypatch.setenv('GOOGLE_SLIDES_CLIENT_ID', 'test')
    monkeypatch.setenv('GOOGLE_SLIDES_CLIENT_SECRET', 'test-secret')
    replies.extend([(400, {'error': 'invalid_grant', 'error_description': 'sensitive-provider-detail'}),
                    (200, {'access_token': 'sensitive-provider-detail'})])
    with pytest.raises(cloud.CloudDeckError) as revoked:
        cloud.refresh_access('google', 'old-refresh')
    with pytest.raises(cloud.CloudDeckError) as no_offline:
        cloud.exchange_code('google', 'https://example.test/cb', 'code', 'verifier')
    for err in (revoked.value, no_offline.value):
        assert err.reconnect and 'sensitive-provider-detail' not in str(err)


@pytest.fixture
def upload(monkeypatch):
    def generate(kind, theme, snapshot, platform):
        assert kind == 'assembly' and theme == 'dark'
        return f"{platform} lunch {snapshot['count']}".encode()

    monkeypatch.setattr(cloud, 'generate_deck', generate)
    monkeypatch.setattr(cloud, 'mark_new_deck', lambda blob, snapshot: b'marked ' + blob)
    monkeypatch.setattr(cloud, 'merge_deck', lambda saved, fresh, snapshot: saved + b' + ' + fresh)

    def sync(provider, file_id=None, count=120):
        return cloud.upsert_deck(provider, 'test-access', 'stable-key', file_id,
                                 {'school_name': 'School', 'count': count}, 'dark')
    return sync


def _google_file(ident='existing'):
    return {'id': ident, 'mimeType': cloud.SLIDES_MIME,
            'appProperties': {'gpAssembly': sha256(b'stable-key').hexdigest()}}


def test_google_creates_native_then_updates_original_file_and_link(api, upload):
    calls, replies = api
    original = _google_file()
    url = cloud.GOOGLE_SLIDES + 'existing'
    replies.extend([(200, {'files': []}), (200, original), (200, native_deck()), (200, {}),
                    (200, original), (200, registered(native_deck())), (200, {'files': []}),
                    (200, _google_file('scratch')), (200, native_deck('178')),
                    (200, {}), (204, b'')])
    file_id, link = upload('google')
    assert link == 'https://docs.google.com/presentation/d/existing/edit'
    assert upload('google', file_id, 178) == (file_id, link)
    assert [method for method, _, _ in calls] == ['GET', 'POST', 'GET', 'POST', 'GET', 'GET', 'GET', 'POST', 'GET', 'POST', 'DELETE']
    assert b'google-slides lunch 120' in calls[1][2]['data']
    assert calls[7][2]['params']['ignoreDefaultVisibility'] == 'true'
    assert b'gpAssemblyScratch' in calls[7][2]['data'] and b'google-slides lunch 178' in calls[7][2]['data']
    assert calls[9][:2] == ('POST', url + ':batchUpdate')
    batch = calls[9][2]['json']
    assert batch['writeControl'] == {'requiredRevisionId': 'revision-1'}
    assert any(op.get('insertText', {}).get('text') == '178' for op in batch['requests'])
    assert calls[-1][1] == cloud.DRIVE + '/scratch'
    assert all(args['headers']['Authorization'] == 'Bearer test-access' for _, _, args in calls)


def test_recovers_existing_binding_and_cleans_only_abandoned_private_scratch(api, upload):
    calls, replies = api
    replies.extend([(200, {'files': [{'id': 'existing'}]}), (200, _google_file()),
                    (200, registered(native_deck())), (200, {'files': [{'id': 'old-temp'}]}), (204, b''),
                    (200, _google_file('scratch')), (200, native_deck()), (204, b'')])
    assert upload('google')[0] == 'existing'
    assert 'gpAssemblyScratch' not in calls[0][2]['params']['q']
    assert 'gpAssemblyScratch' in calls[3][2]['params']['q'] and 'createdTime <' in calls[3][2]['params']['q']
    assert [url for method, url, _ in calls if method == 'DELETE'] == [cloud.DRIVE + '/old-temp', cloud.DRIVE + '/scratch']
    assert not any(url.endswith(':batchUpdate') for _, url, _ in calls)


@pytest.mark.parametrize('fail', ['revision', 'unmarked', 'wrong binding', 'trashed', 'disabled'])
def test_google_keeps_original_on_concurrent_edit_or_unrecognized_layout(api, upload, fail):
    calls, replies = api
    original = _google_file()
    if fail == 'wrong binding':
        original['appProperties'] = {'gpAssembly': 'another-school'}
    if fail == 'trashed':
        original['trashed'] = True
    replies.append((200, original))
    if fail == 'disabled':
        replies.append((403, {'error': {'details': [{'reason': 'SERVICE_DISABLED'}]}}))
    elif fail in ('revision', 'unmarked'):
        replies.extend([(200, native_deck()), (200, {'files': []}), (200, _google_file('scratch')),
                        (200, native_deck('179') if fail == 'revision' else {})])
        if fail == 'revision':
            replies.append((400, {'error': {'message': 'The required revision does not match private revision'}}))
        replies.append((204, b''))
    with pytest.raises(cloud.CloudDeckError) as caught:
        upload('google', 'existing')
    assert not any(method == 'PATCH' for method, _, _ in calls)
    assert all(url != cloud.DRIVE + '/existing' for method, url, _ in calls if method == 'DELETE')
    if fail in ('unmarked', 'revision'):
        assert calls[-1][:2] == ('DELETE', cloud.DRIVE + '/scratch')
    if fail == 'revision':
        assert 'changed' in str(caught.value) and 'private revision' not in str(caught.value)
    if fail == 'disabled':
        assert 'Enable the Google Drive API and Google Slides API' in str(caught.value)


REMOTE = {'id': 'root!school', 'webUrl': 'https://example.sharepoint.com/personal/school/assembly.pptx',
          'eTag': '"file,7"', '@microsoft.graph.downloadUrl': 'https://files.example/download'}
SESSION = {'uploadUrl': 'https://files.example/session'}


def test_onedrive_retains_presentation_item_and_merges_recovered_and_known_files(api, upload):
    calls, replies = api
    folder = {'id': 'root!folder'}
    replies.extend([(200, folder), (404, {}), (201, REMOTE)])
    file_id, link = upload('microsoft')
    assert file_id == REMOTE['id'] and link == REMOTE['webUrl']
    assert calls[2][2]['params'] == {'@microsoft.graph.conflictBehavior': 'fail'}
    assert calls[2][2]['headers']['If-None-Match'] == '*'
    assert calls[2][2]['data'] == b'marked powerpoint lunch 120'
    for prior_id in (None, file_id):
        if not prior_id:
            replies.append((200, folder))
        replies.extend([(200, REMOTE), (200, b'edited by teacher'), (200, SESSION), (200, REMOTE), (200, REMOTE)])
        assert upload('microsoft', prior_id, 178) == (file_id, link)
        download, session, check, write = calls[-4:]
        assert 'Authorization' not in download[2].get('headers', {})
        assert session[:2] == ('POST', cloud.ONEDRIVE + '/items/root%21school/createUploadSession')
        assert session[2]['headers']['If-Match'] == REMOTE['eTag']
        assert check[1].endswith('/items/root%21school')
        assert write[2]['data'] == b'edited by teacher + powerpoint lunch 178'
        assert write[1] == SESSION['uploadUrl']
        assert 'Authorization' not in write[2]['headers']
        assert write[2]['headers']['If-Match'] == REMOTE['eTag']


@pytest.mark.parametrize('phase', ['metadata', 'merge', 'session', 'recheck', 'upload'])
def test_onedrive_never_replaces_on_bad_file_or_concurrent_edit(api, upload, monkeypatch, phase):
    calls, replies = api
    replies.append((200, REMOTE if phase != 'metadata' else dict(REMOTE, eTag='*')))
    if phase != 'metadata':
        replies.append((200, b'saved'))
    if phase == 'merge':
        def reject(*args):
            raise cloud.MergeError('The saved PowerPoint could not be safely updated.')
        monkeypatch.setattr(cloud, 'merge_deck', reject)
    if phase in ('session', 'recheck', 'upload'):
        replies.append((412, {}) if phase == 'session' else (200, SESSION))
    if phase in ('recheck', 'upload'):
        replies.append((200, dict(REMOTE, eTag='"file,8"') if phase == 'recheck' else REMOTE))
    if phase == 'upload':
        replies.append((409, {}))
    with pytest.raises(cloud.CloudDeckError) as error:
        upload('microsoft', REMOTE['id'])
    assert not error.value.reconnect
    assert all(not url.endswith('/content') for _, url, _ in calls)
    assert sum(method == 'PUT' for method, _, _ in calls) == (phase == 'upload')
    assert not replies


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_lost_access_to_known_file_does_not_create_a_new_presentation(api, upload, provider):
    calls, replies = api
    replies.append((404, {'error': {'message': 'private provider detail'}}))
    with pytest.raises(cloud.CloudDeckError) as raised:
        upload(provider, 'original')
    assert raised.value.reconnect and 'private provider detail' not in str(raised.value)
    assert len(calls) == 1 and 'original' in calls[0][1]


def test_onedrive_reads_browser_url_if_upload_did_not_return_it(api, upload):
    calls, replies = api
    url = 'https://tenant.sharepoint.com/personal/school/assembly.pptx'
    replies.extend([(200, {'id': 'folder'}), (404, {}), (201, {'id': 'original'}), (200, {'webUrl': url})])
    assert upload('microsoft') == ('original', url)
    assert calls[-1][:2] == ('GET', cloud.ONEDRIVE + '/items/original')
