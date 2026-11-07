import io
import os
import subprocess
import sys
import uuid

import pytest

from src.routes.golden_plate_recorder_db.db import (
    DraftPool, School, Session, SessionDrawEvent, SessionRecord, SessionTicketEvent,
    Student, Teacher, db_session,
)
from src.routes.golden_plate_recorder_db.ticket_combos import halve_combo, initialize_ticket_combos
from src.routes.golden_plate_recorder_db.draw_db import record_ticket_event
from src.routes.golden_plate_recorder_db.users import create_user_record


@pytest.fixture
def combo_school(client):
    client.get('/api/auth/status')
    school_id = uuid.uuid4().hex
    db_session.add(School(id=school_id, slug=school_id, name='Combo School'))
    db_session.commit()
    account = create_user_record(uuid.uuid4().hex, 'test-password', 'Combo Admin',
                                 role='superadmin', school_id=school_id)
    assert client.post('/api/auth/login', json={'username': account.username, 'password': 'test-password'}).status_code == 200
    roster = b'Student ID,Last,Preferred,House\ncombo-1,Student,Alex,Oak\ncombo-2,Student,Jordan,Elm'
    assert client.post('/api/csv/upload', data={'file': (io.BytesIO(roster), 'students.csv')}).status_code == 200
    faculty = b'Faculty ID,First,Last\ncombo-teacher,Riley,Teacher'
    assert client.post('/api/teachers/upload', data={'file': (io.BytesIO(faculty), 'teachers.csv')}).status_code == 200
    return school_id


def meal(client):
    response = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex})
    assert response.status_code == 200
    return response.get_json()['session_id']


def record(client, category='clean', name='combo-1'):
    result = client.post(f'/api/record/{category}', json={'input_value': name})
    assert result.status_code == 200, result.get_json()


def both_clean(client):
    session_id = meal(client)
    record(client)
    record(client, 'faculty', 'Riley Teacher')
    return session_id


def stats(client, group='students'):
    return client.get('/api/leaderboards').get_json()['historical_tickets'][group][0]['stats']


def summary(client, session_id):
    result = client.get(f'/api/session/{session_id}/draw/summary')
    assert result.status_code == 200
    return result.get_json()


def test_consecutive_rewards_and_every_display_use_the_same_combo(client, combo_school):
    for total, next_gain in [(1, 2), (3, 3), (6, 4)]:
        session_id = both_clean(client)
        for group in ('students', 'faculty'):
            current = stats(client, group)
            assert (current['tickets'], current['historical_tickets'], current['next_ticket_gain']) == (total, total, next_gain)
        data = summary(client, session_id)
        for candidate in [data['candidates'][0], data['top_candidates'][0], data['faculty_draw']['candidates'][0]]:
            assert (candidate['tickets'], candidate['next_ticket_gain']) == (total, next_gain)
        assert data['total_tickets'] == data['faculty_draw']['total_tickets'] == total
    assert client.get('/api/leaderboards').get_json()['historical_tickets']['students'][1]['stats']['next_ticket_gain'] == 1


@pytest.mark.parametrize('category, balance', [('dirty', 4), ('red', 1)])
def test_nonclean_plates_reset_only_combo_unless_red(client, combo_school, category, balance):
    both_clean(client)
    both_clean(client)
    meal(client)
    record(client, category)
    assert stats(client)['next_ticket_gain'] == 1
    meal(client)
    record(client)
    current = stats(client)
    assert (current['tickets'], current['historical_tickets'], current['next_ticket_gain']) == (balance, 4, 2)


def test_missing_session_breaks_combo_but_an_open_session_is_still_an_opportunity(client, combo_school):
    both_clean(client)
    both_clean(client)
    missing = meal(client)
    record(client, name='combo-2')
    # Alex and Riley can still record in the latest open session.
    assert stats(client)['next_ticket_gain'] == stats(client, 'faculty')['next_ticket_gain'] == 3
    next_meal = meal(client)
    assert next_meal != missing
    assert stats(client)['next_ticket_gain'] == stats(client, 'faculty')['next_ticket_gain'] == 1
    record(client)
    record(client, 'faculty', 'Riley Teacher')
    assert stats(client)['tickets'] == stats(client, 'faculty')['tickets'] == 4


@pytest.mark.parametrize('combo, expected', [(1, (1, 1)), (2, (1, 1)), (5, (2, 3)), (6, (3, 3)), (10, (5, 5))])
def test_halving_keeps_integers_and_a_minimum_one(combo, expected):
    assert (halve_combo(combo, 0), halve_combo(combo, 1)) == expected


@pytest.mark.parametrize('round_up, expected_gain', [(0, 2), (1, 3)])
def test_wins_store_rounding_and_reset_tickets_without_erasing_earned_history(client, combo_school, monkeypatch, round_up, expected_gain):
    for _ in range(4):
        session_id = both_clean(client)
    assert stats(client)['next_ticket_gain'] == stats(client, 'faculty')['next_ticket_gain'] == 5
    assert client.post(f'/api/session/{session_id}/draw/override', json={'student_identifier': 'combo-1'}).status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/pick').status_code == 200
    monkeypatch.setattr('src.routes.golden_plate_recorder_db.db.secrets.randbits', lambda _: round_up)
    for target in ('draw', 'faculty'):
        assert client.post(f'/api/session/{session_id}/{target}/finalize').status_code == 200
    for group in ('students', 'faculty'):
        current = stats(client, group)
        assert (current['tickets'], current['historical_tickets'], current['next_ticket_gain']) == (0, 10, expected_gain)
    assert [event.combo_round_up for event in db_session.query(SessionDrawEvent).filter_by(
        school_id=combo_school, event_type='finalize',
    )] == [round_up, round_up]
    # Startup and refresh must reuse the saved coin, even when RNG changes.
    monkeypatch.setattr('src.routes.golden_plate_recorder_db.db.secrets.randbits', lambda _: 1 - round_up)
    # A fresh import follows the deployed WSGI initialization path.
    env = {**os.environ, 'WEBSITE_RELEASE_NOTIFY_ENABLED': 'false',
           'ACCOUNT_LIFECYCLE_WORKER_ENABLED': 'false'}
    started = subprocess.run([sys.executable, '-c', 'import src.main'],
                             env=env, capture_output=True, text=True, timeout=30)
    assert started.returncode == 0, started.stderr
    db_session.remove()
    initialize_ticket_combos()
    assert stats(client)['next_ticket_gain'] == stats(client, 'faculty')['next_ticket_gain'] == expected_gain
    both_clean(client)
    for group in ('students', 'faculty'):
        current = stats(client, group)
        assert (current['tickets'], current['historical_tickets'], current['next_ticket_gain']) == (
            expected_gain, 10 + expected_gain, expected_gain + 1)


def test_merged_sessions_each_advance_student_and_teacher_combos(client, combo_school):
    main = both_clean(client)
    extra = both_clean(client)
    assert client.post(f'/api/session/{extra}/merge', json={'main_session_id': main}).status_code == 200
    data = summary(client, main)
    assert data['total_tickets'] == data['faculty_draw']['total_tickets'] == 3
    assert data['candidates'][0]['next_ticket_gain'] == data['faculty_draw']['candidates'][0]['next_ticket_gain'] == 3
    assert data['top_candidates'] == data['candidates']


def test_excluding_and_restoring_old_plates_recalculates_later_combos(client, combo_school):
    first = both_clean(client)
    both_clean(client)
    last = both_clean(client)
    for category, group in [('clean', 'students'), ('faculty', 'faculty')]:
        target_id = db_session.query(SessionRecord).filter_by(session_id=first, category=category).one().id
        url = f'/api/session/{first}/records/{target_id}/exclusion'
        assert client.post(url, json={'excluded': True, 'reason': 'Incorrect scan'}).status_code == 200
        current = stats(client, group)
        assert (current['tickets'], current['historical_tickets'], current['next_ticket_gain']) == (3, 3, 3)
        assert client.post(url, json={'excluded': False}).status_code == 200
        assert stats(client, group)['tickets'] == 6
    assert summary(client, last)['candidates'][0]['tickets'] == 6


def test_discard_and_restore_replays_both_categories(client, combo_school):
    both_clean(client)
    middle = both_clean(client)
    last = both_clean(client)
    url = f'/api/session/{middle}/draw/discard'
    assert client.post(url, json={'discarded': True}).status_code == 200
    for group in ('students', 'faculty'):
        assert stats(client, group)['tickets'] == 3
    assert summary(client, last)['total_tickets'] == 3
    assert client.post(url, json={'discarded': False}).status_code == 200
    for group in ('students', 'faculty'):
        assert stats(client, group)['tickets'] == 6


def test_startup_upgrades_old_pool_and_ledger_once_without_changing_plate_or_winner_history(client, combo_school):
    for _ in range(3):
        session_id = both_clean(client)
    student_id = db_session.query(Student).filter_by(school_id=combo_school, student_identifier='combo-1').one().id
    # Simulate the old one-ticket-per-clean-plate storage.
    db_session.query(Student).filter_by(id=student_id).update({'ticket_legacy_balance': None})
    db_session.query(DraftPool).filter_by(student_id=student_id).update({'ticket_number': 3})
    events = db_session.query(SessionTicketEvent).filter_by(student_id=student_id).order_by(SessionTicketEvent.occurred_at).all()
    for index, event in enumerate(events, 1):
        event.tickets_delta, event.ticket_balance_after = 1, index
    original = [(row.id, row.category, row.recorded_at) for row in db_session.query(SessionRecord).filter_by(school_id=combo_school)]
    db_session.commit()
    initialize_ticket_combos()
    initialize_ticket_combos()
    assert stats(client)['tickets'] == stats(client, 'faculty')['tickets'] == 6
    assert db_session.query(DraftPool).filter_by(student_id=student_id).one().ticket_number == 6
    assert [row.tickets_delta for row in db_session.query(SessionTicketEvent).filter_by(
        student_id=student_id).order_by(SessionTicketEvent.occurred_at)] == [1, 2, 3]
    assert [(row.id, row.category, row.recorded_at) for row in db_session.query(SessionRecord).filter_by(school_id=combo_school)] == original
    assert summary(client, session_id)['top_candidates'][0]['next_ticket_gain'] == 4


def test_manual_participants_have_combos_within_merged_scope_and_start_fresh_next_time(client, combo_school):
    ids = []
    for _ in range(2):
        ids.append(meal(client))
        record(client, name='Manual Student')
        record(client, 'faculty', 'Manual Teacher')
    assert client.post(f'/api/session/{ids[1]}/merge', json={'main_session_id': ids[0]}).status_code == 200
    data = summary(client, ids[0])
    assert data['candidates'][0]['tickets'] == data['faculty_draw']['candidates'][0]['tickets'] == 3
    new = meal(client)
    record(client, name='Manual Student')
    record(client, 'faculty', 'Manual Teacher')
    data = summary(client, new)
    assert data['candidates'][0]['tickets'] == data['faculty_draw']['candidates'][0]['tickets'] == 1
    assert stats(client)['tickets'] == 0


def test_another_schools_sessions_never_break_the_combo(client, combo_school):
    both_clean(client)
    other = uuid.uuid4().hex
    owner_id = db_session.query(Session.created_by).filter_by(school_id=combo_school).first()[0]
    db_session.add(School(id=other, slug=other, name='Other School'))
    db_session.flush()
    db_session.add(Session(school_id=other, session_name='Foreign meal', created_by=owner_id))
    db_session.commit()
    both_clean(client)
    assert stats(client)['tickets'] == stats(client, 'faculty')['tickets'] == 3


def test_independent_reset_before_a_clean_scan_does_not_consume_the_new_reward(client, combo_school):
    session_id = meal(client)
    student = db_session.query(Student).filter_by(school_id=combo_school, student_identifier='combo-1').one()
    student.ticket_legacy_balance = None
    record_ticket_event(session_id, student.id, 'reset', -10, 0)
    db_session.commit()
    record(client)
    current = stats(client)
    assert (current['tickets'], current['historical_tickets'], current['next_ticket_gain']) == (1, 11, 2)


@pytest.mark.parametrize('round_up, expected_gain', [(0, 2), (1, 3)])
def test_deleted_faculty_draw_keeps_its_saved_rounding_choice(client, combo_school, monkeypatch, round_up, expected_gain):
    for _ in range(5):
        winning_meal = both_clean(client)
    monkeypatch.setattr('src.routes.golden_plate_recorder_db.db.secrets.randbits', lambda _: round_up)
    assert client.post(f'/api/session/{winning_meal}/faculty/pick').status_code == 200
    assert client.post(f'/api/session/{winning_meal}/faculty/finalize').status_code == 200
    both_clean(client)
    assert stats(client, 'faculty')['tickets'] == 3
    assert client.delete(f'/api/session/delete/{winning_meal}').status_code == 200
    # Removing that meal changes the pre-win combo from 6 to 5. The original
    # saved coin must determine rounding, even though the event was deleted.
    assert stats(client, 'faculty')['tickets'] == expected_gain
    initialize_ticket_combos()
    assert stats(client, 'faculty')['tickets'] == expected_gain
