import io
import json
import math
from itertools import combinations
import uuid
from types import SimpleNamespace

import pytest

from src.routes.golden_plate_recorder_db.db import DEFAULT_SCHOOL_ID, RosterSnapshot, School, Session, db_session
from src.routes.golden_plate_recorder_db.house_estimation import (
    estimate_house_stats, hypergeometric_interval, rank_score_intervals, score_model_interval,
)
from src.routes.golden_plate_recorder_db.users import create_user_record

SETTINGS = {'clean_points': 2, 'dirty_penalty': 2, 'very_dirty_penalty': 10}


def model(populations, known=None, unknown=None, faculty=0):
    members = {f'{house}-{i}': house for house, count in populations.items() for i in range(count)}
    snapshot = RosterSnapshot(school_id=DEFAULT_SCHOOL_ID, data=json.dumps({
        'members': members, 'populations': populations, 'missing_house_count': 0,
    }))
    db_session.add(snapshot)
    db_session.commit()
    meal = SimpleNamespace(school_id=DEFAULT_SCHOOL_ID, roster_snapshot_id=snapshot.id, roster_mixed=0)
    records = []
    for house, counts in (known or {}).items():
        identifier = 0
        for category, count in counts.items():
            for _ in range(count):
                records.append(SimpleNamespace(category=category, student_id=f'{house}-{identifier}',
                                               preferred_name='Student', last_name='Test', house=house))
                identifier += 1
    for category, count in {**(unknown or {}), 'faculty': faculty}.items():
        records.extend(SimpleNamespace(category=category, student_id=None, preferred_name=None,
                                       last_name=None, house=None) for _ in range(count))
    return meal, records


def test_document_example_and_exact_student_totals():
    meal, records = model({'A': 100, 'B': 80, 'C': 120}, {
        'A': {'clean': 60, 'red': 10}, 'B': {'clean': 52, 'red': 8}, 'C': {'clean': 75, 'red': 15},
    }, {'dirty': 32}, faculty=100)
    result = estimate_house_stats(meal, records, SETTINGS)
    assert result['available']
    assert result['school_absent_count'] == 48
    assert result['student_plate_count'] == 252
    assert result['student_clean_percentage'] == pytest.approx(187 / 252 * 100)
    rows = {row['house']: row for row in result['house_stats']}
    assert rows['A']['dirty_count'] == 12 and rows['A']['dirty_interval'] == [8, 16]
    assert rows['B']['dirty_count'] == 8 and rows['B']['dirty_interval'] == [4, 12]
    assert rows['C']['absent_count'] == 18 and rows['C']['absent_interval'] == [14, 22]
    assert [rows[h]['score'] for h in 'ABC'] == [-4, 8, -24]
    assert sum(row['dirty_count'] for row in rows.values()) == 32
    assert sum(row['absent_count'] for row in rows.values()) == 48
    assert result['score_coverage'] == .95
    assert result['score_coverage_scope'] == 'simultaneous_across_houses'
    assert result['score_individual_coverage'] == pytest.approx(1 - .05 / 3)
    # Negative dirty penalties reverse the dirty-count interval endpoints.
    for house, observed_score in [('A', 20), ('B', 24), ('C', 0)]:
        count_interval, _ = hypergeometric_interval(80, 32, rows[house]['unknown_students'], result['score_individual_coverage'])
        assert rows[house]['score_interval'] == [observed_score - 2 * count_interval[1],
                                                 observed_score - 2 * count_interval[0]]


def test_known_dirty_plates_condition_the_remaining_allocation():
    meal, records = model({'A': 10, 'B': 10}, {'A': {'dirty': 4}}, {'dirty': 4})
    result = estimate_house_stats(meal, records, SETTINGS)
    a, b = result['house_stats']
    assert a['dirty_count'] == 5.5 and b['dirty_count'] == 2.5
    assert a['observed_dirty_count'] == 4 and a['estimated_additional_dirty'] == 1.5
    assert a['dirty_bounds'] == [4, 8]
    assert a['dirty_interval'][0] >= 4
    assert a['dirty_count'] + b['dirty_count'] == 8
    assert result['school_absent_count'] == 12


def test_anonymous_clean_and_red_are_allocated_without_becoming_absences():
    meal, records = model({'A': 5, 'B': 5}, unknown={'clean': 2, 'dirty': 3, 'red': 1})
    result = estimate_house_stats(meal, records, SETTINGS)
    assert result['school_absent_count'] == 4
    for category, total in [('clean', 2), ('dirty', 3), ('red', 1), ('absent', 4)]:
        assert sum(row[f'{category}_count'] for row in result['house_stats']) == total
    assert result['house_stats'][0]['score_bounds'] == [-16, 4]


@pytest.mark.parametrize('known,unknown,expected', [
    ({'A': {'clean': 2}}, {}, (0, 0)),
    ({}, {}, (0, 2)),
    ({}, {'dirty': 2}, (2, 0)),
])
def test_zero_residual_all_absent_and_all_dirty(known, unknown, expected):
    meal, records = model({'A': 2}, known, unknown)
    result = estimate_house_stats(meal, records, SETTINGS)
    row = result['house_stats'][0]
    assert (row['dirty_count'], row['absent_count']) == expected
    assert row['dirty_interval'] == [expected[0]] * 2
    assert row['absent_interval'] == [expected[1]] * 2
    assert row['score_interval'] == [row['score']] * 2


@pytest.mark.parametrize('intervals,advantages', [
    ([[10, 20], [0, 10]], [[], []]),  # Touching is not a strict advantage.
    ([[10, 20], [15, 25]], [[], []]),
    ([[11, 20], [0, 10]], [['B'], []]),
    ([[4, 4], [4, 4]], [[], []]),
])
def test_score_ranking_only_rewards_strictly_separated_ranges(intervals, advantages):
    rows = rank_score_intervals([{'house': house, 'score_interval': interval, 'score': 999 if house == 'B' else -999}
                                for house, interval in zip('AB', intervals)])
    by_house = {row['house']: row for row in rows}
    assert [by_house[house]['clearly_ahead_of'] for house in 'AB'] == advantages
    if advantages == [[], []]:
        assert all(row['rank_range'] == [1, 2] for row in rows)
    else:
        assert by_house['A']['rank_range'] == [1, 1]
        assert by_house['B']['rank_range'] == [2, 2]


def test_partial_ranking_handles_nontransitive_overlaps():
    rows = rank_score_intervals([{'house': house, 'score_interval': interval} for house, interval in
                                [('A', [10, 20]), ('B', [15, 25]), ('C', [22, 30])]])
    by_house = {row['house']: row for row in rows}
    assert by_house['C']['clearly_ahead_of'] == ['A']
    assert by_house['B']['clearly_ahead_of'] == []
    assert by_house['A']['rank_range'] == [2, 3]
    assert by_house['B']['rank_range'] == [1, 3]
    assert by_house['C']['rank_range'] == [1, 2]


def test_simultaneous_score_coverage_against_all_joint_assignments():
    meal, records = model({'A': 3, 'B': 3, 'C': 4}, unknown={'clean': 2, 'dirty': 3, 'red': 1})
    result = estimate_house_stats(meal, records, SETTINGS)
    intervals = {row['house']: row['score_interval'] for row in result['house_stats']}
    weights = [2, 2, -2, -2, -2, -10, 0, 0, 0, 0]
    total = covered = 0
    for a in combinations(range(10), 3):
        remaining = set(range(10)) - set(a)
        for b in combinations(sorted(remaining), 3):
            c = remaining - set(b)
            scores = {house: sum(weights[i] for i in indices) for house, indices in [('A', a), ('B', b), ('C', c)]}
            total += 1
            covered += all(intervals[house][0] <= score <= intervals[house][1] for house, score in scores.items())
    assert covered / total >= .95
    assert all(row['score_interval_method'] == 'exact_score_distribution' for row in result['house_stats'])


def test_conservative_score_fallback_retains_coverage_with_dependent_categories():
    unknown = dict.fromkeys(('clean', 'dirty', 'red', 'absent'), 80)
    points = {'clean': 2, 'dirty': -2, 'red': -10, 'absent': 0}
    interval, method = score_model_interval(unknown, points, 80, .99)
    assert method == 'conservative_category_projection'
    choices = [math.comb(80, k) for k in range(81)]
    covered = 0
    for clean in range(81):
        for dirty in range(81 - clean):
            for red in range(81 - clean - dirty):
                absent = 80 - clean - dirty - red
                score = 2 * clean - 2 * dirty - 10 * red
                if interval[0] <= score <= interval[1]:
                    covered += choices[clean] * choices[dirty] * choices[red] * choices[absent]
    assert covered / math.comb(320, 80) >= .99


def test_score_interval_zero_weights_and_equal_weight_categories_are_exact():
    unknown = {'clean': 2, 'dirty': 3, 'red': 1, 'absent': 4}
    assert score_model_interval(unknown, dict.fromkeys(unknown, 0), 4, .95)[0] == [0, 0]
    assert score_model_interval(unknown, dict.fromkeys(unknown, -2), 4, .95)[0] == [-8, -8]


@pytest.mark.parametrize('population,successes,draws', [(80, 32, 30), (80, 32, 20), (31, 7, 11), (1000, 400, 120)])
def test_intervals_cover_at_least_95_percent_using_independent_exact_probabilities(population, successes, draws):
    interval, bounds = hypergeometric_interval(population, successes, draws)
    denominator = math.comb(population, draws)
    probabilities = {k: math.comb(successes, k) * math.comb(population - successes, draws - k) / denominator
                     for k in range(bounds[0], bounds[1] + 1)}
    assert sum(probabilities[k] for k in range(interval[0], interval[1] + 1)) >= .95
    assert sum(p for k, p in probabilities.items() if k < interval[0]) <= .025
    assert sum(p for k, p in probabilities.items() if k > interval[1]) <= .025


def test_invalid_data_and_missing_history_have_explicit_reasons():
    meal, records = model({'A': 2}, unknown={'dirty': 3})
    assert 'exceed' in estimate_house_stats(meal, records, SETTINGS)['reason']
    meal.roster_snapshot_id = None
    assert 'historical roster' in estimate_house_stats(meal, [], SETTINGS)['reason']
    meal.roster_mixed = 1
    assert 'multiple roster' in estimate_house_stats(meal, [], SETTINGS)['reason']


def test_saved_membership_checks_and_school_isolation():
    meal, records = model({'A': 2}, {'A': {'clean': 1}})
    records[0].house = 'B'
    assert 'house does not match' in estimate_house_stats(meal, records, SETTINGS)['reason']
    records[0].house = 'A'
    records[0].student_id = 'not-in-roster'
    assert 'not in' in estimate_house_stats(meal, records, SETTINGS)['reason']
    meal.school_id = 'other-school'
    assert not estimate_house_stats(meal, records, SETTINGS)['available']


@pytest.fixture
def estimation_school(client):
    client.get('/api/auth/status')
    suffix = uuid.uuid4().hex
    school = School(id=f'estimate-{suffix}', name='Estimate Academy', slug=f'estimate-{suffix}')
    db_session.add(school)
    db_session.commit()
    admin = create_user_record(f'estimate-admin-{suffix}', 'test-password', 'Estimate Admin',
                               role='superadmin', school_id=school.id)
    assert client.post('/api/auth/login', json={'username': admin.username, 'password': 'test-password'}).status_code == 200
    return school


def upload(client, size, house='A'):
    roster = 'Student ID,Last,Preferred,House\n'
    roster += ''.join(f'{9000+i},Test,Student{i},{house}\n' for i in range(size))
    response = client.post('/api/csv/upload', data={'file': (io.BytesIO(roster.encode()), 'roster.csv')})
    assert response.status_code == 200


def create(client):
    response = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex})
    assert response.status_code == 200
    return response.get_json()['session_id']


def estimate(client, identifier):
    response = client.get(f'/api/session/{identifier}/house-stats')
    assert response.status_code == 200
    return response.get_json()['estimation']


def test_roster_versions_persist_and_historical_sessions_keep_their_population(client, estimation_school):
    upload(client, 8)
    old = create(client)
    assert client.post('/api/record/dirty', json={}).status_code == 200
    assert client.post('/api/record/faculty', json={}).status_code == 200
    initial = estimate(client, old)
    upload(client, 12)
    new = create(client)
    db_session.remove()
    historical = estimate(client, old)
    assert historical['roster_snapshot_id'] == initial['roster_snapshot_id']
    assert historical['population'] == 8 and historical['school_absent_count'] == 7
    assert estimate(client, new)['population'] == 12
    assert estimate(client, new)['roster_snapshot_id'] != initial['roster_snapshot_id']


def test_empty_sessions_follow_current_roster_and_identical_uploads_keep_snapshot(client, estimation_school):
    identifier = create(client)
    assert not estimate(client, identifier)['available']
    upload(client, 3)
    first = estimate(client, identifier)
    assert first['population'] == 3
    upload(client, 3)
    assert estimate(client, identifier)['roster_snapshot_id'] == first['roster_snapshot_id']
    upload(client, 4)
    assert estimate(client, identifier)['population'] == 4


def test_recording_across_roster_changes_reports_unavailable(client, estimation_school):
    upload(client, 3)
    identifier = create(client)
    assert client.post('/api/record/dirty', json={}).status_code == 200
    upload(client, 4)
    assert client.post('/api/record/dirty', json={}).status_code == 200
    assert 'multiple roster' in estimate(client, identifier)['reason']


def test_legacy_populated_sessions_are_not_assigned_todays_roster(client, estimation_school):
    upload(client, 3)
    identifier = create(client)
    assert client.post('/api/record/dirty', json={}).status_code == 200
    meal = db_session.get(Session, identifier)
    meal.roster_snapshot_id = None
    db_session.commit()
    upload(client, 4)
    assert 'historical roster' in estimate(client, identifier)['reason']


def test_missing_roster_house_is_reported(client, estimation_school):
    upload(client, 3, house='')
    identifier = create(client)
    assert 'without a house' in estimate(client, identifier)['reason']


def test_existing_database_upgrade_adds_roster_tracking(monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from src.routes.golden_plate_recorder_db import db as database
    engine = create_engine('sqlite://')
    database.Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE schools DROP COLUMN current_roster_snapshot_id'))
        connection.execute(text('ALTER TABLE sessions DROP COLUMN roster_snapshot_id'))
        connection.execute(text('ALTER TABLE sessions DROP COLUMN roster_mixed'))
        connection.execute(text('DROP TABLE roster_snapshots'))
    monkeypatch.setattr(database, 'engine', engine)
    try:
        database._bootstrap_database()
        inspector = inspect(engine)
        assert 'roster_snapshots' in inspector.get_table_names()
        assert {'roster_snapshot_id', 'roster_mixed'} <= {c['name'] for c in inspector.get_columns('sessions')}
        assert 'current_roster_snapshot_id' in {c['name'] for c in inspector.get_columns('schools')}
        database._bootstrap_database()
    finally:
        engine.dispose()
