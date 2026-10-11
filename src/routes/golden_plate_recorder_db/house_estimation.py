"""Conditional allocations of unattributed plates, preserving observed outcomes."""

import json
import math
from fractions import Fraction
from functools import lru_cache

from .db import RosterSnapshot, db_session
from .utils import normalize_house


MODEL_COVERAGE = .95


def hypergeometric_interval(population, successes, draws, coverage=MODEL_COVERAGE):
    """Equal-tail model interval and exact support, including degenerate cases."""
    lower = max(0, successes - (population - draws))
    upper = min(successes, draws)
    if lower == upper:
        return [lower, upper], [lower, upper]

    def log_choose(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

    logs = [log_choose(successes, k) + log_choose(population - successes, draws - k)
            for k in range(lower, upper + 1)]
    peak = max(logs)
    weights = [math.exp(value - peak) for value in logs]
    total = math.fsum(weights)
    cumulative = 0
    tail = (1 - coverage) / 2
    low_quantile = None
    high_quantile = upper
    for k, weight in zip(range(lower, upper + 1), weights):
        cumulative += weight / total
        if low_quantile is None and cumulative >= tail:
            low_quantile = k
        if cumulative >= 1 - tail:
            high_quantile = k
            break
    return [low_quantile, high_quantile], [lower, upper]


@lru_cache(maxsize=64)
def _score_distribution(groups, draws):
    """Enumerate joint allocations with exact combinatorial weights, when small."""
    groups = sorted(groups, key=lambda group: group[1])
    # Keep larger generalized problems responsive. The fallback below retains
    # guaranteed coverage, rather than replacing the joint model by independence.
    if math.prod(min(draws, count) + 1 for _, count in groups[:-1]) > 100_000:
        return None
    choices = [{k: math.comb(count, k) for k in range(min(draws, count) + 1)}
               for _, count in groups]
    suffix = [sum(count for _, count in groups[i:]) for i in range(len(groups))]
    distribution = {}

    def allocate(index, remaining, score, ways):
        weight, count = groups[index]
        if index == len(groups) - 1:
            if 0 <= remaining <= count:
                score += weight * remaining
                distribution[score] = distribution.get(score, 0) + ways * choices[index][remaining]
            return
        for selected in range(max(0, remaining - suffix[index + 1]), min(count, remaining) + 1):
            allocate(index + 1, remaining - selected, score + weight * selected,
                     ways * choices[index][selected])

    allocate(0, draws, 0, 1)
    return tuple(sorted(distribution.items()))


def score_model_interval(unknown, points, draws, coverage):
    """A score interval accounting for dependent category counts."""
    grouped = {}
    for category, count in unknown.items():
        if count:
            weight = points[category]
            grouped[weight] = grouped.get(weight, 0) + count
    groups = tuple(sorted(grouped.items()))
    population = sum(unknown.values())
    if not draws or not groups:
        return [0, 0], 'exact_score_distribution'
    if len(groups) == 1:
        return [draws * groups[0][0]] * 2, 'exact_score_distribution'
    if len(groups) == 2:
        (weight, count), (other_weight, _) = groups
        interval, _ = hypergeometric_interval(population, count, draws, coverage)
        scores = [draws * other_weight + (weight - other_weight) * k for k in interval]
        return sorted(scores), 'exact_score_distribution'
    distribution = _score_distribution(groups, draws)
    if distribution is not None:
        total = sum(ways for _, ways in distribution)
        tail = (1 - Fraction(str(coverage))) / 2
        cumulative = 0
        lower = None
        upper = distribution[-1][0]
        for score, ways in distribution:
            cumulative += ways
            if lower is None and cumulative * tail.denominator >= total * tail.numerator:
                lower = score
            if cumulative * tail.denominator >= total * (tail.denominator - tail.numerator):
                upper = score
                break
        return [lower, upper], 'exact_score_distribution'
    # Union-bound category coverage yields a conservative score interval with
    # at least the requested coverage, even though the counts are dependent.
    scored = [(category, weight) for category, weight in points.items()
              if weight and unknown[category]]
    category_coverage = 1 - (1 - coverage) / len(scored)
    lower = upper = 0
    for category, weight in scored:
        interval, _ = hypergeometric_interval(population, unknown[category], draws, category_coverage)
        contribution = sorted(weight * value for value in interval)
        lower += contribution[0]
        upper += contribution[1]
    return [lower, upper], 'conservative_category_projection'


def unavailable(reason, **details):
    return {'available': False, 'reason': reason, 'house_stats': [], **details}


def rank_score_intervals(rows):
    """Partial ranks: only strictly disjoint score intervals establish order."""
    for row in rows:
        row['clearly_ahead_of'] = sorted(other['house'] for other in rows
                                        if row['score_interval'][0] > other['score_interval'][1])
        row['clearly_behind'] = sorted(other['house'] for other in rows
                                     if other['score_interval'][0] > row['score_interval'][1])
        row['rank_range'] = [1 + len(row['clearly_behind']), len(rows) - len(row['clearly_ahead_of'])]
    # Alphabetical display resolves presentation within equal minimum ranks;
    # neither point estimates nor a non-transitive overlap comparator rank ties.
    return sorted(rows, key=lambda row: (row['rank_range'][0], row['house']))


def estimate_house_stats(meal, records, settings):
    if meal.roster_mixed:
        return unavailable('Estimated scores are unavailable because this session contains student records from multiple roster versions.')
    snapshot = db_session.query(RosterSnapshot).filter_by(
        id=meal.roster_snapshot_id, school_id=meal.school_id,
    ).first() if meal.roster_snapshot_id else None
    if not snapshot:
        return unavailable('Estimated scores are unavailable because no historical roster was saved for this session. New sessions save their roster automatically.')
    roster = json.loads(snapshot.data)
    matched_at = getattr(meal, 'roster_matched_at', None)
    metadata = {'roster_snapshot_id': snapshot.id, 'roster_filename': snapshot.filename,
                'roster_saved_at': snapshot.created_at.isoformat(),
                'roster_assignment': 'manual' if matched_at else 'automatic',
                'roster_matched_at': matched_at.isoformat() if matched_at else None}
    members = {identifier: normalize_house(house) for identifier, house in roster['members'].items()}
    if not members:
        return unavailable('Estimated scores are unavailable because the saved roster has no students.', **metadata)
    missing_house_count = sum(not house for house in members.values())
    # A linked plate can supply an otherwise missing house without changing the
    # immutable roster. Never infer a house from anonymous plates or proportions.
    for record in records:
        if record.category in ('clean', 'dirty', 'red') and record.student_id in members:
            if not members[record.student_id] and normalize_house(record.house):
                members[record.student_id] = normalize_house(record.house)
    populations = {}
    for house in members.values():
        # The empty key cannot collide with an actual house named "Unassigned house".
        populations[house] = populations.get(house, 0) + 1
    known = {house: {'clean': 0, 'dirty': 0, 'red': 0} for house in populations}
    unknown = {'clean': 0, 'dirty': 0, 'red': 0}
    seen = set()
    for record in records:
        if record.category not in unknown:
            continue
        named = bool(record.student_id or (record.preferred_name or '').strip() or (record.last_name or '').strip())
        if not named:
            unknown[record.category] += 1
            continue
        if record.student_id:
            if record.student_id not in members:
                return unavailable('Estimated scores are unavailable because a recorded student is not in this session’s saved roster.', **metadata)
            if record.student_id in seen:
                return unavailable('Estimated scores are unavailable because a student has multiple recorded plates in this session.', **metadata)
            seen.add(record.student_id)
        house = normalize_house(record.house) or members.get(record.student_id, '')
        if house not in populations or (record.student_id and house != members[record.student_id]):
            return unavailable('Estimated scores are unavailable because a recorded house does not match this session’s saved roster.', **metadata)
        known[house][record.category] += 1
    residuals = {house: count - sum(known[house].values()) for house, count in populations.items()}
    if any(count < 0 for count in residuals.values()):
        return unavailable('Estimated scores are unavailable because recorded plates exceed a house’s saved population.', **metadata)
    school_population = sum(populations.values())
    anonymous_total = sum(unknown.values())
    absences = sum(residuals.values()) - anonymous_total
    if absences < 0:
        return unavailable('Estimated scores are unavailable because student plate counts exceed the saved roster population.', **metadata)
    # Only named, recorded students can be classified as unassigned. Anonymous
    # outcomes remain a separate pool allocated across actual houses only.
    unassigned_counts = known.pop('', dict.fromkeys(unknown, 0))
    unassigned_record_count = sum(unassigned_counts.values())
    excluded_population = populations.pop('', 0)
    residuals.pop('', None)
    residual = sum(residuals.values())
    house_estimates_available = bool(populations) and anonymous_total <= residual
    house_estimates_reason = None
    if not populations:
        house_estimates_reason = 'No actual houses are available in this session’s saved roster or linked student plates. School totals are still shown.'
    elif anonymous_total > residual:
        house_estimates_reason = 'Count-only plates exceed the remaining students with known houses. House estimates cannot allocate them consistently; school totals are still shown.'
    unknown['absent'] = max(0, residual - anonymous_total)
    result = []
    points = {'clean': settings['clean_points'], 'dirty': -settings['dirty_penalty'],
              'red': -settings['very_dirty_penalty'], 'absent': 0}
    # Bonferroni across houses gives at least 95% simultaneous score coverage.
    score_individual_coverage = 1 - (1 - MODEL_COVERAGE) / len(populations) if house_estimates_available else None
    for house in sorted(populations) if house_estimates_available else []:
        row = {'house': house, 'population': populations[house], 'unknown_students': residuals[house],
               'observed_clean_count': known[house]['clean'], 'observed_dirty_count': known[house]['dirty'],
               'observed_red_count': known[house]['red']}
        for category, total in unknown.items():
            observed = known[house].get(category, 0)
            allocation = residuals[house] * total / residual if residual else 0
            interval, bounds = hypergeometric_interval(residual, total, residuals[house])
            row[f'{category}_count'] = observed + allocation
            row[f'{category}_interval'] = [observed + value for value in interval]
            row[f'{category}_bounds'] = [observed + value for value in bounds]
        row['estimated_additional_dirty'] = row['dirty_count'] - row['observed_dirty_count']
        row['total_count'] = sum(row[f'{category}_count'] for category in ('clean', 'dirty', 'red'))
        row['clean_rate'] = 100 * row['clean_count'] / row['total_count'] if row['total_count'] else None
        row['score'] = sum(row[f'{category}_count'] * weight for category, weight in points.items())
        # Possible score bounds respect the fixed category totals jointly.
        observed_score = sum(known[house].get(category, 0) * weight for category, weight in points.items())
        score_bounds = []
        for reverse in (False, True):
            remaining = residuals[house]
            score = observed_score
            for category in sorted(points, key=points.get, reverse=reverse):
                assigned = min(remaining, unknown[category])
                score += assigned * points[category]
                remaining -= assigned
            score_bounds.append(score)
        row['score_bounds'] = score_bounds
        interval, method = score_model_interval(unknown, points, residuals[house], score_individual_coverage)
        row['score_interval'] = [max(score_bounds[0], observed_score + interval[0]),
                                 min(score_bounds[1], observed_score + interval[1])]
        row['score_interval_method'] = method
        result.append(row)
    result = rank_score_intervals(result)
    student_clean = sum(known[house]['clean'] for house in known) + unassigned_counts['clean'] + unknown['clean']
    student_total = school_population - absences
    return {'available': True, 'reason': None, **metadata, 'model': 'conditional_multivariate_hypergeometric',
            'coverage': MODEL_COVERAGE, 'score_coverage': MODEL_COVERAGE if house_estimates_available else None,
            'score_coverage_scope': 'simultaneous_across_houses',
            'score_individual_coverage': score_individual_coverage,
            'house_estimates_available': house_estimates_available,
            'house_estimates_reason': house_estimates_reason,
            'missing_house_count': missing_house_count,
            'excluded_roster_population': excluded_population,
            'resolved_house_count': missing_house_count - excluded_population,
            'unassigned_record_count': unassigned_record_count,
            'unassigned_record_counts': unassigned_counts if unassigned_record_count else None,
            'population': school_population, 'student_plate_count': student_total,
            'student_clean_percentage': 100 * student_clean / student_total if student_total else None,
            'school_absent_count': absences, 'unattributed_counts': {k: v for k, v in unknown.items() if k != 'absent'},
            'observed_dirty_count': sum(known[h]['dirty'] for h in known) + unassigned_counts['dirty'],
            'house_stats': result}
