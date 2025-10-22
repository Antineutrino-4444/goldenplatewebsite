from datetime import datetime


def normalize_name(value):
    return str(value or '').strip()


def make_student_key(preferred_name, last_name, student_id=None):
    student_id_norm = normalize_name(student_id).lower()
    if student_id_norm:
        return f"id:{student_id_norm}"
    preferred_norm = normalize_name(preferred_name).lower()
    last_norm = normalize_name(last_name).lower()
    if not preferred_norm and not last_norm:
        return None
    return f"{preferred_norm}|{last_norm}"


def split_student_key(key):
    if not key:
        return '', ''
    if key.startswith('id:'):
        return '', ''
    parts = key.split('|', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ''


def extract_student_id_from_key(key):
    if not key:
        return ''
    if key.startswith('id:'):
        return key.split(':', 1)[1]
    return ''


def format_display_name(profile):
    preferred = normalize_name(profile.get('preferred_name') or profile.get('first_name', ''))
    last = normalize_name(profile.get('last_name'))
    if preferred and last:
        return f"{preferred} {last}"
    return preferred or last


def safe_parse_datetime(value):
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except Exception:
            return datetime.min


__all__ = [
    'extract_student_id_from_key',
    'format_display_name',
    'make_student_key',
    'normalize_name',
    'safe_parse_datetime',
    'split_student_key',
]
