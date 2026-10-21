from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from src.routes.golden_plate_recorder_db import captcha
from src.routes.golden_plate_recorder_db.db import AccountCreationRequest, db_session
from src.routes.golden_plate_recorder_db.map_db import MapSubmission, map_db_session


def cloudflare_result(**overrides):
    return {
        'success': True, 'action': 'account_signup',
        'hostname': 'goldenplate.ca', 'challenge_ts': datetime.now(timezone.utc).isoformat(),
        **overrides,
    }


@pytest.fixture
def cloudflare(monkeypatch):
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', 'test-secret')
    monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES', 'goldenplate.ca,map.goldenplate.ca')
    state = SimpleNamespace(result=cloudflare_result(), calls=[], failure=None)
    def post(url, *, data, timeout):
        state.calls.append({'url': url, 'data': data, 'timeout': timeout})
        if state.failure:
            raise state.failure
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: state.result)
    monkeypatch.setattr(captcha, 'requests', SimpleNamespace(post=post, RequestException=requests.RequestException))
    return state


def test_valid_turnstile_token_uses_server_secret_and_expected_action(cloudflare):
    assert captcha.captcha_failure('fresh-token', 'account_signup') is None
    assert cloudflare.calls == [{'url': captcha.VERIFY_URL, 'data': {'secret': 'test-secret', 'response': 'fresh-token'}, 'timeout': 10}]


@pytest.mark.parametrize('overrides', [
    {'success': False}, {'success': 1}, {'action': 'school_register'}, {'action': None},
    {'hostname': 'evil.example'}, {'hostname': 'goldenplate.ca.evil.example'}, {'hostname': None},
    {'challenge_ts': 'invalid'}, {'challenge_ts': None},
    {'challenge_ts': datetime.now().isoformat()},
    {'error-codes': ['quota-exceeded']},
])
def test_invalid_turnstile_results_are_rejected_even_when_success_is_true(cloudflare, overrides):
    overrides = {key: value() if callable(value) else value for key, value in overrides.items()}
    cloudflare.result = cloudflare_result(**overrides)
    assert captcha.captcha_failure('token', 'account_signup').code == 'CAPTCHA_INVALID'


@pytest.mark.parametrize('missing', ['action', 'hostname', 'challenge_ts'])
def test_incomplete_responses_cannot_bypass_turnstile_checks(cloudflare, missing):
    cloudflare.result.pop(missing)
    assert captcha.captcha_failure('token', 'account_signup') is not None


@pytest.mark.parametrize('token', ['', None, [], 123])
def test_missing_or_invalid_tokens_do_not_contact_cloudflare(cloudflare, token):
    assert captcha.captcha_failure(token, 'account_signup').code == 'CAPTCHA_REQUIRED'
    assert cloudflare.calls == []


def test_oversized_token_is_rejected_before_contacting_cloudflare(cloudflare):
    assert captcha.captcha_failure('x' * 2049, 'account_signup').code == 'CAPTCHA_INVALID'
    assert cloudflare.calls == []


@pytest.mark.parametrize('secret', sorted(captcha.TEST_SECRETS))
def test_dummy_secrets_cannot_enable_verification_in_production(cloudflare, monkeypatch, secret):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', secret)
    assert captcha.captcha_failure('token', 'account_signup').status == 503
    assert cloudflare.calls == []


def test_localhost_cannot_be_allowed_in_production(cloudflare, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES', 'goldenplate.ca,localhost,127.0.0.1')
    cloudflare.result['hostname'] = 'localhost'
    assert captcha.captcha_failure('token', 'account_signup').code == 'CAPTCHA_INVALID'


@pytest.mark.parametrize('code', ['invalid-input-secret', 'missing-input-secret', 'internal-error'])
def test_configuration_and_provider_errors_report_unavailable(cloudflare, code):
    cloudflare.result = cloudflare_result(**{'success': False, 'error-codes': [code]})
    assert captcha.captcha_failure('token', 'account_signup').status == 503


def test_custom_hostname_is_exactly_allowlisted(cloudflare, monkeypatch):
    cloudflare.result['hostname'] = 'staging.goldenplate.ca'
    assert captcha.captcha_failure('token', 'account_signup') is not None
    monkeypatch.setenv('TURNSTILE_ALLOWED_HOSTNAMES', 'staging.goldenplate.ca')
    assert captcha.captcha_failure('new-token', 'account_signup') is None


@pytest.mark.parametrize('failure', [requests.Timeout('test timeout'), requests.HTTPError('quota error'), ValueError('invalid JSON')])
def test_cloudflare_failures_do_not_allow_requests(cloudflare, failure):
    cloudflare.failure = failure
    assert captcha.captcha_failure('token', 'account_signup').status == 503


@pytest.mark.parametrize('payload', [None, [], 'invalid'])
def test_malformed_cloudflare_response_is_rejected(cloudflare, payload):
    cloudflare.result = payload
    assert captcha.captcha_failure('token', 'account_signup').code == 'CAPTCHA_INVALID'


def test_expiry_and_single_use_errors_request_a_fresh_token(cloudflare):
    cloudflare.result = cloudflare_result(**{'success': False, 'error-codes': ['timeout-or-duplicate']})
    assert captcha.captcha_failure('used-token', 'account_signup').code == 'CAPTCHA_EXPIRED'
    cloudflare.result = cloudflare_result()
    assert captcha.captcha_failure('new-token', 'account_signup') is None


@pytest.mark.parametrize('offset', [timedelta(minutes=-3), timedelta(hours=-2), timedelta(minutes=1)])
def test_verified_tokens_rely_on_cloudflare_expiry_and_not_server_clock(cloudflare, offset):
    cloudflare.result = cloudflare_result(challenge_ts=(datetime.now(timezone.utc) + offset).isoformat())
    assert captcha.captcha_failure('freshly-executed-token', 'account_signup') is None


@pytest.mark.parametrize('accepted', [False, True])
def test_account_email_code_uses_cloudflare_validity_even_after_page_was_left_open(client, login, cloudflare, email_outbox, accepted):
    login()
    cloudflare.result = cloudflare_result(action='account_email_code',
        challenge_ts=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        **({} if accepted else {'success': False, 'error-codes': ['timeout-or-duplicate']}))
    response = client.post('/api/auth/account-email/send-verification-code', json={
        'email': 'fresh-click@example.com', 'captcha_token': 'button-click-token',
    })
    assert response.status_code == (200 if accepted else 400)
    assert len(email_outbox) == (1 if accepted else 0)
    if not accepted:
        assert response.get_json()['code'] == 'CAPTCHA_EXPIRED'


def test_missing_secret_is_allowed_only_in_development(client, monkeypatch):
    monkeypatch.setenv('TURNSTILE_SECRET_KEY', '')
    assert captcha.captcha_failure(None, 'account_signup') is None
    monkeypatch.setenv('APP_ENV', 'production')
    assert captcha.captcha_failure('token', 'account_signup').status == 503
    assert client.post('/api/auth/signup', json={'captcha_token': 'token'}).status_code == 503


ENDPOINTS = [
    ('/api/auth/signup', 'account_signup', False),
    ('/api/auth/signup/send-verification-code', 'account_email_code', False),
    ('/api/auth/send-verification-code', 'school_email_code', False),
    ('/api/auth/register-school', 'school_register', False),
    ('/api/map/send-verification-code', 'map_email_code', False),
    ('/api/map/submissions', 'map_submit', True),
]


@pytest.mark.parametrize('url,action,multipart', ENDPOINTS)
@pytest.mark.parametrize('valid', [False, True])
def test_each_protected_route_checks_its_own_action(client, cloudflare, email_outbox, url, action, multipart, valid):
    cloudflare.result = cloudflare_result(action=action if valid else 'wrong_action')
    payload = {'captcha_token': 'token'}
    response = client.post(url, **({'data': payload} if multipart else {'json': payload}))
    body = response.get_json()
    assert response.status_code == 400
    assert ('CAPTCHA' in body.get('code', '')) is not valid
    assert len(cloudflare.calls) == 1
    assert email_outbox == []


@pytest.mark.parametrize('valid', [False, True])
def test_recovery_checks_its_action_before_sending(client, cloudflare, email_outbox, valid):
    cloudflare.result = cloudflare_result(action='password_recovery' if valid else 'account_signup')
    response = client.post('/api/auth/password-recovery/request', json={
        'identifier': 'nonexistent-turnstile-test-user', 'confirmed': True, 'captcha_token': 'token',
    })
    assert response.status_code == (200 if valid else 400)
    assert len(cloudflare.calls) == 1
    assert email_outbox == []


def test_signed_in_email_verification_rejects_a_token_for_signup(client, login, cloudflare, email_outbox):
    login()
    response = client.post('/api/auth/account-email/send-verification-code', json={
        'email': 'turnstile-mismatch@example.com', 'captcha_token': 'token',
    })
    assert response.status_code == 400
    assert response.get_json()['code'] == 'CAPTCHA_INVALID'
    assert len(cloudflare.calls) == 1
    assert email_outbox == []


def test_valid_signup_token_creates_request_without_exposing_token(client, cloudflare, signup_email_code):
    response = client.post('/api/auth/signup', json={
        'username': 'turnstile-signup-test', 'password': 'test-password', 'name': 'Turnstile Signup',
        'email': 'turnstile-signup@example.com',
        'verification_code': signup_email_code('turnstile-signup@example.com'),
        'school_code': 'SAC', 'captcha_token': 'valid-signup-token',
    })
    assert response.status_code == 201
    assert db_session.query(AccountCreationRequest).filter_by(username='turnstile-signup-test', status='pending').first()
    assert 'valid-signup-token' not in response.get_data(as_text=True)


def test_expired_map_upload_is_rejected_before_saving_and_retry_uses_new_token(client, cloudflare, email_outbox):
    initial_count = map_db_session.query(MapSubmission).count()
    cloudflare.result = cloudflare_result(action='map_submit', **{'success': False, 'error-codes': ['timeout-or-duplicate']})
    response = client.post('/api/map/submissions', data={'captcha_token': 'expired-upload-token', 'email': 'turnstile@sac.on.ca'})
    assert response.status_code == 400
    assert response.get_json()['code'] == 'MAP_CAPTCHA_EXPIRED'
    assert map_db_session.query(MapSubmission).count() == initial_count
    assert email_outbox == []
    cloudflare.result = cloudflare_result(action='map_submit')
    retry = client.post('/api/map/submissions', data={'captcha_token': 'fresh-upload-token'})
    assert retry.get_json()['code'] == 'MAP_EMAIL_REQUIRED'
    assert [call['data']['response'] for call in cloudflare.calls] == ['expired-upload-token', 'fresh-upload-token']


@pytest.fixture(autouse=True)
def _enable_archived_map_for_regression_tests(monkeypatch):
    monkeypatch.setenv("MAP_LEGACY_FEATURES_ENABLED", "true")
