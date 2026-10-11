"""Upper School Estimate tab adapter; existing scoring and overrides stay intact."""

import hashlib
import json
import re
from datetime import timezone

from .clean_percentage_model import (
    clean_percentage_distribution, highest_separating_coverage, rank_percentages,
)
from .db import DEFAULT_SCHOOL_ID, EstimateSystemActivation, RosterSnapshot, Student, db_session
from .house_estimation import estimate_house_stats, hypergeometric_interval


MODEL = 'conditional_clean_percentage_hypergeometric'
VERSION = 'upper-school-clean-percentage-v1'
CATEGORIES = ('clean', 'dirty', 'red')


def normalize_estimate_house(value):
    """Recognize Macdonald combinations locally, never rewrite stored houses."""
    house = str(value or '').strip()
    if house.casefold() == 'macdonald' or re.match(
        r'^Macdonald(?:\s*[-–—/|_:]\s*|\s+)(?=\S)', house, re.IGNORECASE,
    ):
        return 'Macdonald'
    return house


def _grade(value):
    match = re.fullmatch(r'(?:grade\s*)?(\d{1,2})(?:\.0)?', str(value or '').strip(), re.I)
    return int(match[1]) if match else None


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _unavailable(reason, **metadata):
    return {'model': MODEL, 'available': False, 'reason': reason, 'house_stats': [], **metadata}


def estimate_session_percentages(meal, records, settings, *, include_separation=False):
    # This school's eligibility policy must not change existing other-school behavior.
    if meal.school_id != DEFAULT_SCHOOL_ID:
        return estimate_house_stats(meal, records, settings)
    activation = db_session.get(EstimateSystemActivation, VERSION)
    matched_at = getattr(meal, 'roster_matched_at', None)
    created_at = getattr(meal, 'created_at', None)
    if not activation:
        return _unavailable('The updated estimation system has no saved activation date.')
    if not matched_at and (not created_at or _utc(created_at) < _utc(activation.activated_at)):
        return _unavailable('Estimates unavailable — this session was recorded before the updated estimation system was implemented.')
    if meal.roster_mixed:
        return _unavailable('Estimates are unavailable because this session contains student records from multiple roster versions.')
    snapshot = db_session.query(RosterSnapshot).filter_by(
        id=meal.roster_snapshot_id, school_id=meal.school_id,
    ).first() if meal.roster_snapshot_id else None
    if not snapshot:
        return _unavailable('Estimates are unavailable because no roster was saved for this session. Use the existing roster override if an applicable roster is available.')
    metadata = {'roster_snapshot_id': snapshot.id, 'roster_filename': snapshot.filename,
                'roster_saved_at': snapshot.created_at.isoformat(),
                'roster_assignment': 'manual' if matched_at else 'automatic',
                'roster_matched_at': matched_at.isoformat() if matched_at else None}
    try:
        roster = json.loads(snapshot.data)
        members = roster['members']
        if not isinstance(members, dict):
            raise ValueError('Invalid membership')
        grades = roster.get('grades', {})
        if not isinstance(grades, dict):
            raise ValueError('Invalid grades')
    except (ValueError, TypeError, KeyError):
        return _unavailable('Estimates are unavailable because the saved roster is incomplete or invalid.', **metadata)
    if matched_at and not grades:
        # An existing explicit manual override remains an exception. Automatic
        # sessions never reconstruct eligibility from later student profiles.
        grades = {student.id: student.grade for student in db_session.query(Student).filter(
            Student.school_id == meal.school_id, Student.id.in_(members),
        ).all()}
        metadata['grade_source'] = 'manual_override_student_profiles'
    excluded_ids = {record.student_id for record in records
                    if getattr(record, 'is_excluded', False) and record.student_id
                    and record.category in CATEGORIES}
    eligible = {}
    lower_school = set()
    for identifier, house in members.items():
        if identifier in excluded_ids:
            continue
        grade = _grade(grades.get(identifier))
        if grade is None:
            return _unavailable('Estimates are unavailable because an enrolled student has no valid saved grade. A Grades 9–12 population cannot be established.', **metadata)
        if 9 <= grade <= 12:
            eligible[identifier] = normalize_estimate_house(house)
        else:
            lower_school.add(identifier)
    metadata['excluded_roster_student_count'] = sum(
        identifier in members and 9 <= (_grade(grades.get(identifier)) or 0) <= 12
        for identifier in excluded_ids
    )
    populations = {}
    # A linked record may supply a saved member's missing house without edits.
    for record in records:
        if (not getattr(record, 'is_excluded', False) and record.category in CATEGORIES
                and record.student_id in eligible and not eligible[record.student_id]):
            eligible[record.student_id] = normalize_estimate_house(record.house)
    if any(not house for house in eligible.values()):
        return _unavailable('Estimates are unavailable because an eligible student has no known house assignment.', **metadata)
    for house in eligible.values():
        populations[house] = populations.get(house, 0) + 1
    known = {house: dict.fromkeys(CATEGORIES, 0) for house in populations}
    anonymous = dict.fromkeys(CATEGORIES, 0)
    seen = set()
    for record in records:
        if getattr(record, 'is_excluded', False) or record.category not in CATEGORIES:
            continue
        if record.student_id in excluded_ids or record.student_id in lower_school:
            continue
        if record.student_id:
            if record.student_id not in eligible:
                return _unavailable('Estimates are unavailable because a recorded student is not in the eligible saved roster.', **metadata)
            if record.student_id in seen:
                return _unavailable('Estimates are unavailable because a student has multiple recorded plates in this session.', **metadata)
            seen.add(record.student_id)
        elif _grade(getattr(record, 'grade', None)) is not None and not 9 <= _grade(record.grade) <= 12:
            continue
        house = normalize_estimate_house(record.house)
        if record.student_id:
            saved_house = eligible[record.student_id]
            if house and house != saved_house:
                return _unavailable('Estimates are unavailable because a recorded house does not match the eligible saved roster.', **metadata)
            house = saved_house
        if house:
            if house not in populations:
                return _unavailable(f'Estimates are unavailable because the recorded house “{house}” has no corresponding eligible population.', **metadata)
            known[house][record.category] += 1
        else:
            # Unattributed named/manual records are still Upper School outcomes.
            anonymous[record.category] += 1
    capacities = {house: count - sum(known[house].values()) for house, count in populations.items()}
    if any(capacity < 0 for capacity in capacities.values()):
        return _unavailable('Estimates are unavailable because recorded plates exceed a house’s eligible population.', **metadata)
    residual = sum(capacities.values())
    absences = residual - sum(anonymous.values())
    if absences < 0:
        return _unavailable('Estimates are unavailable because student plate counts exceed the eligible population.', **metadata)
    rows = []
    distributions = {}
    for house, population in sorted(populations.items()):
        observed = known[house]
        distribution = clean_percentage_distribution(
            anonymous['clean'], anonymous['dirty'] + anonymous['red'], absences,
            capacities[house], observed['clean'], observed['dirty'] + observed['red'],
        )
        distributions[house] = distribution
        expectation = distribution.expected_percentage
        rounded_key = distribution.rounded_percentage_key()
        row = {'house': house, 'population': population, 'unknown_students': capacities[house],
               'clean_percentage': float(expectation) if expectation is not None else None,
               'clean_percentage_display': f'{rounded_key / 1000:.3f}' if rounded_key is not None else None,
               'clean_percentage_interval': [float(value) for value in distribution.interval()] if expectation is not None else None,
               'zero_participation_probability': float(distribution.zero_participation_probability)}
        for category, total in {**anonymous, 'absent': absences}.items():
            row[f'observed_{category}_count'] = observed.get(category, 0)
            row[f'{category}_count'] = observed.get(category, 0) + (capacities[house] * total / residual if residual else 0)
            interval, bounds = hypergeometric_interval(residual, total, capacities[house], .90)
            row[f'{category}_interval'] = [observed.get(category, 0) + value for value in interval]
            row[f'{category}_bounds'] = [observed.get(category, 0) + value for value in bounds]
        row['total_count'] = sum(row[f'{category}_count'] for category in CATEGORIES)
        rows.append(row)
    rows = rank_percentages(rows, distributions)
    signature_data = {'populations': populations, 'known': known, 'anonymous': anonymous,
                      'absences': absences, 'snapshot': snapshot.id}
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    student_clean = sum(values['clean'] for values in known.values()) + anonymous['clean']
    total = sum(sum(values.values()) for values in known.values()) + sum(anonymous.values())
    result = {'model': MODEL, 'available': True, 'reason': None, **metadata,
              'coverage': .90, 'coverage_scope': 'individual_house_conditional_on_participation',
              'calculation_method': 'exact_joint_allocation', 'calculation_signature': signature,
              'house_stats': rows, 'population': sum(populations.values()),
              'student_plate_count': total, 'school_absent_count': absences,
              'student_clean_percentage': student_clean * 100 / total if total else None,
              'unattributed_counts': anonymous,
              'observed_dirty_count': sum(values['dirty'] for values in known.values()),
              'house_estimates_available': bool(rows),
              'house_estimates_reason': None if rows else 'No eligible students remain in this session’s estimation population.'}
    if include_separation:
        result['separating_coverage'] = highest_separating_coverage(rows, distributions)
    return result
