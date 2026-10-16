"""Exact conditional clean percentages under a joint finite-population allocation.

Dirty and red are both non-clean participants for this statistic. Summing over
their split is exact (Vandermonde's identity), not an independence approximation.
No simulation or floating-point probabilities are used for quantiles or ties.
"""

from bisect import bisect_left
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import comb


@dataclass(frozen=True)
class PercentageDistribution:
    values: tuple
    cumulative_weights: tuple
    participant_weight: int
    total_weight: int
    expected_percentage: Fraction | None

    @property
    def zero_participation_probability(self):
        return Fraction(self.total_weight - self.participant_weight, self.total_weight)

    def interval(self, coverage_steps=900):
        """Equal-tail interval; coverage_steps / 1000 is nominal coverage."""
        if not 1 <= coverage_steps <= 1000:
            raise ValueError('Coverage must be on the 0.1% through 100% grid.')
        if not self.participant_weight:
            return None
        if coverage_steps == 1000:
            return self.values[0], self.values[-1]
        tail = 1000 - coverage_steps
        targets = (tail, 2000 - tail)
        return tuple(self.values[bisect_left(
            self.cumulative_weights,
            (self.participant_weight * target + 1999) // 2000,
        )] for target in targets)

    def rounded_percentage_key(self):
        """Round percentages to three decimals, with exact half-up ties."""
        value = self.expected_percentage
        if value is None:
            return None
        return (value.numerator * 2000 + value.denominator) // (2 * value.denominator)


@lru_cache(maxsize=64)
def clean_percentage_distribution(clean, nonclean, absent, capacity,
                                  observed_clean=0, observed_nonclean=0):
    """A house marginal of the joint CLEAN/DIRTY/RED/absence allocation.

    Each feasible (clean, nonclean, absent) allocation has its exact number of
    compatible population subsets as weight. Zero-participant outcomes retain
    their probability but are omitted from the conditional percentage law.
    """
    inputs = (clean, nonclean, absent, capacity, observed_clean, observed_nonclean)
    if any(not isinstance(value, int) or value < 0 for value in inputs):
        raise ValueError('Population and plate counts must be nonnegative integers.')
    population = clean + nonclean + absent
    if capacity > population:
        raise ValueError('House capacity exceeds the unresolved population.')
    total_weight = comb(population, capacity)
    known_participants = observed_clean + observed_nonclean
    masses = {}
    clean_choices = [comb(clean, count) for count in range(min(clean, capacity) + 1)]
    other_choices = [comb(nonclean, count) for count in range(min(nonclean, capacity) + 1)]
    absent_choices = [comb(absent, count) for count in range(min(absent, capacity) + 1)]
    for clean_count in range(max(0, capacity - nonclean - absent), min(clean, capacity) + 1):
        for other_count in range(max(0, capacity - clean_count - absent),
                                 min(nonclean, capacity - clean_count) + 1):
            participants = known_participants + clean_count + other_count
            if not participants:
                continue
            weight = (clean_choices[clean_count] * other_choices[other_count]
                      * absent_choices[capacity - clean_count - other_count])
            percentage = Fraction(100 * (observed_clean + clean_count), participants)
            masses[percentage] = masses.get(percentage, 0) + weight
    ordered = sorted(masses.items())
    participant_weight = sum(masses.values())
    cumulative = []
    running = 0
    for _, weight in ordered:
        running += weight
        cumulative.append(running)
    expectation = (sum((value * weight for value, weight in ordered), Fraction(0))
                   / participant_weight) if participant_weight else None
    return PercentageDistribution(tuple(value for value, _ in ordered), tuple(cumulative),
                                  participant_weight, total_weight, expectation)


def rank_percentages(rows, distributions):
    ranked = [row for row in rows if distributions[row['house']].participant_weight]
    unranked = [row for row in rows if not distributions[row['house']].participant_weight]
    ranked.sort(key=lambda row: (-distributions[row['house']].rounded_percentage_key(), row['house']))
    previous_key = None
    rank = None
    for index, row in enumerate(ranked):
        key = distributions[row['house']].rounded_percentage_key()
        if key != previous_key:
            rank = index + 1
        row['percentage_rank'] = rank
        previous_key = key
    for row in unranked:
        row['percentage_rank'] = None
    return ranked + sorted(unranked, key=lambda row: row['house'])


def add_rank_ranges(rows, distributions):
    """Conservative 90% simultaneous ranges for ranks among participating houses.

    Allocate at most 10% / n failure probability to each marginal interval,
    rounding coverage up on the supported grid. The union bound does not
    assume independent house allocations. A potentially absent house cannot
    be counted as certainly ahead. Exact ties share competition ranks.
    """
    ranked = [row for row in rows if distributions[row['house']].participant_weight]
    level = 1000 - 100 // len(ranked) if ranked else 1000
    intervals = {row['house']: distributions[row['house']].interval(level) for row in ranked}
    for row in rows:
        house = row['house']
        if house not in intervals:
            row.update(rank_range=None, rank_percentage_interval=None, overlapping_houses=[],
                       tied_houses=[], ranking_uncertain=False)
            continue
        low, high = intervals[house]
        others = [other['house'] for other in ranked if other['house'] != house]
        ahead = [name for name in others if intervals[name][0] > high
                 and not distributions[name].zero_participation_probability]
        possibly_ahead = [name for name in others if intervals[name][1] > low]
        row['rank_range'] = [1 + len(ahead), 1 + len(possibly_ahead)]
        row['rank_percentage_interval'] = [float(low), float(high)]
        row['overlapping_houses'] = sorted(name for name in others
                                          if intervals[name][0] <= high and intervals[name][1] >= low)
        row['tied_houses'] = sorted(name for name in others
                                   if distributions[name].rounded_percentage_key()
                                   == distributions[house].rounded_percentage_key())
        row['ranking_uncertain'] = row['rank_range'][0] != row['rank_range'][1]
    return rows


def highest_separating_coverage(rows, distributions):
    ranked = [row for row in rows if row['percentage_rank'] is not None]
    if len(ranked) < 2:
        return {'available': False, 'coverage_percentage': None,
                'reason': 'At least two ranked houses are needed to compare intervals.'}
    if len({row['percentage_rank'] for row in ranked}) != len(ranked):
        return {'available': False, 'coverage_percentage': None,
                'reason': 'No fully separating level is available because predicted percentages are tied.'}

    def separates(level):
        intervals = [distributions[row['house']].interval(level) for row in ranked]
        return all(higher[0] > lower[1] for higher, lower in zip(intervals, intervals[1:]))

    if not separates(1):
        return {'available': False, 'coverage_percentage': None,
                'reason': 'No fully separating level is available on the supported 0.1% to 100% grid.'}
    # Equal-tail intervals are nested. Binary search is equivalent to checking
    # every grid level, with strict comparisons of exact rational endpoints.
    low, high = 1, 1000
    while low < high:
        middle = (low + high + 1) // 2
        if separates(middle):
            low = middle
        else:
            high = middle - 1
    return {'available': True, 'coverage_percentage': low / 10, 'reason': None}
