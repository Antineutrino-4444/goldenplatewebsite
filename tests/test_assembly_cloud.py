import base64
from hashlib import sha256
import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

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
        response._content = json.dumps(body).encode()
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

    def sync(provider, file_id=None, count=120):
        return cloud.upsert_deck(provider, 'test-access', 'stable-key', file_id,
                                 {'school_name': 'School', 'count': count}, 'dark')
    return sync


def test_google_creates_native_then_updates_original_file_and_link(api, upload):
    calls, replies = api
    remote = {'id': 'abc-def_G42', 'mimeType': cloud.SLIDES_MIME}
    replies.extend([(200, {'files': []}), (200, remote), (200, remote)])
    file_id, link = upload('google')
    assert link == 'https://docs.google.com/presentation/d/abc-def_G42/edit'
    assert upload('google', file_id, 178) == (file_id, link)
    assert [method for method, _, _ in calls] == ['GET', 'POST', 'PATCH']
    first = calls[1][2]['data']
    assert b'"appProperties"' in first and b'google-slides lunch 120' in first
    assert cloud.SLIDES_MIME.encode() in first and cloud.PPTX_MIME.encode() in first
    assert calls[2][1] == cloud.UPLOAD + '/' + file_id
    assert b'google-slides lunch 178' in calls[2][2]['data']
    assert all(args['headers']['Authorization'] == 'Bearer test-access' for _, _, args in calls)


def test_recovery_patches_discovered_native_file_without_creating_duplicate(api, upload):
    calls, replies = api
    remote = {'id': 'existing', 'mimeType': cloud.SLIDES_MIME}
    replies.extend([(200, {'files': [{'id': 'existing'}]}), (200, remote)])
    assert upload('google')[0] == 'existing'
    assert [call[0] for call in calls] == ['GET', 'PATCH']
    binding = sha256(b'stable-key').hexdigest()
    assert binding in calls[0][2]['params']['q']


def test_onedrive_retains_presentation_item_and_path_on_retry(api, upload):
    calls, replies = api
    folder = {'id': 'root!folder'}
    remote = {'id': 'root!school', 'webUrl': 'https://example.sharepoint.com/personal/school/assembly.pptx'}
    replies.extend([(200, folder), (201, remote), (200, folder), (200, remote), (200, remote)])
    file_id, link = upload('microsoft')
    assert upload('microsoft') == (file_id, link)
    assert upload('microsoft', file_id, 178) == (file_id, link)
    assert file_id == remote['id'] and link == remote['webUrl']
    assert calls[0][1] == cloud.ONEDRIVE + '/special/approot'
    assert calls[1][1] == calls[3][1] and calls[1][1].endswith('.pptx:/content')
    assert calls[4][:2] == ('PUT', cloud.ONEDRIVE + '/items/root%21school/content')
    assert calls[1][2]['data'] == b'powerpoint lunch 120' and calls[4][2]['data'] == b'powerpoint lunch 178'


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
    replies.extend([(200, {'id': 'original'}), (200, {'webUrl': url})])
    assert upload('microsoft', 'original') == ('original', url)
    assert [call[0] for call in calls] == ['PUT', 'GET']
    assert calls[1][1].endswith('/items/original')
