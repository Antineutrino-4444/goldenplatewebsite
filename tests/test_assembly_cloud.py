import base64
from copy import deepcopy
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
        status, body, *response_headers = replies.pop(0)
        response = requests.Response()
        response.status_code = status
        response._content = body if isinstance(body, bytes) else json.dumps(body).encode()
        if response_headers:
            response.headers.update(response_headers[0])
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


@pytest.mark.parametrize('category', ['invalid_client', 'unauthorized_client', 'invalid_scope'])
def test_microsoft_token_configuration_failures_are_distinct_and_safely_logged(api, caplog, category):
    _, replies = api
    private = 'private-token-secret-code-and-account'
    replies.append((400, {'error': category, 'error_description': private,
                          'error_codes': [7000215, private, True, {'secret': private}],
                          'access_token': private, 'refresh_token': private}))
    with pytest.raises(cloud.CloudDeckError) as caught:
        cloud._request('POST', cloud._oauth_endpoint('microsoft'),
                       data={'client_secret': private, 'code': private})
    assert caught.value.configuration and not caught.value.reconnect
    assert 'site administrator' in str(caught.value)
    assert 'provider=microsoft status=400' in caplog.text
    assert f'error={category} codes=[7000215]' in caplog.text
    assert private not in caplog.text and private not in str(caught.value)


@pytest.mark.parametrize('error', ['private-unknown-provider-error', {'code': 'private-unknown-provider-error'}])
def test_unknown_oauth_errors_do_not_leak_provider_content(api, caplog, error):
    _, replies = api
    replies.append((400, {'error': error, 'error_description': 'private-description',
                          'error_codes': 'private-codes'}))
    with pytest.raises(cloud.CloudDeckError) as caught:
        cloud._request('POST', cloud._oauth_endpoint('microsoft'))
    assert not caught.value.configuration
    assert 'error=unknown codes=[]' in caplog.text
    assert 'private-' not in caplog.text


def test_token_network_failure_logs_provider_without_request_secrets(monkeypatch, caplog):
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError('private-request-url-and-secret')
    monkeypatch.setattr(cloud.requests, 'request', unavailable)
    with pytest.raises(cloud.CloudDeckError):
        cloud._request('POST', cloud._oauth_endpoint('microsoft'))
    assert 'provider=microsoft status=network' in caplog.text
    assert 'private-' not in caplog.text


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
    assert 'writeControl' not in batch
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


@pytest.mark.parametrize('fail', ['wrong binding', 'trashed', 'disabled'])
def test_google_does_not_replace_wrong_binding_or_unavailable_account(api, upload, fail):
    calls, replies = api
    original = _google_file()
    if fail == 'wrong binding':
        original['appProperties'] = {'gpAssembly': 'another-school'}
    if fail == 'trashed':
        original['trashed'] = True
    replies.append((200, original))
    if fail == 'disabled':
        replies.append((403, {'error': {'details': [{'reason': 'SERVICE_DISABLED'}]}}))
    with pytest.raises(cloud.CloudDeckError) as caught:
        upload('google', 'existing')
    assert not any(method == 'PATCH' for method, _, _ in calls)
    assert all(url != cloud.DRIVE + '/existing' for method, url, _ in calls if method == 'DELETE')
    if fail == 'disabled':
        assert 'Enable the Google Drive API and Google Slides API' in str(caught.value)
        assert caught.value.configuration


def test_google_native_update_overwrites_edits_without_a_revision_condition(api, upload):
    calls, replies = api
    saved = registered(native_deck())
    saved.pop('revisionId')
    replies.extend([(200, _google_file()), (200, saved), (200, {'files': []}),
                    (200, _google_file('scratch')), (200, native_deck('178', revision='newer-edit')),
                    (200, {}), (204, b'')])
    assert upload('google', 'existing', 178) == ('existing', 'https://docs.google.com/presentation/d/existing/edit')
    batch = next(args['json'] for _, url, args in calls if url.endswith(':batchUpdate'))
    assert 'writeControl' not in batch
    assert any(op.get('insertText', {}).get('text') == '178' for op in batch['requests'])
    assert not any(method == 'PATCH' for method, _, _ in calls)
    assert not replies


@pytest.mark.parametrize('failure', ['unmarked', 'duplicate', 'concurrent', 'read'])
def test_google_replaces_unusable_saved_presentation_at_same_id_and_link(api, upload, failure):
    calls, replies = api
    saved = native_deck()
    if failure == 'unmarked':
        saved = {'slides': [{'objectId': 'teacher_slide', 'pageElements': []}]}
    elif failure == 'duplicate':
        saved['slides'].append(deepcopy(saved['slides'][0]))
    replies.extend([(200, _google_file()), (500, {}) if failure == 'read' else (200, saved)])
    if failure != 'read':
        replies.extend([(200, {'files': []}), (200, _google_file('scratch')), (200, native_deck('178'))])
        if failure == 'concurrent':
            replies.append((400, {'error': {'message': 'Object deleted during private-account edit'}}))
    replies.extend([(200, _google_file()), (200, native_deck('178')), (200, {})])
    if failure != 'read':
        replies.append((204, b''))
    assert upload('google', 'existing', 178) == ('existing', 'https://docs.google.com/presentation/d/existing/edit')
    writes = [(url, args) for method, url, args in calls if method == 'PATCH']
    assert len(writes) == 1
    url, args = writes[0]
    assert url == cloud.UPLOAD + '/existing'
    assert args['params']['uploadType'] == 'multipart'
    assert b'google-slides lunch 178' in args['data']
    assert b'"mimeType": "application/vnd.google-apps.presentation"' in args['data']
    assert b'"name"' not in args['data'] and b'"appProperties"' not in args['data']
    assert 'If-Match' not in args['headers']
    batches = [args['json'] for _, url, args in calls if url.endswith(':batchUpdate')]
    assert batches and all('writeControl' not in batch for batch in batches)
    deleted = [url for method, url, _ in calls if method == 'DELETE']
    assert deleted == ([] if failure == 'read' else [cloud.DRIVE + '/scratch'])
    assert not replies


@pytest.mark.parametrize('replacement', [
    (403, {'error': {'code': 'accessDenied', 'message': 'private-account'}}),
    (200, _google_file('unexpected-file')),
])
def test_google_replacement_failure_reports_error_and_cleans_only_scratch(api, upload, replacement):
    calls, replies = api
    replies.extend([(200, _google_file()), (200, {'slides': []}), (200, {'files': []}),
                    (200, _google_file('scratch')), (200, native_deck()), replacement, (204, b'')])
    with pytest.raises(cloud.CloudDeckError) as caught:
        upload('google', 'existing')
    assert 'private-account' not in str(caught.value)
    assert calls[-1][:2] == ('DELETE', cloud.DRIVE + '/scratch')
    assert [url for method, url, _ in calls if method == 'PATCH'] == [cloud.UPLOAD + '/existing']
    assert not replies


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
        replies.extend([(200, REMOTE), (200, b'edited by teacher'), (200, SESSION), (200, REMOTE)])
        assert upload('microsoft', prior_id, 178) == (file_id, link)
        download, session, write = calls[-3:]
        assert 'Authorization' not in download[2].get('headers', {})
        assert session[:2] == ('POST', cloud.ONEDRIVE + '/items/root%21school/createUploadSession')
        assert 'If-Match' not in session[2]['headers']
        assert write[2]['data'] == b'edited by teacher + powerpoint lunch 178'
        assert write[1] == SESSION['uploadUrl']
        assert 'Authorization' not in write[2]['headers']
        assert 'If-Match' not in write[2]['headers']
        assert not replies


def test_onedrive_personal_opaque_version_tag_updates_the_same_file(api, upload):
    calls, replies = api
    personal = dict(REMOTE, eTag='aRDQ2NDhGMDZDOTFEOUQzRCE1NDkyNy4w')
    replies.extend([(200, personal), (200, b'teacher edits'), (200, SESSION), (200, personal)])
    assert upload('microsoft', personal['id'], 178) == (personal['id'], personal['webUrl'])
    assert 'If-Match' not in calls[2][2]['headers']
    assert 'If-Match' not in calls[3][2]['headers']
    assert calls[3][2]['data'] == b'teacher edits + powerpoint lunch 178'
    assert 'Authorization' not in calls[1][2].get('headers', {})
    assert 'Authorization' not in calls[3][2]['headers']


@pytest.mark.parametrize('recover', [False, True])
def test_onedrive_existing_file_does_not_fail_its_own_name_conflict(api, upload, monkeypatch, recover):
    calls, replies = api
    if recover:
        replies.append((200, {'id': 'folder'}))
    replies.extend([(200, REMOTE), (200, b'teacher slides and photos'), (200, SESSION)])
    send = cloud.requests.request

    def existing_file(method, url, **kwargs):
        if method == 'POST' and url.endswith('/createUploadSession'):
            # Model OneDrive's final name-conflict check for an existing file.
            behavior = kwargs.get('json', {}).get('item', {}).get('@microsoft.graph.conflictBehavior', 'fail')
            replies.append((200, REMOTE) if behavior == 'replace' else
                           (409, {'error': {'code': 'nameAlreadyExists'}}))
        return send(method, url, **kwargs)

    monkeypatch.setattr(cloud.requests, 'request', existing_file)
    assert upload('microsoft', None if recover else REMOTE['id'], 178) == (REMOTE['id'], REMOTE['webUrl'])
    session = next(args for method, url, args in calls if url.endswith('/createUploadSession'))
    assert 'If-Match' not in session['headers']
    assert 'If-Match' not in calls[-1][2]['headers']
    assert calls[-1][2]['data'] == b'teacher slides and photos + powerpoint lunch 178'
    assert 'Authorization' not in calls[-1][2]['headers']
    assert not replies


@pytest.mark.parametrize('status,code,expected', [
    (409, 'nameAlreadyExists', 'file-name conflict'),
    (409, 'resourceModified', 'conflict'),
    (412, 'preconditionFailed', 'changed'),
    (423, 'resourceLocked', 'locked'),
])
def test_upload_conflict_errors_distinguish_recovery_without_provider_details(api, status, code, expected):
    _, replies = api
    replies.append((status, {'error': {'code': code, 'message': 'private-file-url-and-account'}}))
    with pytest.raises(cloud.CloudDeckError) as caught:
        cloud._request('PUT', SESSION['uploadUrl'], data=b'updated deck')
    assert expected in str(caught.value)
    assert 'private-' not in str(caught.value)
    assert not caught.value.reconnect


@pytest.mark.parametrize('tag', [None, '', '*', 'W/"version"', '"one","two"',
                                 'one,two', 'one two', 'one\r\nIf-Match: *', 'one\x00two', '"one\ttwo"'])
def test_onedrive_version_tags_do_not_prevent_replacement_or_enter_headers(api, upload, tag):
    calls, replies = api
    replies.extend([(200, dict(REMOTE, eTag=tag)), (200, b'teacher edits'), (200, SESSION), (200, REMOTE)])
    assert upload('microsoft', REMOTE['id'])[0] == REMOTE['id']
    assert all('If-Match' not in options.get('headers', {}) for _, _, options in calls)
    assert not replies


@pytest.mark.parametrize('large', [False, True])
def test_onedrive_overwrites_edits_made_during_upload(api, upload, monkeypatch, large):
    calls, replies = api
    merged = b'new assembly' if not large else b'x' * (10 * 1024 * 1024 + 17)
    monkeypatch.setattr(cloud, 'merge_deck', lambda *args: merged)
    replies.extend([(200, REMOTE), (200, b'earlier edits'), (200, SESSION)])
    send = cloud.requests.request

    def edit_during_upload(method, url, **kwargs):
        if method == 'PUT':
            # The remote version changed after download. Reject stale conditions.
            assert 'If-Match' not in kwargs['headers']
            final = kwargs['headers']['Content-Range'].endswith(f'-{len(merged) - 1}/{len(merged)}')
            replies.append((200, dict(REMOTE, eTag='newer-edited-version')) if final else
                           (202, {'nextExpectedRanges': ['10485760-']}))
        return send(method, url, **kwargs)

    monkeypatch.setattr(cloud.requests, 'request', edit_during_upload)
    assert upload('microsoft', REMOTE['id']) == (REMOTE['id'], REMOTE['webUrl'])
    writes = [options['data'] for method, _, options in calls if method == 'PUT']
    assert b''.join(writes) == merged
    assert len(writes) == (2 if large else 1)
    assert [url for method, url, _ in calls if method == 'GET'] == [
        cloud.ONEDRIVE + '/items/root%21school', REMOTE['@microsoft.graph.downloadUrl']]
    assert not replies


def test_onedrive_wrong_identity_is_never_overwritten(api, upload):
    calls, replies = api
    replies.append((200, dict(REMOTE, id='another-file')))
    with pytest.raises(cloud.CloudDeckError, match='original presentation identity'):
        upload('microsoft', REMOTE['id'])
    assert len(calls) == 1


@pytest.mark.parametrize('annotation', ['absent', None, ''])
def test_onedrive_missing_download_annotation_uses_content_redirect(api, upload, annotation):
    calls, replies = api
    info = {key: value for key, value in REMOTE.items() if key != '@microsoft.graph.downloadUrl'}
    if annotation != 'absent':
        info['@microsoft.graph.downloadUrl'] = annotation
    replies.extend([(200, info), (302, b'', {'Location': REMOTE['@microsoft.graph.downloadUrl']}),
                    (200, b'teacher edits'), (200, SESSION), (200, REMOTE)])
    assert upload('microsoft', info['id'], 178) == (info['id'], info['webUrl'])
    content, download, session, write = calls[1:]
    assert content[:2] == ('GET', cloud.ONEDRIVE + '/items/root%21school/content')
    assert content[2]['headers']['Authorization'] == 'Bearer test-access'
    assert 'Authorization' not in download[2].get('headers', {})
    assert 'If-Match' not in session[2]['headers']
    assert 'If-Match' not in write[2]['headers']
    assert 'Authorization' not in write[2]['headers']
    assert write[2]['data'] == b'teacher edits + powerpoint lunch 178'
    assert not replies


def test_onedrive_content_endpoint_can_return_the_file_directly(api, upload):
    calls, replies = api
    info = dict(REMOTE, **{'@microsoft.graph.downloadUrl': None})
    replies.extend([(200, info), (200, b'teacher edits'), (200, SESSION), (200, REMOTE)])
    assert upload('microsoft', info['id']) == (info['id'], info['webUrl'])
    assert calls[1][1].endswith('/content')
    assert calls[-1][2]['data'] == b'teacher edits + powerpoint lunch 120'


@pytest.mark.parametrize('location', [None, '', 'http://files.example/download',
                                     'https://secret@files.example/download', 'javascript:secret',
                                     '/relative', 'https://[invalid', 'https://files.example/\r\nsecret'])
def test_onedrive_unusable_download_redirect_replaces_with_fresh_deck(api, upload, location):
    calls, replies = api
    replies.extend([(200, dict(REMOTE, **{'@microsoft.graph.downloadUrl': None})),
                    (302, b'', {} if location is None else {'Location': location}),
                    (200, SESSION), (200, REMOTE)])
    assert upload('microsoft', REMOTE['id'])[0] == REMOTE['id']
    assert len(calls) == 4  # Never fetch the unsafe redirect.
    assert calls[-1][2]['data'] == b'marked powerpoint lunch 120'
    assert not replies


@pytest.mark.parametrize('status,reconnect', [(401, True), (403, True), (404, True)])
def test_onedrive_content_failure_keeps_the_file_and_reports_safe_recovery(api, upload, status, reconnect):
    calls, replies = api
    replies.extend([(200, dict(REMOTE, **{'@microsoft.graph.downloadUrl': None})),
                    (status, {'error': {'code': 'accessDenied', 'message': 'private provider detail'}})])
    with pytest.raises(cloud.CloudDeckError) as caught:
        upload('microsoft', REMOTE['id'])
    assert caught.value.reconnect is reconnect
    assert 'private provider detail' not in str(caught.value)
    assert len(calls) == 2 and all(method == 'GET' for method, _, _ in calls)


@pytest.mark.parametrize('failure', ['merge', 'download', 'unsafe_url'])
def test_onedrive_unusable_saved_deck_is_replaced_at_same_link(api, upload, monkeypatch, failure):
    calls, replies = api
    info = dict(REMOTE)
    if failure == 'unsafe_url':
        info['@microsoft.graph.downloadUrl'] = 'http://files.example/unsafe'
    replies.append((200, info))
    if failure == 'merge':
        replies.append((200, b'corrupt or unrecognized presentation'))
        def reject(*args):
            raise cloud.MergeError('Cannot merge this saved file')
        monkeypatch.setattr(cloud, 'merge_deck', reject)
    elif failure == 'download':
        replies.append((500, {}))
    replies.extend([(200, SESSION), (200, REMOTE)])
    assert upload('microsoft', REMOTE['id']) == (REMOTE['id'], REMOTE['webUrl'])
    assert calls[-1][2]['data'] == b'marked powerpoint lunch 120'
    assert not any(url.startswith('http://') for _, url, _ in calls)
    assert not replies


@pytest.mark.parametrize('phase', ['session', 'upload'])
@pytest.mark.parametrize('status', [409, 412, 423])
def test_onedrive_reports_provider_rejection_without_creating_another_file(api, upload, phase, status):
    calls, replies = api
    replies.extend([(200, REMOTE), (200, b'saved'),
                    (status, {}) if phase == 'session' else (200, SESSION)])
    if phase == 'upload':
        replies.append((status, {}))
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
