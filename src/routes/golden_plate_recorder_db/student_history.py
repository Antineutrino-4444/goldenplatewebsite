"""Immutable recording profiles and school-scoped current-roster comparisons."""
import json
from collections import defaultdict

from sqlalchemy import and_

from .db import SessionRecord, Student, db_session
from .utils import extract_student_id_from_key, normalize_house, normalize_name, split_student_key


PROFILE_FIELDS = {
    'Student ID': 'student_identifier', 'Preferred': 'preferred_name', 'Last': 'last_name',
    'Grade': 'grade', 'Advisor': 'advisor', 'House': 'house', 'Clan': 'clan',
}
LEGACY_NOTE = ('Legacy record: a complete recording-time profile was not saved; '
               'unsaved fields use the last known roster and may already have changed')


def _json(value, default):
    try:
        decoded = json.loads(value or 'null')
        return decoded if isinstance(decoded, type(default)) else default
    except (ValueError, TypeError):
        return default


def student_profile(student):
    return {label: (normalize_house if label == 'House' else normalize_name)(
        getattr(student, field, '') if student else '') for label, field in PROFILE_FIELDS.items()}


def recorded_profile(record, student=None):
    saved = _json(record.student_profile, {})
    if saved:
        return saved
    profile = student_profile(student)
    key_identifier = extract_student_id_from_key(record.dedupe_key)
    if key_identifier and key_identifier.casefold() != profile['Student ID'].casefold():
        profile['Student ID'] = key_identifier
    for label, field in [('Preferred', 'preferred_name'), ('Last', 'last_name'),
                         ('Grade', 'grade'), ('House', 'house')]:
        value = getattr(record, field)
        if value is not None:
            profile[label] = (normalize_house if label == 'House' else normalize_name)(value)
    first, last = split_student_key(record.dedupe_key)
    profile['Preferred'] = profile['Preferred'] or first
    profile['Last'] = profile['Last'] or last
    profile['_history_note'] = LEGACY_NOTE
    profile['_roster_conflicts'] = _json(student.roster_conflicts, []) if student else []
    return profile


def preserve_legacy_profiles(school_id):
    """Freeze still-available legacy details before the next roster replacement."""
    records = (db_session.query(SessionRecord, Student)
               .outerjoin(Student, and_(SessionRecord.student_id == Student.id,
                                       Student.school_id == school_id))
               .filter(SessionRecord.school_id == school_id,
                       SessionRecord.student_profile.is_(None),
                       SessionRecord.category != 'faculty').all())
    for record, student in records:
        if record.student_id or record.preferred_name or record.last_name or extract_student_id_from_key(record.dedupe_key):
            record.student_profile = json.dumps(recorded_profile(record, student), ensure_ascii=False)


class RosterComparison:
    def __init__(self, school_id):
        self.by_id = defaultdict(list)
        self.by_name = defaultdict(list)
        for student in db_session.query(Student).filter_by(school_id=school_id, is_active=1).all():
            self.by_id[normalize_name(student.student_identifier).casefold()].append(student)
            self.by_name[self.name_key(student_profile(student))].append(student)

    @staticmethod
    def name_key(profile):
        return tuple(normalize_name(profile.get(field)).casefold() for field in ('Preferred', 'Last'))

    def compare(self, record, student):
        profile = recorded_profile(record, student)
        identifier = normalize_name(profile.get('Student ID'))
        name_key = self.name_key(profile)
        names = self.by_name.get(name_key, []) if all(name_key) else []
        notes = []
        if profile.get('_history_note'):
            notes.append([(None, profile['_history_note'])])
        if profile.get('_matched_by_name'):
            notes.append([(None, 'Recording matched a unique full name; no Student ID was supplied')])
        candidates = profile.get('_recording_candidates') or []
        if candidates:
            parts = [(None, 'Conflict: recording had multiple full-name matches; no Student ID assigned: ')]
            for index, candidate in enumerate(candidates):
                if index:
                    parts.append((None, ', '))
                parts.append(('Student ID', candidate))
            notes.append(parts)
        matched = None
        if identifier:
            matches = self.by_id.get(identifier.casefold(), [])
            if len(matches) == 1:
                matched = matches[0]
                status = 'Current'
                notes.append([(None, 'Matched by Student ID')])
                if record.student_id and student and student.id != matched.id:
                    notes.append([(None, 'Conflict: saved student link disagrees with Student ID; ID takes priority')])
                if names and matched not in names:
                    notes.append(self.candidates('Conflict: recorded name points to other current Student IDs', names))
            elif matches:
                status = 'Unresolved'
                notes.append(self.candidates('Conflict: multiple current students share Student ID', matches))
            else:
                status = 'Old'
                notes.append([(None, 'Student ID is absent from the current roster')])
                if names:
                    notes.append(self.candidates('Conflict: same name has different current Student IDs; identities were not merged', names))
        elif names:
            # Supporting fields can distinguish namesakes, but never override a known ID.
            def score(candidate):
                current = student_profile(candidate)
                return sum(bool(profile.get(field)) and normalize_name(profile[field]).casefold() ==
                           normalize_name(current[field]).casefold()
                           for field in ('Grade', 'Advisor', 'House', 'Clan'))
            scores = [(score(candidate), candidate) for candidate in names]
            best = max(value for value, _ in scores)
            finalists = [candidate for value, candidate in scores if value == best]
            if len(finalists) == 1:
                matched = finalists[0]
                status = 'Current'
                notes.append([(None, 'No saved Student ID: matched by full name and available supporting fields; identity is unverified')])
                if len(names) > 1:
                    notes.append(self.candidates('Conflict: multiple full-name matches; supporting fields favored one candidate', names))
            else:
                status = 'Unresolved'
                notes.append(self.candidates('Conflict: no saved Student ID and ambiguous full-name matches; no identity assigned', names))
        else:
            status = 'Unresolved'
            notes.append([(None, 'No saved Student ID and no full-name match; current membership cannot be verified')])

        if student and identifier and normalize_name(student.student_identifier).casefold() != identifier.casefold():
            notes.append([(None, 'Conflict: saved student link now has a different Student ID: '),
                          ('Student ID', student.student_identifier), (None, '; original ID retained')])
        house_changed = ''
        if matched:
            current = student_profile(matched)
            house_changed = 'Yes' if profile.get('House', '') != current['House'] else 'No'
            for field in PROFILE_FIELDS:
                if field == 'Student ID':
                    continue
                if profile.get(field, '') != current[field]:
                    notes.append([(None, f'{field} changed: '), (field, profile.get(field, '')),
                                  (None, ' -> '), (field, current[field])])
        conflicts = list(profile.get('_roster_conflicts') or [])
        if matched:
            conflicts.extend(_json(matched.roster_conflicts, []))
        for conflict in conflicts:
            field = conflict.get('field')
            if field in PROFILE_FIELDS:
                notes.append([(None, f'Conflict: duplicate roster rows disagree on {field}: '),
                              (field, conflict.get('kept', '')), (None, ' / '),
                              (field, conflict.get('other', '')), (None, '; first row retained')])
        for conflict in profile.get('_recording_conflicts') or []:
            field = conflict.get('field')
            if field in PROFILE_FIELDS:
                notes.append([(None, f'Conflict: recording supplied a different {field}: '),
                              (field, conflict.get('other', '')), (None, '; ID-priority value retained: '),
                              (field, conflict.get('kept', ''))])
        return profile, status, house_changed, notes

    @staticmethod
    def candidates(message, students):
        parts = [(None, message + ': ')]
        for index, student in enumerate(students):
            if index:
                parts.append((None, ', '))
            parts.append(('Student ID', student.student_identifier))
        return parts


def render_roster_notes(notes, mask=lambda field, value: value):
    """Mask field values inside notes using the same export choices as their columns."""
    messages = []
    for parts in notes:
        message = ''.join(str(mask(field, value)) if field and value != '' else
                          ('(blank)' if field else str(value)) for field, value in parts)
        if message not in messages:
            messages.append(message)
    return '; '.join(messages)
