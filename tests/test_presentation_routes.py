import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

import pytest

from src.routes.golden_plate_recorder_db.db import (
    INTERSCHOOL_SCHOOL_SLUG, School, Session, db_session, _now_utc,
)
from src.routes.golden_plate_recorder_db.users import create_user_record

ENDPOINT = '/api/resources/presentations/download'


@pytest.fixture
def school_data(client):
    client.get('/api/auth/status')
    tag = uuid.uuid4().hex[:10]
    school = School(id=f'slides-{tag}', name='Slides School', slug=f'School-{tag}',
                    guest_privacy_enabled=0, live_counter_settings=json.dumps({'timezone': 'Asia/Tokyo', 'milestone': 100}))
    db_session.add(school)
    db_session.commit()
    user = create_user_record(f'member-{tag}', 'member-password', 'Internal Member',
                              school_id=school.id, email=f'{tag}@example.com', email_verified_at=_now_utc())

    def session(name, day, counts, public=1, status='active'):
        row = Session(school_id=school.id, session_name=name, created_by=user.id, is_public=public,
                      status=status, created_at=datetime(2026, 10, day, 20, tzinfo=timezone.utc),
                      clean_number=counts[0], faculty_number=counts[1], dirty_number=counts[2], red_number=counts[3])
        db_session.add(row)
        db_session.commit()
        return row.id

    return {'code': school.slug, 'id': school.id, 'username': user.username, 'session': session}


def download(client, code, **options):
    return client.post(ENDPOINT, json={'school_code': code, 'kind': 'assembly', 'theme': 'light',
                                       'format': 'pptx', **options})


@pytest.fixture
def exports(monkeypatch):
    captured = []

    def generate(kind, theme, snapshot, platform):
        captured.append((kind, theme, snapshot, platform))
        return b'exported presentation'

    monkeypatch.setattr('src.services.presentation_exports.generate_deck', generate)
    return captured


def test_download_school_label_is_optional_and_preserves_school_identity(client, school_data, exports):
    for options, expected in [({}, None), ({'school_label': '   '}, None),
                              ({'school_label': '  École\n  ABC  '}, 'École ABC')]:
        response = download(client, school_data['code'], **options)
        assert response.status_code == 200
        snapshot = exports[-1][2]
        assert snapshot['school_name'] == 'Slides School' and snapshot['school_label'] == expected
        assert school_data['code'] in response.headers['Content-Disposition']
    for invalid in [[], 7, 'School\0name', 'z' * 201]:
        assert download(client, school_data['code'], school_label=invalid).status_code == 400
    assert len(exports) == 3


def test_download_uses_custom_label_in_slides_and_registered_name_in_notes(client, school_data):
    from pptx import Presentation

    response = download(client, school_data['code'], school_label='SAC')
    assert response.status_code == 200
    deck = Presentation(BytesIO(response.data))
    headers = [shape.text for slide in deck.slides for shape in slide.shapes if shape.name == 'school']
    assert headers == ['SAC'] * (len(deck.slides) - 1)
    assert all('Slides School' in slide.notes_slide.notes_text_frame.text for slide in deck.slides)


def test_public_export_uses_latest_nonempty_results_and_school_totals(client, school_data, exports):
    add = school_data['session']
    add('Earlier lunch', 1, (0, 0, 3, 1))
    add('Middle lunch', 2, (2, 2, 4, 0), status='archived')
    add('Latest lunch', 3, (4, 2, 1, 1))
    add('Empty future lunch', 4, (None, None, None, None))
    add('Discarded private lunch', 5, (500, 500, 2, 4), public=0, status='discarded')
    other = School(id='other-' + school_data['id'], name='Other school', slug='other-' + school_data['code'])
    db_session.add(other)
    db_session.flush()
    peer = db_session.query(Session).filter_by(school_id=school_data['id']).first()
    db_session.add(Session(school_id=other.id, created_by=peer.created_by, session_name='Other private lunch',
                           clean_number=1000, is_public=0))
    db_session.commit()

    response = download(client, ' ' + school_data['code'].swapcase() + ' ', format='google-slides', theme='dark')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Content-Disposition'].endswith('.pptx"')
    assert response.mimetype.endswith('.presentationml.presentation')
    assert len(exports) == 1
    kind, theme, data, platform = exports[0]
    assert (kind, theme, platform) == ('assembly', 'dark', 'google-slides')
    assert data['milestone'] == 100
    assert data['totals'] == {'student_clean': 6, 'faculty_clean': 4, 'clean': 10, 'dirty': 8, 'very_dirty': 2,
                              'total': 20, 'clean_percentage': 50.0, 'session_count': 3}
    assert data['latest'] == {'name': 'Latest lunch', 'date': '2026-10-04', 'student_clean': 4, 'faculty_clean': 2,
                              'clean': 6, 'dirty': 1, 'very_dirty': 1, 'total': 8, 'clean_percentage': 75.0}
    assert data['previous']['name'] == 'Middle lunch'
    assert data['change'] == {'clean': 2, 'total': 0, 'clean_percentage_points': 25.0, 'clean_relative_percent': 50.0}
    assert 'Other private lunch' not in str(data)
    assert 'Internal Member' not in str(data)
    assert school_data['username'] not in str(data)


def test_changed_access_guest_and_cross_school_never_render_private_deck(client, login, school_data, exports):
    code = school_data['code']
    row_id = school_data['session']('Lunch', 3, (4, None, 1, None))
    assert download(client, code).status_code == 200

    # Either privacy control is enough to require school membership.
    school = db_session.get(School, school_data['id'])
    school.guest_privacy_enabled = 1
    db_session.commit()
    assert download(client, code).status_code == 401
    school = db_session.get(School, school_data['id'])
    school.guest_privacy_enabled = 0
    db_session.get(Session, row_id).is_public = 0
    db_session.commit()
    assert client.post('/api/auth/guest', json={'school_slug': code}).status_code == 200
    response = download(client, code, format='pdf')
    assert response.status_code == 401 and response.json['code'] == 'SCHOOL_LOGIN_REQUIRED'
    assert login().status_code == 200  # superadmin of a different school
    response = download(client, code, format='google-slides', kind='overview', theme='dark')
    assert response.status_code == 403 and response.json['code'] == 'WRONG_SCHOOL_ACCOUNT'
    assert len(exports) == 1

    assert client.post('/api/auth/login', json={'username': school_data['username'],
                                                'password': 'member-password'}).status_code == 200
    response = download(client, code, kind='overview', format='pdf')
    assert response.status_code == 200 and response.mimetype == 'application/pdf'
    assert response.headers['Content-Disposition'].endswith('.pdf"')
    assert exports[-1][0] == 'overview' and exports[-1][-1] == 'pdf'
    assert exports[-1][2]['latest']['name'] == 'Lunch'


def test_empty_first_and_zero_baseline_results(client, school_data, exports):
    download(client, school_data['code'])
    data = exports[-1][2]
    assert data['latest'] is data['previous'] is data['change'] is None
    assert data['totals']['total'] == data['totals']['session_count'] == 0

    school_data['session']('First', 1, (None, None, 1, 0))
    download(client, school_data['code'])
    data = exports[-1][2]
    assert data['latest']['name'] == 'First' and data['previous'] is data['change'] is None

    school_data['session']('Second', 2, (1, 2, 3, 0))
    download(client, school_data['code'])
    delta = exports[-1][2]['change']
    assert delta == {'clean': 3, 'total': 5, 'clean_percentage_points': 50, 'clean_relative_percent': None}
    school_data['session']('Third', 3, (0, 0, 1, 0))
    download(client, school_data['code'])
    assert exports[-1][2]['change'] == {'clean': -3, 'total': -5, 'clean_percentage_points': -50,
                                        'clean_relative_percent': -100}


def test_email_verification_gate_only_applies_to_private_results(client, school_data, exports):
    session_id = school_data['session']('Lunch', 3, (4, 1, 1, 0))
    school = db_session.get(School, school_data['id'])
    school.signup_email_policy = json.dumps({'enabled': True, 'allowed_domains': ['school.example'], 'exceptions': []})
    db_session.commit()
    login = client.post('/api/auth/login', json={'username': school_data['username'], 'password': 'member-password'})
    assert login.get_json()['user']['email_required']
    assert download(client, school_data['code']).status_code == 200
    db_session.get(Session, session_id).is_public = 0
    db_session.commit()
    denied = download(client, school_data['code'])
    assert denied.status_code == 403 and denied.get_json()['code'] == 'ACCOUNT_EMAIL_REQUIRED'
    assert len(exports) == 1


def test_input_validation_and_disabled_schools(client, school_data):
    for key, value in [('school_code', []), ('theme', ['dark']), ('format', 'xlsx'), ('kind', 'unknown')]:
        assert download(client, school_data['code'], **{key: value}).status_code == 400
    for invalid in ('unknown-code', INTERSCHOOL_SCHOOL_SLUG):
        assert download(client, invalid).status_code == 404
    school = db_session.get(School, school_data['id'])
    school.status = 'disabled'
    db_session.commit()
    assert download(client, school_data['code']).status_code == 404


@pytest.mark.parametrize(('kind', 'theme', 'output'), [
    ('overview', 'light', 'pptx'), ('assembly', 'dark', 'google-slides'), ('assembly', 'dark', 'pdf'),
])
def test_real_export_contains_current_school_results(client, school_data, kind, theme, output):
    school_data['session']('Monday lunch', 3, (12, 2, 5, 1))
    school_data['session']('Tuesday lunch', 4, (15, 1, 2, 2))
    response = download(client, school_data['code'], kind=kind, theme=theme, format=output)
    assert response.status_code == 200
    if output == 'pdf':
        assert response.data.startswith(b'%PDF-') and response.data.rstrip().endswith(b'%%EOF')
    else:
        with ZipFile(BytesIO(response.data)) as presentation:
            cover = presentation.read('ppt/slides/slide1.xml')
            assert b'Slides School' in cover and b'Tuesday lunch' in cover
            if kind == 'assembly':
                assert b'Monday lunch' in presentation.read('ppt/slides/slide3.xml')
            else:
                assert 'ppt/slides/slide2.xml' not in presentation.namelist()
