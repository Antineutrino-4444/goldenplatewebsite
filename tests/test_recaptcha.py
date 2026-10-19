from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests

from src.routes.golden_plate_recorder_db import recaptcha
from src.routes.golden_plate_recorder_db.db import AccountCreationRequest, db_session
from src.routes.golden_plate_recorder_db.map_db import MapSubmission, map_db_session


def google_result(**overrides):
    return {
        'success': True, 'score': 0.9, 'action': 'account_signup',
        'hostname': 'goldenplate.ca', 'challenge_ts': datetime.now(timezone.utc).isoformat(),
        **overrides,
    }


@pytest.fixture
def google(monkeypatch):
    monkeypatch.setenv('RECAPTCHA_SECRET_KEY', 'test-secret')
    monkeypatch.setenv('RECAPTCHA_MIN_SCORE', '0.5')
    monkeypatch.setenv('RECAPTCHA_ALLOWED_HOSTNAMES', 'goldenplate.ca,map.goldenplate.ca')
    state = SimpleNamespace(result=google_result(), calls=[], failure=None)
    def post(url, *, data, timeout):
        state.calls.append({'url': url, 'data': data, 'timeout': timeout})
        if state.failure:
            raise state.failure
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: state.result)
    monkeypatch.setattr(recaptcha, 'requests', SimpleNamespace(post=post, RequestException=requests.RequestException))
    return state


def test_valid_v3_token_uses_server_secret_and_expected_action(google):
    assert recaptcha.recaptcha_failure('fresh-token', 'account_signup') is None
    assert google.calls == [{'url': recaptcha.VERIFY_URL, 'data': {'secret': 'test-secret', 'response': 'fresh-token'}, 'timeout': 10}]


@pytest.mark.parametrize('overrides', [
    {'success': False}, {'success': 1}, {'action': 'school_register'}, {'action': None},
    {'hostname': 'evil.example'}, {'hostname': 'goldenplate.ca.evil.example'}, {'hostname': None},
    {'score': None}, {'score': '0.9'}, {'score': True}, {'score': float('nan')},
    {'score': -0.1}, {'score': 1.1}, {'challenge_ts': 'invalid'}, {'challenge_ts': None},
    {'challenge_ts': datetime.now().isoformat()},
    {'error-codes': ['quota-exceeded']},
])
def test_invalid_v3_results_are_rejected_even_when_success_is_true(google, overrides):
    overrides = {key: value() if callable(value) else value for key, value in overrides.items()}
    google.result = google_result(**overrides)
    assert recaptcha.recaptcha_failure('token', 'account_signup').code == 'RECAPTCHA_INVALID'


@pytest.mark.parametrize('missing', ['action', 'hostname', 'score', 'challenge_ts'])
def test_v2_or_incomplete_responses_cannot_bypass_v3_checks(google, missing):
    google.result.pop(missing)
    assert recaptcha.recaptcha_failure('token', 'account_signup') is not None


@pytest.mark.parametrize('token', ['', None, [], 123])
def test_missing_or_invalid_tokens_do_not_contact_google(google, token):
    assert recaptcha.recaptcha_failure(token, 'account_signup').code == 'RECAPTCHA_REQUIRED'
    assert google.calls == []


def test_low_score_is_rejected_and_threshold_is_configurable(google, monkeypatch):
    google.result['score'] = 0.4
    assert recaptcha.recaptcha_failure('token', 'account_signup').status == 403
    monkeypatch.setenv('RECAPTCHA_MIN_SCORE', '0.3')
    assert recaptcha.recaptcha_failure('new-token', 'account_signup') is None


@pytest.mark.parametrize('threshold', ['NaN', '-1', '2', 'invalid'])
def test_bad_server_threshold_fails_closed(google, monkeypatch, threshold):
    monkeypatch.setenv('RECAPTCHA_MIN_SCORE', threshold)
    assert recaptcha.recaptcha_failure('token', 'account_signup').status == 503
    assert google.calls == []


def test_custom_hostname_is_exactly_allowlisted(google, monkeypatch):
    google.result['hostname'] = 'staging.goldenplate.ca'
    assert recaptcha.recaptcha_failure('token', 'account_signup') is not None
    monkeypatch.setenv('RECAPTCHA_ALLOWED_HOSTNAMES', 'staging.goldenplate.ca')
    assert recaptcha.recaptcha_failure('new-token', 'account_signup') is None


@pytest.mark.parametrize('failure', [requests.Timeout('test timeout'), requests.HTTPError('quota error'), ValueError('invalid JSON')])
def test_google_failures_do_not_allow_requests(google, failure):
    google.failure = failure
    assert recaptcha.recaptcha_failure('token', 'account_signup').status == 503


@pytest.mark.parametrize('payload', [None, [], 'invalid'])
def test_malformed_google_response_is_rejected(google, payload):
    google.result = payload
    assert recaptcha.recaptcha_failure('token', 'account_signup').code == 'RECAPTCHA_INVALID'


def test_expiry_and_single_use_errors_request_a_fresh_token(google):
    google.result = google_result(**{'success': False, 'error-codes': ['timeout-or-duplicate']})
    assert recaptcha.recaptcha_failure('used-token', 'account_signup').code == 'RECAPTCHA_EXPIRED'
    google.result = google_result()
    assert recaptcha.recaptcha_failure('new-token', 'account_signup') is None


@pytest.mark.parametrize('offset', [timedelta(minutes=-3), timedelta(hours=-2), timedelta(minutes=1)])
def test_google_valid_tokens_do_not_expire_based_on_challenge_load_time_or_server_clock(google, offset):
    google.result = google_result(challenge_ts=(datetime.now(timezone.utc) + offset).isoformat())
    assert recaptcha.recaptcha_failure('freshly-executed-token', 'account_signup') is None


@pytest.mark.parametrize('accepted', [False, True])
def test_account_email_code_uses_google_validity_even_after_page_was_left_open(client, login, google, email_outbox, accepted):
    login()
    google.result = google_result(action='account_email_code',
        challenge_ts=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        **({} if accepted else {'success': False, 'error-codes': ['timeout-or-duplicate']}))
    response = client.post('/api/auth/account-email/send-verification-code', json={
        'email': 'fresh-click@example.com', 'recaptcha_token': 'button-click-token',
    })
    assert response.status_code == (200 if accepted else 400)
    assert len(email_outbox) == (1 if accepted else 0)
    if not accepted:
        assert response.get_json()['code'] == 'RECAPTCHA_EXPIRED'


def test_missing_secret_is_allowed_only_in_development(client, monkeypatch):
    monkeypatch.setenv('RECAPTCHA_SECRET_KEY', '')
    assert recaptcha.recaptcha_failure(None, 'account_signup') is None
    monkeypatch.setenv('APP_ENV', 'production')
    assert recaptcha.recaptcha_failure('token', 'account_signup').status == 503
    assert client.post('/api/auth/signup', json={'recaptcha_token': 'token'}).status_code == 503


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
def test_each_protected_route_checks_its_own_action(client, google, email_outbox, url, action, multipart, valid):
    google.result = google_result(action=action if valid else 'wrong_action')
    payload = {'recaptcha_token': 'token'}
    response = client.post(url, **({'data': payload} if multipart else {'json': payload}))
    body = response.get_json()
    assert response.status_code == 400
    assert ('RECAPTCHA' in body.get('code', '')) is not valid
    assert len(google.calls) == 1
    assert email_outbox == []


def test_valid_signup_token_creates_request_without_exposing_token(client, google, signup_email_code):
    response = client.post('/api/auth/signup', json={
        'username': 'v3-signup-test', 'password': 'test-password', 'name': 'V3 Signup',
        'email': 'v3-signup@example.com',
        'verification_code': signup_email_code('v3-signup@example.com'),
        'school_code': 'SAC', 'recaptcha_token': 'valid-signup-token',
    })
    assert response.status_code == 201
    assert db_session.query(AccountCreationRequest).filter_by(username='v3-signup-test', status='pending').first()
    assert 'valid-signup-token' not in response.get_data(as_text=True)


def test_expired_map_upload_is_rejected_before_saving_and_retry_uses_new_token(client, google, email_outbox):
    initial_count = map_db_session.query(MapSubmission).count()
    google.result = google_result(action='map_submit', **{'success': False, 'error-codes': ['timeout-or-duplicate']})
    response = client.post('/api/map/submissions', data={'recaptcha_token': 'expired-upload-token', 'email': 'v3@sac.on.ca'})
    assert response.status_code == 400
    assert response.get_json()['code'] == 'MAP_RECAPTCHA_EXPIRED'
    assert map_db_session.query(MapSubmission).count() == initial_count
    assert email_outbox == []
    google.result = google_result(action='map_submit')
    retry = client.post('/api/map/submissions', data={'recaptcha_token': 'fresh-upload-token'})
    assert retry.get_json()['code'] == 'MAP_EMAIL_REQUIRED'
    assert [call['data']['response'] for call in google.calls] == ['expired-upload-token', 'fresh-upload-token']


@pytest.fixture(autouse=True)
def _enable_archived_map_for_regression_tests(monkeypatch):
    monkeypatch.setenv("MAP_LEGACY_FEATURES_ENABLED", "true")
