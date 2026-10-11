import io
import uuid

import pytest

from src.routes.golden_plate_recorder_db.db import (
    DraftPool, RecordExclusionEvent, RosterSnapshot, School, Session, SessionDrawEvent, SessionRecord,
    Student, db_session,
)
from src.routes.golden_plate_recorder_db.draw_db import get_student_ticket_balance
from src.routes.golden_plate_recorder_db.storage import get_session_entry
from src.routes.golden_plate_recorder_db.users import create_user_record


@pytest.fixture
def school(client):
    client.get('/api/auth/status')
    school = School(id=uuid.uuid4().hex, name='Exclusion School', slug=uuid.uuid4().hex)
    db_session.add(school)
    db_session.commit()
    account = create_user_record(uuid.uuid4().hex, 'test-password', 'Superadmin',
                                 role='superadmin', school_id=school.id)
    assert client.post('/api/auth/login', json={'username': account.username, 'password': 'test-password'}).status_code == 200
    upload(client)
    return school


def upload(client, identifiers=('9100', '9101')):
    text = 'Student ID,Last,Preferred,House\n'
    text += ''.join(f'{identifier},Student,Name{identifier},A\n' for identifier in identifiers)
    assert client.post('/api/csv/upload', data={'file': (io.BytesIO(text.encode()), 'students.csv')}).status_code == 200


def create(client):
    result = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex})
    assert result.status_code == 200
    return result.get_json()['session_id']


def record(client, session_id, category='clean', identifier='9100'):
    assert client.post(f'/api/record/{category}', json={'input_value': identifier}).status_code == 200
    return db_session.query(SessionRecord).filter_by(session_id=session_id, category=category).order_by(
        SessionRecord.recorded_at.desc()).first().id


def exclude(client, session_id, record_id, value=True, **extra):
    return client.post(f'/api/session/{session_id}/records/{record_id}/exclusion',
                       json={'excluded': value, 'reason': 'Roster correction', **extra})


def stats(client, session_id):
    result = client.get(f'/api/session/{session_id}/house-stats')
    assert result.status_code == 200
    return result.get_json()


def test_legacy_review_finds_current_roster_conflict_before_manual_matching(client, school):
    upload(client, ['9100', '9101', '9102'])
    session_id = create(client)
    record(client, session_id)
    outsider_id = record(client, session_id, identifier='9102')
    upload(client)
    meal = db_session.get(Session, session_id)
    meal.roster_snapshot_id = None  # A historical session with no saved roster.
    meal.roster_mixed = 0
    db_session.commit()
    snapshot_count = db_session.query(RosterSnapshot).count()
    assert 'no historical roster' in stats(client, session_id)['estimation']['reason']
    attempt = client.post(f'/api/session/{session_id}/roster/current')
    assert attempt.status_code == 400
    assert 'not in the current roster' in attempt.get_json()['error']
    review = client.get(f'/api/session/{session_id}/calculation-records').get_json()
    assert review['roster_review'] == {'source': 'current', 'filename': 'students.csv',
                                      'available': True, 'has_saved_roster': False}
    outsider = next(row for row in review['records'] if row['record_id'] == outsider_id)
    assert outsider['issue'] == 'Student is not in the current roster.'
    assert db_session.get(Session, session_id).roster_snapshot_id is None
    assert db_session.query(RosterSnapshot).count() == snapshot_count
    assert exclude(client, session_id, outsider_id).status_code == 200
    # Reviewing and excluding cannot attest the historical roster for the user.
    assert not stats(client, session_id)['estimation']['available']
    assert client.post(f'/api/session/{session_id}/roster/current').status_code == 200
    assert stats(client, session_id)['estimation']['available']
    review = client.get(f'/api/session/{session_id}/calculation-records').get_json()
    assert review['roster_review']['source'] == 'saved'
    assert review['roster_review']['has_saved_roster']


def test_review_can_compare_current_roster_without_changing_saved_history(client, school):
    upload(client, ['9100', '9101', '9102'])
    session_id = create(client)
    outsider_id = record(client, session_id, identifier='9102')
    snapshot_id = db_session.get(Session, session_id).roster_snapshot_id
    upload(client)
    before = stats(client, session_id)['estimation']
    assert before['available'] and before['population'] == 3
    saved = client.get(f'/api/session/{session_id}/calculation-records').get_json()
    assert saved['roster_review']['source'] == 'saved'
    assert saved['records'][0]['issue'] is None
    current_url = f'/api/session/{session_id}/calculation-records?roster=current'
    current = client.get(current_url).get_json()
    assert current['roster_review']['has_saved_roster']
    assert current['roster_review']['source'] == 'current'
    assert current['records'][0]['issue'] == 'Student is not in the current roster.'
    result = client.post(f'/api/session/{session_id}/records/{outsider_id}/exclusion?roster=current',
                         json={'excluded': True})
    assert result.status_code == 200
    assert result.get_json()['roster_review']['source'] == 'current'
    assert result.get_json()['records'][0]['is_excluded']
    assert db_session.get(Session, session_id).roster_snapshot_id == snapshot_id
    assert stats(client, session_id)['estimation']['population'] == 2


def test_current_roster_review_finds_house_conflicts_but_not_anonymous_counts(client, school):
    session_id = create(client)
    record(client, session_id)
    record(client, session_id, category='dirty', identifier='')
    student = db_session.query(Student).filter_by(school_id=school.id, student_identifier='9100').one()
    student.house = 'B'
    db_session.commit()
    result = client.get(f'/api/session/{session_id}/calculation-records?roster=current').get_json()
    assert result['records'][0]['issue'] == 'Recorded house conflicts with the current roster.'
    assert result['records'][1]['is_count_only'] and result['records'][1]['issue'] is None
    assert client.post(f'/api/session/{session_id}/roster/current').status_code == 400
    assert client.get(f'/api/session/{session_id}/calculation-records').get_json()['records'][0]['issue'] is None


def test_review_without_any_roster_reports_membership_check_unavailable(client, school):
    session_id = create(client)
    target = record(client, session_id)
    db_session.get(Session, session_id).roster_snapshot_id = None
    db_session.query(Student).filter_by(school_id=school.id).update({'is_active': 0})
    db_session.commit()
    result = client.get(f'/api/session/{session_id}/calculation-records').get_json()
    assert result['roster_review']['source'] == 'current'
    assert not result['roster_review']['available']
    assert result['records'][0]['record_id'] == target
    assert result['records'][0]['issue'] is None


def test_invalid_roster_review_scope_does_not_exclude_records(client, school):
    session_id = create(client)
    target = record(client, session_id)
    assert client.get(f'/api/session/{session_id}/calculation-records?roster=other').status_code == 400
    assert client.post(f'/api/session/{session_id}/records/{target}/exclusion?roster=other',
                       json={'excluded': True}).status_code == 400
    assert not db_session.get(SessionRecord, target).is_excluded
    assert db_session.query(RecordExclusionEvent).count() == 0


def test_missing_member_exclusion_fixes_estimates_scores_counts_draws_and_history(client, school, email_outbox):
    upload(client, ['9100', '9101', '9102'])
    session_id = create(client)
    record(client, session_id)
    outsider_id = record(client, session_id, identifier='9102')
    upload(client)
    meal = db_session.get(Session, session_id)
    meal.roster_snapshot_id = db_session.get(School, school.id).current_roster_snapshot_id
    outsider = db_session.query(Student).filter_by(school_id=school.id, student_identifier='9102').one()
    outsider.is_active = 1
    student_id = outsider.id
    db_session.commit()
    assert 'not in' in stats(client, session_id)['estimation']['reason']
    rows = client.get(f'/api/session/{session_id}/calculation-records').get_json()['records']
    assert 'not in' in next(row for row in rows if row['record_id'] == outsider_id)['issue']
    assert len(client.get(f'/api/session/{session_id}/draw/summary').get_json()['candidates']) == 2
    assert client.post(f'/api/session/{session_id}/draw/override', json={'student_identifier': '9102'}).status_code == 200
    email_count = len(email_outbox)
    response = exclude(client, session_id, outsider_id)
    assert response.status_code == 200
    assert response.get_json()['reset_draw_session_ids'] == [session_id]
    assert len(email_outbox) == email_count
    result = stats(client, session_id)
    assert result['estimation']['available'] and result['estimation']['population'] == 2
    assert result['estimation']['student_plate_count'] == 1
    assert result['house_stats'][0]['score'] == 2 and result['house_stats'][0]['total_count'] == 1
    status = client.get('/api/session/status').get_json()
    assert status['clean_count'] == status['total_recorded'] == 1
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert [row['student_identifier'] for row in summary['candidates']] == ['9100']
    assert not summary['draw_info']['has_winner']
    assert get_student_ticket_balance(student_id) == 0
    assert client.post(f'/api/session/{session_id}/draw/override', json={'student_identifier': '9102'}).status_code in (400, 404)
    history = client.get('/api/session/scan-history').get_json()['scan_history']
    assert len(history) == 2
    assert next(row for row in history if row['record_id'] == outsider_id)['is_excluded']
    assert len(get_session_entry(session_id)['clean_records']) == 1
    db_session.remove()
    assert db_session.get(SessionRecord, outsider_id).is_excluded == 1
    assert db_session.query(RecordExclusionEvent).filter_by(record_id=outsider_id).count() == 1
    assert exclude(client, session_id, outsider_id).status_code == 200  # Idempotent.
    assert db_session.query(RecordExclusionEvent).filter_by(record_id=outsider_id).count() == 1
    assert exclude(client, session_id, outsider_id, False).status_code == 200
    assert get_student_ticket_balance(student_id) == 1
    assert stats(client, session_id)['house_stats'][0]['total_count'] == 2
    assert not stats(client, session_id)['estimation']['available']  # Conflict comes back.
    assert db_session.query(RecordExclusionEvent).filter_by(record_id=outsider_id).count() == 2
    assert db_session.query(SessionDrawEvent).filter_by(session_id=session_id, event_type='restore').count() == 1


def test_excluded_roster_member_is_removed_from_population_not_counted_absent(client, school):
    session_id = create(client)
    target = record(client, session_id)
    record(client, session_id, category='dirty', identifier='')
    before = stats(client, session_id)['estimation']
    assert before['population'] == 2 and before['school_absent_count'] == 0
    assert exclude(client, session_id, target).status_code == 200
    after = stats(client, session_id)['estimation']
    assert after['population'] == 1 and after['school_absent_count'] == 0
    assert after['excluded_roster_student_count'] == 1
    assert after['student_plate_count'] == 1 and after['unassigned_record_count'] == 0
    assert exclude(client, session_id, target, False).status_code == 200
    assert stats(client, session_id)['estimation']['population'] == 2


def test_archived_session_can_exclude_all_students_and_restore_without_losing_roster(client, school):
    session_id = create(client)
    first = record(client, session_id)
    second = record(client, session_id, 'dirty', '9101')
    meal = db_session.get(Session, session_id)
    snapshot_id = meal.roster_snapshot_id
    meal.status = 'archived'
    db_session.commit()
    assert exclude(client, session_id, first).status_code == 200
    assert exclude(client, session_id, second).status_code == 200
    result = stats(client, session_id)
    assert result['house_stats'] == []
    assert result['estimation']['available'] and result['estimation']['population'] == 0
    assert result['estimation']['school_absent_count'] == 0
    assert result['estimation']['excluded_roster_student_count'] == 2
    assert not result['estimation']['house_estimates_available']
    assert exclude(client, session_id, first, False).status_code == 200
    meal = db_session.get(Session, session_id)
    assert meal.roster_snapshot_id == snapshot_id and meal.status == 'archived'
    assert stats(client, session_id)['estimation']['population'] == 1


def test_recorded_house_conflict_can_be_excluded_before_matching_current_roster(client, school):
    session_id = create(client)
    target = record(client, session_id)
    student = db_session.query(Student).filter_by(school_id=school.id, student_identifier='9100').one()
    student.house = 'B'
    db_session.commit()
    assert client.post(f'/api/session/{session_id}/roster/current').status_code == 400
    assert exclude(client, session_id, target).status_code == 200
    response = client.post(f'/api/session/{session_id}/roster/current')
    assert response.status_code == 200
    result = response.get_json()['estimation']
    assert result['available'] and result['population'] == 1
    assert result['excluded_roster_student_count'] == 1


def test_excluded_records_do_not_create_a_false_mixed_roster_when_new_recording_begins(client, school):
    session_id = create(client)
    target = record(client, session_id)
    original_snapshot = db_session.get(Session, session_id).roster_snapshot_id
    assert exclude(client, session_id, target).status_code == 200
    upload(client, ['9100', '9101', '9102'])
    record(client, session_id, identifier='9101')
    meal = db_session.get(Session, session_id)
    assert meal.roster_snapshot_id != original_snapshot and not meal.roster_mixed
    result = stats(client, session_id)['estimation']
    assert result['available'] and result['population'] == 2
    assert result['excluded_roster_student_count'] == 1
    assert result['student_plate_count'] == 1


@pytest.mark.parametrize('category', ['clean', 'dirty', 'red', 'faculty'])
def test_count_only_exclusions_recalculate_every_category_without_removing_roster_students(client, school, category):
    session_id = create(client)
    target = record(client, session_id, category, '')
    assert exclude(client, session_id, target).status_code == 200
    status = client.get('/api/session/status').get_json()
    assert status['total_recorded'] == status['clean_count'] == status['dirty_count'] == status['red_count'] == status['faculty_clean_count'] == 0
    result = stats(client, session_id)['estimation']
    assert result['population'] == 2 and result['school_absent_count'] == 2
    assert exclude(client, session_id, target, False).status_code == 200
    assert client.get('/api/session/status').get_json()['total_recorded'] == 1


@pytest.mark.parametrize('categories,target_index,expected', [
    (['clean', 'red', 'clean'], 0, 1),
    (['clean', 'red', 'clean'], 1, 2),
    (['clean', 'red', 'red', 'clean'], 1, 1),  # The second red originally earned no reset event.
])
def test_ticket_replay_respects_later_resets_and_reds_with_original_zero_balance(client, school, categories, target_index, expected):
    ids = []
    for category in categories:
        session_id = create(client)
        ids.append((session_id, record(client, session_id, category)))
    student_id = db_session.query(Student).filter_by(school_id=school.id, student_identifier='9100').one().id
    assert get_student_ticket_balance(student_id) == 1
    assert exclude(client, *ids[target_index]).status_code == 200
    assert get_student_ticket_balance(student_id) == expected
    assert exclude(client, *ids[target_index], False).status_code == 200
    assert get_student_ticket_balance(student_id) == 1


def test_ticket_replay_preserves_balances_predating_event_history(client, school):
    student = db_session.query(Student).filter_by(school_id=school.id, student_identifier='9100').one()
    student_id = student.id
    db_session.add(DraftPool(school_id=school.id, student_id=student_id, ticket_number=10))
    db_session.commit()
    session_id = create(client)
    target = record(client, session_id)
    assert get_student_ticket_balance(student_id) == 11
    assert exclude(client, session_id, target).status_code == 200
    assert get_student_ticket_balance(student_id) == 10


def test_merged_extra_exclusion_clears_main_draw_and_removes_extra_candidate(client, school):
    main_id = create(client)
    record(client, main_id, identifier='9101')
    extra_id = create(client)
    target = record(client, extra_id)
    extra = db_session.get(Session, extra_id)
    extra.main_session_id = main_id
    db_session.commit()
    assert client.post(f'/api/session/{main_id}/draw/override', json={'student_identifier': '9100'}).status_code == 200
    assert exclude(client, extra_id, target).get_json()['reset_draw_session_ids'] == [main_id]
    summary = client.get(f'/api/session/{main_id}/draw/summary').get_json()
    assert [row['student_identifier'] for row in summary['candidates']] == ['9101']
    assert not summary['draw_info']['has_winner']
    assert stats(client, main_id)['house_stats'][0]['total_count'] == 1


def test_excluding_a_finalized_winner_clears_selection_preserves_public_log_and_ticket_reset(client, school):
    session_id = create(client)
    target = record(client, session_id)
    assert client.post(f'/api/session/{session_id}/draw/start', json={}).status_code == 200
    assert client.post(f'/api/session/{session_id}/draw/finalize', json={}).status_code == 200
    assert exclude(client, session_id, target).status_code == 200
    summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
    assert not summary['draw_info']['has_winner'] and not summary['draw_info']['finalized']
    assert db_session.query(SessionDrawEvent).filter_by(session_id=session_id, event_type='finalize').count() == 1
    assert db_session.query(SessionDrawEvent).filter_by(session_id=session_id, event_type='restore').count() == 1
    # The historical finalized prize consumed these tickets; restoring a plate
    # cannot grant those previously spent tickets again.
    assert exclude(client, session_id, target, False).status_code == 200
    student_id = db_session.get(SessionRecord, target).student_id
    assert get_student_ticket_balance(student_id) == 0


def test_exclusion_updates_live_totals_exports_and_survives_cache_rehydration(client, school):
    session_id = create(client)
    target = record(client, session_id)
    record(client, session_id, 'dirty', '')
    before = client.get('/api/live-counter').get_json()['ranges'][0]
    assert before['clean_count'] == 1
    assert exclude(client, session_id, target).status_code == 200
    after = client.get('/api/live-counter').get_json()['ranges'][0]
    assert after['clean_count'] == 0 and after['dirty_count'] == 1
    csv = client.get('/api/export/csv/detailed').get_data(as_text=True)
    assert 'Name9100' not in csv and 'DIRTY' in csv
    from src.routes.golden_plate_recorder_db.storage import hydrate_session_from_db, session_data
    session_data.pop(session_id)
    hydrated = hydrate_session_from_db(session_id)
    assert hydrated['clean_records'] == [] and len(hydrated['dirty_records']) == 1
    assert exclude(client, session_id, target, False).status_code == 200
    assert client.get('/api/live-counter').get_json()['ranges'][0]['clean_count'] == 1


def test_excluded_faculty_record_invalidates_faculty_draw_and_counts(client, school):
    session_id = create(client)
    assert client.post('/api/record/faculty', json={'input_value': 'Teacher Example'}).status_code == 200
    target = db_session.query(SessionRecord).filter_by(session_id=session_id, category='faculty').one().id
    assert client.post(f'/api/session/{session_id}/faculty/pick', json={}).status_code == 200
    assert exclude(client, session_id, target).status_code == 200
    status = client.get('/api/session/status').get_json()
    assert status['faculty_clean_count'] == 0 and status['faculty_pick'] is None
    assert client.post(f'/api/session/{session_id}/faculty/pick', json={}).status_code == 400
    assert exclude(client, session_id, target, False).status_code == 200
    assert client.post(f'/api/session/{session_id}/faculty/pick', json={}).status_code == 200


def test_exclusion_failure_rolls_back_counts_tickets_audit_and_cached_records(client, school, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    session_id = create(client)
    target = record(client, session_id)
    student_id = db_session.get(SessionRecord, target).student_id
    def fail():
        raise SQLAlchemyError('test write failure')
    with monkeypatch.context() as patch:
        patch.setattr(db_session, 'commit', fail)
        assert exclude(client, session_id, target).status_code == 500
    assert not db_session.get(SessionRecord, target).is_excluded
    assert db_session.query(RecordExclusionEvent).filter_by(record_id=target).count() == 0
    assert get_student_ticket_balance(student_id) == 1
    assert client.get('/api/session/status').get_json()['clean_count'] == 1
    assert len(get_session_entry(session_id)['clean_records']) == 1


def test_schema_upgrade_preserves_existing_records_and_defaults_to_included(monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from src.routes.golden_plate_recorder_db import db as database
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text('DROP TABLE session_records'))
        connection.execute(text('''CREATE TABLE session_records (
            id TEXT PRIMARY KEY, school_id TEXT, session_id TEXT, student_id TEXT,
            category TEXT, grade TEXT, house TEXT, is_manual_entry INTEGER,
            recorded_by TEXT, recorded_at DATETIME, dedupe_key TEXT,
            preferred_name TEXT, last_name TEXT)'''))
        connection.execute(text("INSERT INTO session_records (id,school_id,session_id,category,is_manual_entry,recorded_by,dedupe_key) VALUES ('legacy','school','meal','clean',0,'actor','legacy')"))
    monkeypatch.setattr(database, 'engine', engine)
    database._migrate_schema()
    columns = {column['name'] for column in inspect(engine).get_columns('session_records')}
    assert {'is_excluded', 'excluded_at', 'excluded_by', 'exclusion_reason'} <= columns
    with engine.connect() as connection:
        assert connection.execute(text("SELECT is_excluded FROM session_records WHERE id='legacy'")).scalar() == 0


@pytest.mark.parametrize('role', ['admin', 'user', 'inter_school', 'guest', 'anonymous'])
def test_only_superadmins_can_review_or_exclude_records(client, school, role):
    session_id = create(client)
    target = record(client, session_id)
    client.post('/api/auth/logout')
    if role == 'guest':
        client.post('/api/auth/guest', json={'school_slug': school.slug})
    elif role != 'anonymous':
        user = create_user_record(uuid.uuid4().hex, 'test-password', 'Other', role=role, school_id=school.id)
        client.post('/api/auth/login', json={'username': user.username, 'password': 'test-password'})
    expected = 401 if role in ('guest', 'anonymous') else 403
    assert client.get(f'/api/session/{session_id}/calculation-records').status_code == expected
    assert exclude(client, session_id, target).status_code == expected
    assert not db_session.get(SessionRecord, target).is_excluded


def test_superadmin_cannot_exclude_other_schools_records_or_wrong_session(client, school):
    session_id = create(client)
    target = record(client, session_id)
    other_session = create(client)
    assert exclude(client, other_session, target).status_code == 404
    other_school = School(id=uuid.uuid4().hex, name='Other', slug=uuid.uuid4().hex)
    db_session.add(other_school)
    db_session.flush()
    other = Session(school_id=other_school.id, session_name=uuid.uuid4().hex, created_by='other')
    db_session.add(other)
    db_session.commit()
    assert client.get(f'/api/session/{other.id}/calculation-records').status_code == 404
    assert exclude(client, other.id, target).status_code == 404
    assert exclude(client, session_id, uuid.uuid4().hex).status_code == 404


@pytest.mark.parametrize('value', [None, 0, 1, 'true', [], {}])
def test_exclusion_requires_boolean_payload(client, school, value):
    session_id = create(client)
    target = record(client, session_id)
    assert exclude(client, session_id, target, value).status_code == 400
    assert not db_session.get(SessionRecord, target).is_excluded
