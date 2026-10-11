"""Detailed exports with identities scoped to a single downloaded file."""
import csv
import hashlib
import hmac
import io
import json
import re
import secrets
import zipfile

from sqlalchemy import and_, func

from .db import SessionRecord, Student, db_session
from .storage import _extract_faculty_names
from .users import readable_user_label, user_labels_for_school
from .utils import normalize_house, normalize_name, plate_count_label, split_student_key


EXPORT_COLUMNS = [
    ('Session', 'Session name'),
    ('Session Status', 'Session status'),
    ('Category', 'Plate category'),
    ('Last', 'Last name'),
    ('Preferred', 'First / preferred name'),
    ('Grade', 'Grade'),
    ('Advisor', 'Advisor'),
    ('House', 'House'),
    ('Clan', 'Clan'),
    ('Recorded At', 'Recording date and time'),
    ('Recorded By', 'Recorded by'),
    ('Manual Entry', 'Manual entry'),
]
CSV_HEADER = ['Session', 'Session Status', 'Person'] + [name for name, _ in EXPORT_COLUMNS[2:]]


def record_counts_for_sessions(sessions, school_id):
    """Include legacy count-only dirty plates, without resurrecting excluded rows."""
    counts = {item.id: {'included': 0, 'dirty': 0} for item in sessions}
    if not counts:
        return counts
    groups = (
        db_session.query(SessionRecord.session_id, SessionRecord.category,
                         SessionRecord.is_excluded, func.count(SessionRecord.id))
        .filter(SessionRecord.school_id == school_id, SessionRecord.session_id.in_(counts))
        .group_by(SessionRecord.session_id, SessionRecord.category, SessionRecord.is_excluded)
        .all()
    )
    for session_id, category, excluded, count in groups:
        if not excluded:
            counts[session_id]['included'] += count
        if category == 'dirty':
            counts[session_id]['dirty'] += count
    for item in sessions:
        remaining = max(0, (item.dirty_number or 0) - counts[item.id]['dirty'])
        counts[item.id]['legacy_dirty'] = remaining
        counts[item.id]['included'] += int(remaining > 0)
    return counts


class ExportLabels:
    def __init__(self):
        # Never persist or export this key. Unsalted hashes of names are guessable.
        self.key = secrets.token_bytes(32)

    def label(self, column, value):
        encoded = json.dumps([column, value], ensure_ascii=False).encode('utf-8')
        digest = hmac.new(self.key, encoded, hashlib.sha256).hexdigest()[:32]
        return f'{column.lower().replace(" ", "-")}-{digest}'


def _spreadsheet_safe(value):
    text = str(value) if value is not None else ''
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


def detailed_sessions_export(sessions, school_id, anonymize_columns, export_format='csv'):
    session_map = {item.id: item for item in sessions}
    user_labels = user_labels_for_school(school_id)
    counts = record_counts_for_sessions(sessions, school_id)
    records = (
        db_session.query(SessionRecord, Student)
        .outerjoin(Student, and_(SessionRecord.student_id == Student.id, Student.school_id == school_id))
        .filter(SessionRecord.school_id == school_id, SessionRecord.session_id.in_(session_map),
                SessionRecord.is_excluded == 0)
        .order_by(SessionRecord.recorded_at.desc(), SessionRecord.id.asc())
        .all()
    )
    labels = ExportLabels()
    session_rows = {item.id: [] for item in sessions}

    def add_row(session_id, row, person_key=None):
        row['Person'] = labels.label('person', person_key) if person_key else ''
        for column in anonymize_columns:
            if row[column] != '':
                # Names are person-specific, so two students named Alex stay distinct.
                value = person_key if column in ('Preferred', 'Last') and person_key else row[column]
                row[column] = labels.label(column, value)
        session_rows[session_id].append([_spreadsheet_safe(row.get(column, '')) for column in CSV_HEADER])

    for record, student in records:
        item = session_map[record.session_id]
        faculty = record.category == 'faculty'
        count_only = not (record.student_id or record.preferred_name or record.last_name) and (
            (record.dedupe_key or '').startswith('count:') or record.category == 'dirty'
        )
        preferred = normalize_name(record.preferred_name or (student.preferred_name if student else ''))
        last = normalize_name(record.last_name or (student.last_name if student else ''))
        if not count_only and (not preferred or not last):
            legacy_preferred, legacy_last = (
                _extract_faculty_names(record.dedupe_key) if faculty else split_student_key(record.dedupe_key)
            )
            preferred = preferred or normalize_name(legacy_preferred)
            last = last or normalize_name(legacy_last)
        person_key = None
        if not count_only and (preferred or last or record.student_id):
            if record.student_id:
                person_key = ['student', record.student_id]
            else:
                person_key = ['faculty' if faculty else 'student-name', preferred.casefold(), last.casefold()]
        row = {
            'Session': item.session_name,
            'Session Status': 'Discarded' if item.status == 'discarded' else 'Active',
            'Category': record.category.upper(),
            'Last': last,
            'Preferred': preferred if preferred or last else plate_count_label(record.category),
            'Grade': '' if faculty else normalize_name(record.grade or (student.grade if student else '')),
            'Advisor': '' if faculty or not student else normalize_name(student.advisor),
            'House': '' if faculty else normalize_house(record.house or (student.house if student else '')),
            'Clan': '' if faculty or not student else normalize_name(student.clan),
            'Recorded At': record.recorded_at.isoformat() if record.recorded_at else '',
            'Recorded By': readable_user_label(record.recorded_by, labels=user_labels),
            'Manual Entry': 'Yes' if record.is_manual_entry else 'No',
        }
        add_row(item.id, row, person_key)

    for item in sessions:
        remaining = counts[item.id]['legacy_dirty']
        if remaining:
            row = {column: '' for column in CSV_HEADER}
            row.update({'Session': item.session_name,
                        'Session Status': 'Discarded' if item.status == 'discarded' else 'Active',
                        'Category': 'DIRTY', 'Preferred': f'Count: {remaining}'})
            add_row(item.id, row)

    def session_label(column, value):
        return labels.label(column, value) if column in anonymize_columns else value

    row_count = sum(len(rows) for rows in session_rows.values())
    if export_format == 'zip':
        archive_output = io.BytesIO()
        with zipfile.ZipFile(archive_output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for index, item in enumerate(sessions, 1):
                name = session_label('Session', item.session_name)
                safe_name = re.sub(r'[^\w. -]', '_', name).strip(' .-_')[:100] or 'session'
                output = io.StringIO(newline='')
                writer = csv.writer(output)
                writer.writerow(CSV_HEADER)
                writer.writerows(session_rows[item.id])
                archive.writestr(f'{index:03d}_{safe_name}.csv', output.getvalue().encode('utf-8'))
        return archive_output.getvalue(), row_count

    output = io.StringIO(newline='')
    writer = csv.writer(output)
    for index, item in enumerate(sessions):
        if index:
            writer.writerow([])
        name = session_label('Session', item.session_name)
        status = session_label('Session Status', 'Discarded' if item.status == 'discarded' else 'Active')
        writer.writerow([f'Session: {name}', f'Status: {status}'])
        writer.writerow(CSV_HEADER)
        writer.writerows(session_rows[item.id])
    return output.getvalue(), row_count
