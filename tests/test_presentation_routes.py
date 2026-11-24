import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile

import pytest

from src.routes.golden_plate_recorder_db.db import (
    INTERSCHOOL_SCHOOL_SLUG, School, Session, SessionDrawEvent, SessionRecord, Student, Teacher, User,
    db_session, _now_utc,
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
    school_id, user_id = school.id, user.id

    def session(name, day, counts, public=1, status='active'):
        row = Session(school_id=school_id, session_name=name, created_by=user_id, is_public=public,
                      status=status, created_at=datetime(2026, 10, day, 20, tzinfo=timezone.utc),
                      clean_number=counts[0], faculty_number=counts[1], dirty_number=counts[2], red_number=counts[3])
        db_session.add(row)
        db_session.commit()
        return row.id

    return {'code': school.slug, 'id': school_id, 'user_id': user_id, 'username': user.username, 'session': session}


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
    assert headers == ['SAC'] * (len(deck.slides) - 3)  # The intro, closing message and logo outro omit the school header.
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
    assert data['reporting_timezone'] == 'Asia/Tokyo'
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


def test_winner_names_follow_the_latest_lunch_and_school_access(client, school_data, exports):
    from src.routes.golden_plate_recorder_db.presentation_routes import assembly_snapshot_for_owner

    lunch = school_data['session']('Main lunch', 2, (12, 1, 0, 0))
    extra = school_data['session']('Extra sitting', 3, (5, 0, 0, 0))
    winner = Student(school_id=school_data['id'], student_identifier='private-roster-code',
                     preferred_name='Riley', last_name='Chen', grade='10', house='Maple - Elm', clan='Sun')
    db_session.add(winner)
    db_session.flush()
    winner_id = winner.id
    meal = db_session.get(Session, lunch)
    meal.finalized, meal.winner_student_id = 1, winner_id
    meal.tickets_at_selection, meal.probability_at_selection = 4, 1250
    meal.eligible_pool_size, meal.method = 18, 'random'
    meal.faculty_pick_display_name = 'Morgan Ellis'
    db_session.add_all([
        SessionDrawEvent(school_id=school_data['id'], session_id=lunch, draw_number=meal.draw_number,
                         event_type='draw', selected_student_id=winner_id, tickets_at_event=4.5,
                         probability_at_event=1250, eligible_pool_size=18, comment='private draw note'),
        SessionDrawEvent(school_id=school_data['id'], session_id=lunch, draw_target='faculty',
                         event_type='override', faculty_name='Morgan Ellis', tickets_at_event=0,
                         probability_at_event=0, eligible_pool_size=0),
    ])
    db_session.get(Session, extra).main_session_id = lunch
    db_session.commit()

    def snapshot(**options):
        assert download(client, school_data['code'], **options).status_code == 200
        return exports[-1][2]

    assert 'winner_names' not in snapshot()
    assert client.post('/api/auth/login', json={'username': school_data['username'],
                                                'password': 'member-password'}).status_code == 200
    assert snapshot()['winner_names'] == {'student': 'Riley Chen'}
    db_session.get(Session, lunch).faculty_finalized = 1
    db_session.commit()
    data = snapshot()
    assert data['winner_names'] == {'student': 'Riley Chen', 'faculty': 'Morgan Ellis'}
    assert data['winner_details'] == {
        'student': {'tickets': 4.5, 'probability': 12.5, 'pool_size': 18, 'method': 'random',
                    'grade': '10', 'house': 'Maple', 'clan': 'Sun', 'next_ticket_gain': 1},
        'faculty': {'tickets': 0, 'probability': 0, 'pool_size': 0, 'method': 'manual'},
    }
    assert data['latest']['name'] == 'Extra sitting'
    assert len(set(data['winner_keys'].values())) == 2
    assert all(len(value) == 64 for value in data['winner_keys'].values())
    assert all(private not in str(data) for private in (winner_id, 'private-roster-code', 'private draw note'))
    owner = (school_data['id'], school_data['user_id'])
    live = assembly_snapshot_for_owner(*owner, with_winners=True)
    assert live['winner_names'] == data['winner_names'] and live['winner_keys'] == data['winner_keys']
    assert live['winner_details'] == data['winner_details']
    assert 'winner_names' not in assembly_snapshot_for_owner(*owner)
    assert 'winner_names' not in snapshot(kind='overview') and 'winner_names' not in snapshot(format='google-slides')
    new_lunch = school_data['session']('Next lunch', 4, (8, 2, 0, 0))
    assert 'winner_names' not in snapshot()
    next_meal = db_session.get(Session, new_lunch)
    next_meal.finalized, next_meal.winner_student_id = 1, winner_id
    db_session.commit()
    assert snapshot()['winner_keys']['student'] != data['winner_keys']['student']


def test_draw_details_follow_current_person_role_and_round(school_data):
    from src.routes.golden_plate_recorder_db.presentation_routes import assembly_snapshot_for_owner

    school_id, owner = school_data['id'], school_data['user_id']
    lunch = school_data['session']('Results', 2, (4, 2, 0, 0))
    winner = Student(school_id=school_id, student_identifier='winner', preferred_name='Sam', last_name='Lee')
    other = Student(school_id=school_id, student_identifier='other', preferred_name='Other', last_name='Student')
    teacher = Teacher(school_id=school_id, name='Morgan Ellis')
    peer = School(id='peer-' + school_id, name='Other school', slug='peer-' + school_data['code'])
    db_session.add_all([winner, other, teacher, peer])
    db_session.flush()
    record = SessionRecord(school_id=school_id, session_id=lunch, teacher_id=teacher.id, category='faculty',
                           recorded_by=owner, dedupe_key='faculty-slot')
    db_session.add(record)
    db_session.flush()
    draw = db_session.get(Session, lunch)
    draw.winner_student_id, draw.finalized, draw.draw_number = winner.id, 1, 2
    draw.tickets_at_selection, draw.probability_at_selection, draw.override_applied = 0, 0, 1
    draw.faculty_finalized, draw.faculty_pick_teacher_id, draw.faculty_pick_record_id = 1, teacher.id, record.id
    draw.faculty_pick_display_name = 'Morgan Ellis'
    db_session.add_all([
        SessionDrawEvent(school_id=school_id, session_id=lunch, draw_number=1, event_type='draw',
                         selected_student_id=winner.id, tickets_at_event=999),
        SessionDrawEvent(school_id=school_id, session_id=lunch, draw_number=2, event_type='draw',
                         selected_student_id=other.id, tickets_at_event=888),
        SessionDrawEvent(school_id=peer.id, session_id=lunch, draw_number=2, event_type='draw',
                         selected_student_id=winner.id, tickets_at_event=777,
                         created_at=datetime(2027, 1, 1, tzinfo=timezone.utc)),
        # Early faculty events were typed as student events and identified by the selected record.
        SessionDrawEvent(school_id=school_id, session_id=lunch, draw_number=2, event_type='draw',
                         selected_record_id=record.id, tickets_at_event=3, probability_at_event=625, eligible_pool_size=9),
    ])
    db_session.commit()

    def results():
        return assembly_snapshot_for_owner(school_id, owner, with_winners=True)['winner_details']

    assert results() == {'student': {'tickets': 0, 'probability': 0, 'method': 'manual', 'next_ticket_gain': 1},
                         'faculty': {'tickets': 3, 'probability': 6.25, 'pool_size': 9, 'method': 'random',
                                     'next_ticket_gain': 2}}
    db_session.add(SessionDrawEvent(school_id=school_id, session_id=lunch, draw_number=2,
                                    draw_target='faculty', event_type='restore'))
    db_session.commit()
    assert results()['faculty'] == {'next_ticket_gain': 2}
    db_session.add(SessionDrawEvent(school_id=school_id, session_id=lunch, draw_number=2, draw_target='faculty',
                                    event_type='override', faculty_name='Another person', tickets_at_event=777))
    db_session.commit()
    assert results()['faculty'] == {'next_ticket_gain': 2}


@pytest.mark.parametrize('scope', ['roster', 'manual_teacher', 'legacy_name'])
def test_current_ticket_gain_uses_the_post_finalization_draw_state(client, school_data, exports, monkeypatch, scope):
    from src.routes.golden_plate_recorder_db import presentation_routes as routes

    school, owner = school_data['id'], school_data['user_id']
    manual = scope != 'roster'
    pupil = Student(school_id=school, preferred_name='Riley', last_name='Chen', student_identifier='riley',
                    is_active=int(not manual))
    db_session.add(pupil)
    teacher = Teacher(school_id=school, name='Morgan Ellis', is_active=int(not manual)) if scope != 'legacy_name' else None
    if teacher:
        db_session.add(teacher)
    db_session.flush()
    pupil_id, teacher_id = pupil.id, teacher.id if teacher else None
    main = school_data['session']('Main', 1, (1, 1, 0, 0))

    def record_clean_lunch(day):
        meal = main if day == 1 else school_data['session'](f'Extra {day}', day, (1, 1, 0, 0))
        if meal != main:
            db_session.get(Session, meal).main_session_id = main
        at = datetime(2026, 10, day, 21, tzinfo=timezone.utc)
        shared = dict(school_id=school, session_id=meal, recorded_by=owner, recorded_at=at)
        student_plate = SessionRecord(**shared, student_id=pupil_id, category='clean', is_manual_entry=int(manual),
                                      dedupe_key='riley')
        faculty_plate = SessionRecord(**shared, teacher_id=teacher_id, category='faculty', preferred_name='Morgan',
                                     last_name='Ellis', faculty_roster_entry=int(not manual), dedupe_key='morgan')
        db_session.add_all([student_plate, faculty_plate])
        db_session.flush()
        faculty_record_id = faculty_plate.id
        db_session.commit()
        return faculty_record_id

    for day in (1, 2, 3):
        last_record = record_clean_lunch(day)
    draw = db_session.get(Session, main)
    draw.finalized = draw.faculty_finalized = 1
    draw.winner_student_id = pupil_id
    draw.faculty_pick_display_name = 'Morgan Ellis'
    draw.faculty_pick_teacher_id = teacher_id
    draw.faculty_pick_record_id = None if scope == 'legacy_name' else last_record
    win = dict(school_id=school, session_id=main, draw_number=1, event_type='finalize',
               created_at=datetime(2026, 10, 3, 22, tzinfo=timezone.utc), combo_round_up=0)
    db_session.add_all([SessionDrawEvent(**win, selected_student_id=pupil_id),
                        SessionDrawEvent(**win, draw_target='faculty', selected_teacher_id=teacher_id,
                                         selected_record_id=last_record, faculty_ticket_scope='session' if manual else 'roster')])
    db_session.commit()

    calls = []
    replay = routes.replay_school_tickets

    def capture_replay(school_id):
        calls.append(school_id)
        return replay(school_id)

    monkeypatch.setattr(routes, 'replay_school_tickets', capture_replay)
    assert download(client, school_data['code']).status_code == 200
    assert 'winner_details' not in exports[-1][2]
    assert 'winner_details' not in routes.assembly_snapshot_for_owner(school, owner)
    assert calls == []

    expected = {'student': {'next_ticket_gain': 2}, 'faculty': {'next_ticket_gain': 2}}
    assert routes.assembly_snapshot_for_owner(school, owner, with_winners=True)['winner_details'] == expected
    assert calls == [school]
    assert client.post('/api/auth/login', json={'username': school_data['username'],
                                                'password': 'member-password'}).status_code == 200
    assert download(client, school_data['code']).status_code == 200
    assert exports[-1][2]['winner_details'] == expected and calls == [school, school]
    record_clean_lunch(4)
    assert routes.assembly_snapshot_for_owner(school, owner, with_winners=True)['winner_details'] == {
        'student': {'next_ticket_gain': 3}, 'faculty': {'next_ticket_gain': 3},
    }
    if scope == 'legacy_name':
        db_session.get(Session, main).faculty_pick_record_id = 'unmatched-record'
        db_session.commit()
        current = routes.assembly_snapshot_for_owner(school, owner, with_winners=True)
        assert current['winner_names']['faculty'] == 'Morgan Ellis'
        assert 'next_ticket_gain' not in current['winner_details'].get('faculty', {})


def test_public_results_keep_winner_identities_school_scoped(client, login, school_data, exports):
    from src.routes.golden_plate_recorder_db.presentation_routes import assembly_snapshot_for_owner

    lunch = school_data['session']('Public lunch', 1, (8, 2, 0, 0))
    draw = db_session.get(Session, lunch)
    draw.faculty_finalized, draw.faculty_pick_display_name = 1, 'Avery Patel'
    db_session.add(SessionDrawEvent(school_id=school_data['id'], session_id=lunch, draw_target='faculty',
                                    event_type='draw', faculty_name='Avery Patel', tickets_at_event=7))
    db_session.commit()

    def check_public_results():
        assert download(client, school_data['code']).status_code == 200
        data = exports[-1][2]
        assert data['latest']['name'] == 'Public lunch'
        assert not {'winner_names', 'winner_keys', 'winner_details'}.intersection(data)
        assert 'Avery Patel' not in str(data)

    assert client.post('/api/auth/guest', json={'school_slug': school_data['code']}).status_code == 200
    check_public_results()
    assert login().status_code == 200  # This superadmin belongs to a different school.
    check_public_results()
    with client.session_transaction() as session:
        outsider_id = session['user_uuid']
    assert assembly_snapshot_for_owner(school_data['id'], outsider_id, with_winners=True) is None

    school = db_session.get(School, school_data['id'])
    school.signup_email_policy = json.dumps({'enabled': True, 'allowed_domains': ['school.example'], 'exceptions': []})
    member = db_session.get(User, school_data['user_id'])
    member.email, member.email_verified_at = 'teacher@school.example', None
    db_session.commit()
    assert client.post('/api/auth/login', json={'username': school_data['username'],
                                                'password': 'member-password'}).json['user']['email_required']
    check_public_results()
    assert assembly_snapshot_for_owner(school_data['id'], school_data['user_id'], with_winners=True) is None


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
