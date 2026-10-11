"""Independent allocation checks and Estimate-only integration regressions."""
import io
import json
import math
import uuid
from collections import Counter
from datetime import timedelta
from fractions import Fraction
from itertools import combinations, product
from types import SimpleNamespace

import pytest

from src.routes.golden_plate_recorder_db.clean_percentage_model import (
    PercentageDistribution, clean_percentage_distribution,
    highest_separating_coverage, rank_percentages,
)
from src.routes.golden_plate_recorder_db.clean_percentage_estimation import (
    MODEL, VERSION, estimate_session_percentages, normalize_estimate_house,
)
from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_ID, EstimateSystemActivation, RosterSnapshot, Session, Student,
    _bootstrap_database, _now_utc, db_session,
)

SETTINGS = {'clean_points': 2, 'dirty_penalty': 2, 'very_dirty_penalty': 10}


def scenario(populations, known=None, anonymous=None, grades=None):
    members = {f'{house}-{index}': house for house, count in populations.items() for index in range(count)}
    snapshot = RosterSnapshot(school_id=DEFAULT_SCHOOL_ID, data=json.dumps({
        'members': members, 'grades': {identifier: (grades or {}).get(identifier, '9') for identifier in members},
    }))
    db_session.add(snapshot)
    db_session.commit()
    meal = SimpleNamespace(school_id=DEFAULT_SCHOOL_ID, roster_snapshot_id=snapshot.id,
                           roster_mixed=0, roster_matched_at=None, created_at=_now_utc())
    records = []
    for house, counts in (known or {}).items():
        identifiers = iter(identifier for identifier in members if members[identifier] == house)
        for category, count in counts.items():
            for _ in range(count):
                records.append(SimpleNamespace(category=category, student_id=next(identifiers),
                                               house=house, grade='9', is_excluded=False))
    for category, count in (anonymous or {}).items():
        records.extend(SimpleNamespace(category=category, student_id=None, house=None,
                                       grade=None, is_excluded=False) for _ in range(count))
    return meal, records


def test_exact_distribution_against_independent_enumeration_of_labeled_students():
    # Include separate dirty/red labels in the independent calculation. The
    # production clean statistic combines them algebraically, retaining their dependence.
    for clean, dirty, red, absent in product(range(3), repeat=4):
        categories = ['clean'] * clean + ['dirty'] * dirty + ['red'] * red + ['absent'] * absent
        for capacity in range(len(categories) + 1):
            for known_clean, known_dirty in [(0, 0), (1, 0), (0, 1)]:
                counts = Counter()
                total = 0
                for selected in combinations(range(len(categories)), capacity):
                    total += 1
                    outcomes = [categories[index] for index in selected]
                    participants = known_clean + known_dirty + sum(value != 'absent' for value in outcomes)
                    if participants:
                        counts[Fraction(100 * (known_clean + outcomes.count('clean')), participants)] += 1
                result = clean_percentage_distribution(clean, dirty + red, absent, capacity, known_clean, known_dirty)
                assert result.total_weight == total
                assert result.participant_weight == sum(counts.values())
                assert result.values == tuple(sorted(counts))
                if counts:
                    assert result.expected_percentage == sum(value * weight for value, weight in counts.items()) / sum(counts.values())
                    lower, upper = result.interval()
                    assert sum(weight for value, weight in counts.items() if lower <= value <= upper) * 10 >= 9 * sum(counts.values())
                    assert sum(weight for value, weight in counts.items() if value < lower) * 20 <= sum(counts.values())
                    assert sum(weight for value, weight in counts.items() if value > upper) * 20 <= sum(counts.values())
                    assert result.interval(1000) == (min(counts), max(counts))
                else:
                    assert result.expected_percentage is None and result.interval() is None


def test_expectation_is_not_ratio_of_expected_counts_and_absences_are_excluded():
    distribution = clean_percentage_distribution(0, 1, 1, 1, observed_clean=1)
    assert distribution.expected_percentage == 75  # 50% or 100%, equally likely.
    assert distribution.expected_percentage != Fraction(100, 1 + Fraction(1, 2))
    assert distribution.zero_participation_probability == 0
    one_participant = clean_percentage_distribution(0, 0, 59, 59, observed_clean=1)
    assert one_participant.expected_percentage == 100
    assert one_participant.interval() == (100, 100)


def test_conditional_mean_and_zero_participation_are_separate():
    small = clean_percentage_distribution(1, 1, 8, 1)
    larger = clean_percentage_distribution(1, 1, 8, 5)
    assert small.expected_percentage == larger.expected_percentage == 50
    assert small.zero_participation_probability == Fraction(4, 5)
    assert larger.zero_participation_probability == Fraction(math.comb(8, 5), math.comb(10, 5))


def point_distribution(value):
    return PercentageDistribution((Fraction(value),), (1,), 1, 1, Fraction(value))


def test_exact_three_decimal_competition_ties_and_unranked_houses():
    distributions = {'B': point_distribution('75.1234'), 'A': point_distribution('75.1233'),
                     'C': point_distribution('75.1235'), 'D': point_distribution(20),
                     'E': clean_percentage_distribution(0, 0, 1, 1)}
    rows = rank_percentages([{'house': name} for name in distributions], distributions)
    assert [(row['house'], row['percentage_rank']) for row in rows] == [('C', 1), ('A', 2), ('B', 2), ('D', 4), ('E', None)]
    assert distributions['C'].rounded_percentage_key() == 75124
    assert highest_separating_coverage(rows, distributions)['available'] is False


def test_highest_separating_coverage_agrees_with_full_grid_and_handles_touching():
    distributions = {
        'A': clean_percentage_distribution(1, 5, 4, 4, 4, 0),
        'B': clean_percentage_distribution(1, 5, 4, 3, 1, 2),
    }
    rows = rank_percentages([{'house': name} for name in distributions], distributions)
    separated = []
    for level in range(1, 1001):
        upper_house, lower_house = [distributions[row['house']].interval(level) for row in rows]
        if upper_house[0] > lower_house[1]:
            separated.append(level)
    result = highest_separating_coverage(rows, distributions)
    assert result['coverage_percentage'] == max(separated) / 10
    assert 0 < result['coverage_percentage'] < 100
    touching = {'A': PercentageDistribution((Fraction(50), Fraction(100)), (1, 2), 2, 2, Fraction(75)),
                'B': point_distribution(50)}
    rows = rank_percentages([{'house': name} for name in touching], touching)
    assert not highest_separating_coverage(rows, touching)['available']
    certain = {'A': point_distribution(100), 'B': point_distribution(0)}
    assert highest_separating_coverage(rank_percentages([{'house': name} for name in certain], certain), certain)['coverage_percentage'] == 100
    assert not highest_separating_coverage([{'house': 'A', 'percentage_rank': 1}], certain)['available']


def test_joint_category_totals_and_known_dirty_house_only_records():
    meal, records = scenario({'Flavelle': 5, 'Laidlaw': 5},
                             {'Flavelle': {'clean': 1, 'dirty': 1}}, {'clean': 2, 'dirty': 1, 'red': 1})
    records[1].student_id = None  # A known house is enough to retain direct attribution.
    result = estimate_session_percentages(meal, records, SETTINGS, include_separation=True)
    assert result['available'] and result['coverage'] == .9
    assert result['school_absent_count'] == 4
    for category, count in {'clean': 3, 'dirty': 2, 'red': 1, 'absent': 4}.items():
        assert sum(row[f'{category}_count'] for row in result['house_stats']) == count
    flavelle = next(row for row in result['house_stats'] if row['house'] == 'Flavelle')
    assert flavelle['observed_dirty_count'] == 1 and flavelle['zero_participation_probability'] == 0
    assert not any('score' in key for row in result['house_stats'] for key in row)


def test_lower_grades_and_excluded_students_are_removed_once():
    meal, records = scenario({'Flavelle': 4}, {'Flavelle': {'clean': 3}},
                             {'dirty': 1}, grades={'Flavelle-0': '8'})
    records[1].is_excluded = True
    records.append(SimpleNamespace(**vars(records[1])))
    result = estimate_session_percentages(meal, records, SETTINGS)
    assert result['available'] and result['population'] == 2
    assert result['excluded_roster_student_count'] == 1
    assert result['student_plate_count'] == 2 and result['school_absent_count'] == 0
    assert result['house_stats'][0]['clean_percentage'] == 50
    records[-1] = SimpleNamespace(category='dirty', student_id=None, house=None, grade=None, is_excluded=True)
    result = estimate_session_percentages(meal, records, SETTINGS)
    assert result['population'] == 2 and result['unattributed_counts']['dirty'] == 1


def test_named_unattributed_clean_plates_are_not_treated_as_absences():
    meal, records = scenario({'Smith': 3}, anonymous={'clean': 1})
    records[0].preferred_name = 'Manual record without ID'
    result = estimate_session_percentages(meal, records, SETTINGS)
    assert result['school_absent_count'] == 2
    assert result['house_stats'][0]['clean_percentage'] == 100


@pytest.mark.parametrize('label', ['Macdonald-Flavelle', 'Macdonald – Smith', 'Macdonald/Laidlaw', 'Macdonald - Perrier', 'macdonald—Sifton'])
def test_macdonald_classification_is_local_and_non_destructive(label):
    meal, records = scenario({label: 2}, {label: {'dirty': 1}})
    snapshot = db_session.get(RosterSnapshot, meal.roster_snapshot_id)
    before = snapshot.data
    result = estimate_session_percentages(meal, records, SETTINGS)
    assert result['house_stats'][0]['house'] == 'Macdonald'
    assert snapshot.data == before and records[0].house == label
    assert normalize_estimate_house('Unexpected - House') == 'Unexpected - House'


def test_unknown_house_missing_grades_and_inconsistent_counts_are_explained():
    meal, records = scenario({'Smith': 1}, anonymous={'clean': 1})
    records[0].house = 'Unexpected House'
    assert 'no corresponding eligible population' in estimate_session_percentages(meal, records, SETTINGS)['reason']
    records[0].house = None
    records.append(SimpleNamespace(**vars(records[0])))
    assert 'exceed' in estimate_session_percentages(meal, records, SETTINGS)['reason']
    snapshot = db_session.get(RosterSnapshot, meal.roster_snapshot_id)
    snapshot.data = json.dumps({'members': {'Smith-0': 'Smith'}})
    db_session.commit()
    assert 'saved grade' in estimate_session_percentages(meal, [], SETTINGS)['reason']


def test_historical_cutoff_is_persistent_and_manual_override_remains_an_exception():
    meal, records = scenario({'Smith': 1}, {'Smith': {'clean': 1}})
    cutoff = db_session.get(EstimateSystemActivation, VERSION).activated_at
    meal.created_at = cutoff - timedelta(seconds=1)
    assert 'before the updated estimation system' in estimate_session_percentages(meal, records, SETTINGS)['reason']
    _bootstrap_database()
    db_session.expire_all()
    assert db_session.get(EstimateSystemActivation, VERSION).activated_at == cutoff
    meal.roster_matched_at = _now_utc()
    assert estimate_session_percentages(meal, records, SETTINGS)['available']
    meal.roster_mixed = 1
    assert 'multiple roster versions' in estimate_session_percentages(meal, records, SETTINGS)['reason']


def test_zero_participants_are_unranked_not_zero_percent():
    meal, records = scenario({'Smith': 4, 'Sifton': 2})
    result = estimate_session_percentages(meal, records, SETTINGS)
    for row in result['house_stats']:
        assert row['percentage_rank'] is None and row['clean_percentage'] is None
        assert row['clean_percentage_interval'] is None
        assert row['zero_participation_probability'] == 1


def test_api_preserves_scoring_override_access_and_grade_snapshots(client, login, email_outbox):
    assert login().status_code == 200
    roster = 'Student ID,Last,Preferred,Grade,House\n99001,One,Student,9,Flavelle\n99002,Two,Student,8,Flavelle\n99003,Three,Student,10,Laidlaw\n'
    assert client.post('/api/csv/upload', data={'file': (io.BytesIO(roster.encode()), 'upper-school.csv')}, content_type='multipart/form-data').status_code == 200
    response = client.post('/api/session/create', json={'session_name': f'new-estimate-{uuid.uuid4().hex}'})
    identifier = response.get_json()['session_id']
    assert client.post('/api/record/clean', json={'input_value': '99001'}).status_code == 200
    path = f'/api/session/{identifier}/house-stats'
    response = client.get(path).get_json()
    assert response['estimation']['model'] == MODEL
    assert response['estimation']['population'] == 2
    assert response['house_stats'][0]['score'] == 2
    assert response['score_settings'] == SETTINGS
    before = response['estimation']['calculation_signature']
    assert client.post('/api/record/dirty', json={}).status_code == 200
    current = client.get(path + '?estimate_separation=1').get_json()
    assert current['house_stats'] == response['house_stats']  # Anonymous plates never change the original scores.
    assert current['estimation']['calculation_signature'] != before
    assert current['estimation']['separating_coverage']['coverage_percentage'] == 100
    # A later edit of current grades must not rewrite saved session eligibility.
    student = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='99001').one()
    student.grade = '8'
    db_session.commit()
    assert client.get(path).get_json()['estimation']['population'] == 2
    meal = db_session.get(Session, identifier)
    meal.created_at = db_session.get(EstimateSystemActivation, VERSION).activated_at - timedelta(days=1)
    db_session.commit()
    assert not client.get(path).get_json()['estimation']['available']
    # Restore current grade for the existing override's explicit attestation.
    student = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='99001').one()
    student.grade = '9'
    db_session.commit()
    assert client.post(f'/api/session/{identifier}/roster/current').status_code == 200
    assert client.get(path).get_json()['estimation']['available']
    assert not email_outbox
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get(path + '?estimate_separation=1').status_code == 401
