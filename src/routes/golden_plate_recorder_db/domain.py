from datetime import datetime

from .storage import ensure_session_structure, session_data, student_lookup
from .storage import get_dirty_count  # noqa: F401 - used externally
from .utils import (
    extract_student_id_from_key,
    format_display_name,
    make_student_key,
    normalize_name,
    safe_parse_datetime,
)


def build_profile_from_record(record):
    preferred = normalize_name(record.get('preferred_name') or record.get('first_name'))
    last = normalize_name(record.get('last_name'))
    student_id = normalize_name(record.get('student_id'))
    key = record.get('student_key') or make_student_key(preferred, last, student_id)
    if not student_id and key:
        student_id = extract_student_id_from_key(key)
    profile = {
        'preferred_name': preferred,
        'last_name': last,
        'grade': normalize_name(record.get('grade')),
        'advisor': normalize_name(record.get('advisor')),
        'house': normalize_name(record.get('house')),
        'clan': normalize_name(record.get('clan')),
        'student_id': student_id
    }
    profile['key'] = key
    if key and key in student_lookup:
        lookup = student_lookup[key]
        for field in ['preferred_name', 'last_name', 'grade', 'advisor', 'house', 'clan', 'student_id']:
            if not profile.get(field):
                profile[field] = lookup.get(field, '')
    profile['display_name'] = format_display_name(profile)
    return profile


def is_student_profile_eligible(profile):
    key = profile.get('key')
    if not key:
        return False
    if student_lookup:
        return key in student_lookup
    return True


def compute_ticket_rollups():
    generated_at = datetime.now().isoformat()
    ordered = sorted(
        session_data.items(),
        key=lambda item: (safe_parse_datetime(item[1].get('created_at')), item[0])
    )
    summaries = {}
    current_tickets = {}
    student_profiles = {}
    for session_id, info in ordered:
        ensure_session_structure(info)
        if info.get('is_discarded'):
            summaries[session_id] = {
                'session_id': session_id,
                'session_name': info.get('session_name', ''),
                'created_at': info.get('created_at'),
                'is_discarded': True,
                'tickets_snapshot': {},
                'profiles': {},
                'total_tickets': 0.0,
                'candidates': [],
                'top_candidates': [],
                'eligible_count': 0,
                'excluded_records': 0,
                'generated_at': generated_at
            }
            continue
        pre_session_keys = set(current_tickets.keys())
        present_keys = set()
        excluded_records = 0
        for record in info.get('clean_records', []):
            profile = build_profile_from_record(record)
            key = profile.get('key')
            if not key or not is_student_profile_eligible(profile):
                excluded_records += 1
                continue
            present_keys.add(key)
            student_profiles[key] = profile
            current_tickets[key] = current_tickets.get(key, 0.0) + 1.0
        for record in info.get('red_records', []):
            profile = build_profile_from_record(record)
            key = profile.get('key')
            if not key or not is_student_profile_eligible(profile):
                excluded_records += 1
                continue
            present_keys.add(key)
            student_profiles[key] = profile
            current_tickets[key] = 0.0
        for key in pre_session_keys:
            if key not in present_keys:
                value = current_tickets.get(key, 0.0)
                if value > 0:
                    current_tickets[key] = value / 2.0
        snapshot = {k: float(v) for k, v in current_tickets.items() if v > 0}
        total_tickets = sum(snapshot.values())
        profiles_snapshot = {k: student_profiles.get(k, {}).copy() for k in snapshot}
        candidates = []
        for key, value in sorted(snapshot.items(), key=lambda item: (-item[1], item[0])):
            profile = profiles_snapshot.get(key, {})
            display_name = profile.get('display_name') or format_display_name(profile)
            candidate = {
                'key': key,
                'tickets': value,
                'preferred_name': profile.get('preferred_name', ''),
                'last_name': profile.get('last_name', ''),
                'display_name': display_name,
                'grade': profile.get('grade', ''),
                'advisor': profile.get('advisor', ''),
                'house': profile.get('house', ''),
                'clan': profile.get('clan', ''),
                'student_id': profile.get('student_id', ''),
                'probability': (value / total_tickets * 100.0) if total_tickets > 0 else 0.0
            }
            candidates.append(candidate)
        summaries[session_id] = {
            'session_id': session_id,
            'session_name': info.get('session_name', ''),
            'created_at': info.get('created_at'),
            'is_discarded': False,
            'tickets_snapshot': snapshot,
            'profiles': profiles_snapshot,
            'total_tickets': total_tickets,
            'candidates': candidates,
            'top_candidates': candidates[:3],
            'eligible_count': len(candidates),
            'excluded_records': excluded_records,
            'generated_at': generated_at
        }
        draw_info = info.get('draw_info', {})
        winner = draw_info.get('winner')
        if winner and draw_info.get('finalized'):
            winner_key = winner.get('key')
            if winner_key:
                current_tickets[winner_key] = 0.0
    return summaries


def get_ticket_summary_for_session(session_id):
    summaries = compute_ticket_rollups()
    return summaries.get(session_id), summaries


def serialize_draw_info(draw_info):
    if not isinstance(draw_info, dict):
        return {
            'winner': None,
            'winner_timestamp': None,
            'selected_by': None,
            'method': None,
            'finalized': False,
            'finalized_at': None,
            'finalized_by': None,
            'override': False,
            'tickets_at_selection': None,
            'probability_at_selection': None,
            'eligible_pool_size': None,
            'history': []
        }
    result = {
        'winner_timestamp': draw_info.get('winner_timestamp'),
        'selected_by': draw_info.get('selected_by'),
        'method': draw_info.get('method'),
        'finalized': draw_info.get('finalized', False),
        'finalized_at': draw_info.get('finalized_at'),
        'finalized_by': draw_info.get('finalized_by'),
        'override': draw_info.get('override', False),
        'tickets_at_selection': draw_info.get('tickets_at_selection'),
        'probability_at_selection': draw_info.get('probability_at_selection'),
        'eligible_pool_size': draw_info.get('eligible_pool_size'),
        'history': list(draw_info.get('history', []))
    }
    winner = draw_info.get('winner')
    if isinstance(winner, dict):
        result['winner'] = {
            'key': winner.get('key'),
            'display_name': winner.get('display_name') or format_display_name(winner),
            'preferred_name': winner.get('preferred_name'),
            'last_name': winner.get('last_name'),
            'grade': winner.get('grade'),
            'advisor': winner.get('advisor'),
            'house': winner.get('house'),
            'clan': winner.get('clan'),
            'student_id': winner.get('student_id'),
            'tickets': winner.get('tickets'),
            'probability': winner.get('probability')
        }
    else:
        result['winner'] = None
    return result


__all__ = [
    'build_profile_from_record',
    'compute_ticket_rollups',
    'get_ticket_summary_for_session',
    'is_student_profile_eligible',
    'serialize_draw_info',
]
