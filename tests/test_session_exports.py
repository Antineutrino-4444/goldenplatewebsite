import csv
import io
import uuid
import zipfile

import pytest

from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_ID, DEFAULT_SCHOOL_SLUG, INTERSCHOOL_SCHOOL_ID,
    Session as SessionModel, SessionRecord, Student, User, db_session,
)
from src.routes.golden_plate_recorder_db.session_exports import CSV_HEADER, EXPORT_COLUMNS


URL = '/api/admin/sessions/export'


@pytest.fixture
def export_data(client, login):
    login()
    owner = db_session.query(User).filter_by(username='greenguys').one()
    owner_id, school_id = owner.id, owner.school_id
    session_ids = []
    names = []
    for name in ('Lunch', 'Discarded lunch', 'Extra lunch'):
        name = f'{name} {uuid.uuid4().hex}'
        response = client.post('/api/session/create', json={'session_name': name})
        assert response.status_code == 200
        session_ids.append(response.get_json()['session_id'])
        names.append(name)
    db_session.get(SessionModel, session_ids[1]).status = 'discarded'
    db_session.get(SessionModel, session_ids[2]).main_session_id = session_ids[0]
    students = [Student(
        school_id=school_id, student_identifier=uuid.uuid4().hex,
        preferred_name='Alex', last_name='Doe', grade='9', advisor='Ms Lee',
        house='Barn', clan='Alpha',
    ) for _ in range(2)]
    db_session.add_all(students)
    db_session.flush()
    student_ids = [student.id for student in students]

    def record(session_index, student_index, category='clean', **extra):
        return SessionRecord(
            school_id=school_id, session_id=session_ids[session_index],
            student_id=student_ids[student_index] if student_index is not None else None,
            category=category, recorded_by=owner_id, dedupe_key=uuid.uuid4().hex,
            preferred_name='Alex' if student_index is not None else None,
            last_name='Doe' if student_index is not None else None,
            grade='9', house='Barn', **extra,
        )
    records = [record(0, 0), record(0, 1), record(1, 0, 'red'), record(2, 0, 'dirty'),
               record(0, 0, 'red', is_excluded=1)]
    db_session.add_all(records)
    db_session.commit()
    return {'ids': session_ids, 'names': names, 'students': student_ids, 'owner': owner_id}


def download(client, ids, **options):
    response = client.post(URL, json={'session_ids': ids, **options})
    assert response.status_code == 200
    rows = [dict(zip(CSV_HEADER, row)) for row in csv.reader(io.StringIO(response.get_data(as_text=True)))
            if len(row) == len(CSV_HEADER) and row != CSV_HEADER]
    return response, rows


def test_bulk_export_selection_discard_filter_and_merged_records(client, export_data):
    ids, names = export_data['ids'], export_data['names']
    response = client.get(URL)
    assert response.status_code == 200
    options = {item['session_id']: item for item in response.get_json()['sessions']}
    assert [options[key]['record_count'] for key in ids] == [2, 1, 1]
    assert options[ids[1]]['is_discarded'] is True
    assert all(options[key]['owner'] == 'greenguys' for key in ids)
    assert {column['key'] for column in response.get_json()['columns']} == {key for key, _ in EXPORT_COLUMNS}

    response, rows = download(client, ids)
    assert len(rows) == 4  # Excluded records omitted; merged extras are not duplicated.
    assert {row['Session'] for row in rows} == set(names)
    assert response.headers['X-Export-Session-Count'] == '3'
    assert response.headers['X-Export-Record-Count'] == '4'
    assert response.headers['Cache-Control'] == 'no-store'
    assert all(row['Preferred'] == 'Alex' and row['Last'] == 'Doe' for row in rows)

    _, selected_rows = download(client, [ids[0], ids[2]])
    assert len(selected_rows) == 3
    assert names[1] not in {row['Session'] for row in selected_rows}
    _, filtered = download(client, ids, exclude_discarded=True)
    assert len(filtered) == 3
    assert {row['Session Status'] for row in filtered} == {'Active'}


def test_combined_csv_has_separate_sections_including_empty_sessions(client, export_data):
    empty = client.post('/api/session/create', json={'session_name': 'Empty ' + uuid.uuid4().hex}).get_json()
    ids = export_data['ids'] + [empty['session_id']]
    response, records = download(client, ids)
    raw_rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    headings = [row[0] for row in raw_rows if row and row[0].startswith('Session: ')]
    assert set(headings) == {f'Session: {name}' for name in export_data['names'] + [empty['session_name']]}
    assert raw_rows.count(CSV_HEADER) == 4
    assert raw_rows.count([]) == 3
    assert len(records) == 4
    masked, _ = download(client, ids, anonymize_columns=['Session', 'Session Status'])
    masked_headings = [row for row in csv.reader(io.StringIO(masked.get_data(as_text=True)))
                       if row and row[0].startswith('Session: ')]
    assert all(row[0].startswith('Session: session-') and row[1].startswith('Status: session-status-')
               for row in masked_headings)
    assert all(name not in masked.get_data(as_text=True) for name in export_data['names'])


@pytest.mark.parametrize('anonymize', [[], [key for key, _ in EXPORT_COLUMNS]])
def test_zip_has_one_csv_per_session_and_consistent_labels(client, export_data, anonymize):
    empty = client.post('/api/session/create', json={'session_name': 'Empty ' + uuid.uuid4().hex}).get_json()
    ids = export_data['ids'] + [empty['session_id']]
    response = client.post(URL, json={'session_ids': ids, 'format': 'zip', 'anonymize_columns': anonymize})
    assert response.status_code == 200
    assert response.mimetype == 'application/zip'
    assert response.headers['Content-Disposition'].endswith('.zip"')
    assert response.headers['X-Export-Record-Count'] == '4'
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        files = archive.namelist()
        assert len(files) == len(set(files)) == 4
        assert all(name.endswith('.csv') and '/' not in name and '\\' not in name for name in files)
        tables = [list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8')))) for name in files]
        assert sorted(len(table) for table in tables) == [0, 1, 1, 2]
        rows = [row for table in tables for row in table]
        people = [row['Person'] for row in rows]
        assert sorted(people.count(person) for person in set(people)) == [1, 3]
        if anonymize:
            assert all('_session-' in name for name in files)
            assert len({row['House'] for row in rows}) == 1
            assert len({row['Preferred'] for row in rows}) == 2
            content = '\n'.join(archive.read(name).decode('utf-8') for name in files)
            assert all(value not in content for value in export_data['names'] + ['Alex', 'Doe', 'Ms Lee', 'Barn', 'greenguys'])
            assert all(name not in '\n'.join(files) for name in export_data['names'])


def test_zip_discard_filter_and_safe_unique_filenames(client, export_data):
    ids = export_data['ids']
    db_session.get(SessionModel, ids[0]).session_name = '../secret/path'
    db_session.get(SessionModel, ids[2]).session_name = '..\\secret\\path'
    db_session.commit()
    response = client.post(URL, json={'session_ids': ids, 'format': 'zip', 'exclude_discarded': True})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert len(archive.namelist()) == 2
        assert all('/' not in name and '\\' not in name and not name.startswith('.') for name in archive.namelist())
        rows = [row for name in archive.namelist()
                for row in csv.DictReader(io.StringIO(archive.read(name).decode('utf-8')))]
        assert len(rows) == 3
        assert all(row['Session Status'] == 'Active' for row in rows)


def test_anonymization_is_person_specific_consistent_and_fresh(client, export_data):
    ids = export_data['ids']
    response, rows = download(client, ids, anonymize_columns=['Preferred', 'Last', 'House'])
    first_session = [row for row in rows if row['Session'] == export_data['names'][0]]
    assert len({row['Person'] for row in first_session}) == 2
    assert len({row['Preferred'] for row in first_session}) == 2
    assert len({row['Last'] for row in first_session}) == 2
    repeated_person = next(row for row in rows if row['Session'] == export_data['names'][1])
    matches = [row for row in rows if row['Person'] == repeated_person['Person']]
    assert len(matches) == 3
    assert len({row['Preferred'] for row in matches}) == 1
    assert len({row['Last'] for row in matches}) == 1
    assert len({row['House'] for row in rows}) == 1
    assert all(row['House'] != 'Barn' and row['Preferred'] != 'Alex' and row['Last'] != 'Doe' for row in rows)
    assert all(row['Grade'] == '9' and row['Advisor'] == 'Ms Lee' and row['Recorded By'] == 'greenguys' for row in rows)
    for internal_id in export_data['students'] + [export_data['owner']]:
        assert internal_id not in response.get_data(as_text=True)
    _, another = download(client, ids, anonymize_columns=['Preferred', 'Last', 'House'])
    assert {row['Person'] for row in rows}.isdisjoint({row['Person'] for row in another})
    assert {row['House'] for row in rows}.isdisjoint({row['House'] for row in another})
    assert db_session.query(Student).filter(Student.id.in_(export_data['students'])).first().preferred_name == 'Alex'


@pytest.mark.parametrize('column', [key for key, _ in EXPORT_COLUMNS])
def test_each_column_can_be_anonymized_independently(client, export_data, column):
    _, rows = download(client, [export_data['ids'][0]], anonymize_columns=[column])
    assert all(row[column].startswith(column.lower().replace(' ', '-') + '-') for row in rows)
    assert all(row['Preferred'] == 'Alex' for row in rows) if column != 'Preferred' else True
    assert all(row['Last'] == 'Doe' for row in rows) if column != 'Last' else True


def test_anonymize_all_blanks_count_only_and_csv_escaping(client, export_data):
    session_id = export_data['ids'][0]
    record = SessionRecord(
        school_id=DEFAULT_SCHOOL_ID, session_id=session_id, category='faculty',
        recorded_by=export_data['owner'], dedupe_key='count:faculty:' + uuid.uuid4().hex,
    )
    db_session.add(record)
    db_session.commit()
    _, rows = download(client, [session_id], anonymize_columns=[key for key, _ in EXPORT_COLUMNS])
    assert len(rows) == 3
    for row in rows:
        for key, _ in EXPORT_COLUMNS:
            assert row[key] == '' or row[key].startswith(key.lower().replace(' ', '-') + '-')
    count_only = next(row for row in rows if not row['Person'])
    assert count_only['Last'] == count_only['Grade'] == count_only['House'] == ''
    db_session.get(SessionModel, session_id).session_name = '=HYPERLINK("untrusted")'
    db_session.commit()
    _, readable = download(client, [session_id])
    assert all(row['Session'] == '\'=HYPERLINK("untrusted")' for row in readable)


def test_legacy_dirty_counts_do_not_reintroduce_excluded_rows(client, export_data):
    session_id = export_data['ids'][0]
    db_session.get(SessionModel, session_id).dirty_number = 4
    db_session.add(SessionRecord(
        school_id=DEFAULT_SCHOOL_ID, session_id=session_id, category='dirty',
        recorded_by=export_data['owner'], dedupe_key='count:dirty:' + uuid.uuid4().hex,
        is_excluded=1,
    ))
    db_session.commit()
    _, rows = download(client, [session_id])
    legacy = [row for row in rows if row['Category'] == 'DIRTY']
    assert len(legacy) == 1 and legacy[0]['Preferred'] == 'Count: 3'
    assert legacy[0]['Person'] == ''


def test_export_school_isolation_and_no_partial_download(client, export_data):
    other_owner = db_session.query(User).filter_by(school_id=INTERSCHOOL_SCHOOL_ID).first()
    foreign = SessionModel(school_id=INTERSCHOOL_SCHOOL_ID, created_by=other_owner.id,
                           session_name=uuid.uuid4().hex)
    db_session.add(foreign)
    db_session.commit()
    foreign_id = foreign.id
    assert foreign_id not in {item['session_id'] for item in client.get(URL).get_json()['sessions']}
    response = client.post(URL, json={'session_ids': export_data['ids'] + [foreign_id]})
    assert response.status_code == 404
    assert response.is_json


@pytest.mark.parametrize('payload', [
    None, [], {}, {'session_ids': []}, {'session_ids': 'all'}, {'session_ids': [123]},
    {'session_ids': ['missing'], 'anonymize_columns': ['Student ID']},
    {'session_ids': ['missing'], 'anonymize_columns': 'all'},
    {'session_ids': ['missing'], 'exclude_discarded': 'true'},
    {'session_ids': ['missing'], 'format': 'pdf'},
    {'session_ids': ['missing'], 'format': []},
])
def test_export_validates_options(client, login, payload):
    login()
    assert client.post(URL, json=payload).status_code == 400


def test_empty_selection_after_discard_filter_is_reported(client, export_data):
    response = client.post(URL, json={'session_ids': [export_data['ids'][1]], 'exclude_discarded': True})
    assert response.status_code == 400
    assert 'No sessions remain' in response.get_json()['error']


def test_export_requires_school_admin_and_supports_admin_role(client, export_data):
    owner_id = export_data['owner']
    db_session.get(User, owner_id).role = 'admin'
    db_session.commit()
    try:
        assert client.get(URL).status_code == 200
        assert client.post(URL, json={'session_ids': export_data['ids']}).status_code == 200
        db_session.get(User, owner_id).role = 'user'
        db_session.commit()
        assert client.get(URL).status_code == 403
        assert client.post(URL, json={'session_ids': export_data['ids']}).status_code == 403
    finally:
        db_session.get(User, owner_id).role = 'superadmin'
        db_session.commit()
    client.post('/api/auth/logout')
    assert client.get(URL).status_code == 403
    client.post('/api/auth/guest', json={'school_slug': DEFAULT_SCHOOL_SLUG})
    assert client.post(URL, json={'session_ids': export_data['ids']}).status_code == 403
