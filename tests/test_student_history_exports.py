import csv
import io
import json
import re
import uuid
import zipfile

import pytest

from src.routes.golden_plate_recorder_db import storage
from src.routes.golden_plate_recorder_db.db import (
    DEFAULT_SCHOOL_ID, School, SessionRecord, Student, User, db_session,
)
from src.routes.golden_plate_recorder_db.session_exports import CSV_HEADER


FIELDS = ['Student ID', 'Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan']
OLD = [
    ['9701', 'Original', 'Alex', '9', 'Old Advisor', 'Barn', 'Alpha'],
    ['9702', 'Departed', 'Jordan', '10', 'Other Advisor', 'Hall', 'Beta'],
]
NEW = [['9701', 'Updated', 'Avery', '11', 'New Advisor', 'Hall', 'Gamma']]


def upload(client, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(FIELDS)
    writer.writerows(rows)
    response = client.post('/api/csv/upload', data={'file': (io.BytesIO(output.getvalue().encode()), 'roster.csv')})
    assert response.status_code == 200, response.get_json()


def create_session(client):
    response = client.post('/api/session/create', json={'session_name': uuid.uuid4().hex})
    assert response.status_code == 200
    return response.get_json()['session_id']


def export(client, session_id, format='csv', anonymize=()):
    if format == 'single':
        response = client.get('/api/export/csv/detailed')
        assert response.status_code == 200
        return list(csv.DictReader(io.StringIO(response.get_data(as_text=True))))
    response = client.post('/api/admin/sessions/export', json={
        'session_ids': [session_id], 'format': format, 'anonymize_columns': list(anonymize),
    })
    assert response.status_code == 200
    if format == 'zip':
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            return list(csv.DictReader(io.StringIO(archive.read(archive.namelist()[0]).decode())))
    return [dict(zip(CSV_HEADER, row)) for row in csv.reader(io.StringIO(response.get_data(as_text=True)))
            if len(row) == len(CSV_HEADER) and row != CSV_HEADER]


@pytest.mark.parametrize('format', ['single', 'csv', 'zip'])
def test_recorded_profiles_survive_roster_replacement_and_return(client, login, format):
    login()
    upload(client, OLD)
    meal = create_session(client)
    for identifier in ('9701', '9702'):
        assert client.post('/api/record/clean', json={'input_value': identifier}).status_code == 200
    original_ids = {s.student_identifier: s.id for s in db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID).all()}
    upload(client, NEW)
    # Names follow the permanent person link; recording-time facts remain snapshots.
    storage.session_data.clear()
    rows = {row['Student ID']: row for row in export(client, meal, format)}
    assert rows['9701']['Roster Status'] == 'Current'
    assert rows['9701']['House Changed'] == 'Yes'
    for key, value in zip(FIELDS, OLD[0]):
        assert rows['9701'][key] == (NEW[0][FIELDS.index(key)] if key in ('Preferred', 'Last') else value)
    for field in ('Last', 'Preferred', 'Grade', 'Advisor', 'House', 'Clan'):
        assert f'{field} changed:' in rows['9701']['Roster Notes']
    assert 'House changed: Barn -> Hall' in rows['9701']['Roster Notes']
    assert rows['9702']['Roster Status'] == 'Old'
    assert 'Legacy record' not in rows['9701']['Roster Notes']
    hydrated = storage.hydrate_session_from_db(meal, persist=False)['clean_records']
    assert {row['student_id']: row['advisor'] for row in hydrated} == {'9701': 'Old Advisor', '9702': 'Other Advisor'}
    assert {row['student_id']: row['house'] for row in hydrated} == {'9701': 'Barn', '9702': 'Hall'}
    upload(client, NEW + [OLD[1]])
    rows = {row['Student ID']: row for row in export(client, meal, format)}
    assert rows['9702']['Roster Status'] == 'Current'
    assert rows['9702']['House Changed'] == 'No'
    assert all(db_session.get(Student, sid).student_identifier == identifier for identifier, sid in original_ids.items())
    # Later recordings use the new profile while keeping the same identity.
    later = create_session(client)
    assert client.post('/api/record/red', json={'input_value': '9701'}).status_code == 200
    current = export(client, later)[0]
    assert current['Preferred'] == 'Avery' and current['Grade'] == '11'
    assert current['House'] == 'Hall' and current['House Changed'] == 'No'


def test_blank_recorded_fields_do_not_take_future_roster_values(client, login):
    login()
    upload(client, [['9701', 'Original', 'Alex', '', '', '', '']])
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    upload(client, NEW)
    storage.session_data.clear()
    row = export(client, meal)[0]
    assert all(row[field] == '' for field in ['Grade', 'Advisor', 'House', 'Clan'])
    assert row['House Changed'] == 'Yes' and 'House changed: (blank) -> Hall' in row['Roster Notes']


def test_known_id_never_merges_with_same_name_using_different_id(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    upload(client, [['9799'] + OLD[0][1:]])
    row = export(client, meal)[0]
    assert row['Student ID'] == '9701' and row['Roster Status'] == 'Old'
    assert 'different current Student IDs' in row['Roster Notes'] and '9799' in row['Roster Notes']


@pytest.mark.parametrize('format', ['csv', 'zip'])
def test_anonymization_also_masks_values_inside_roster_notes(client, login, format):
    login()
    upload(client, OLD)
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    upload(client, NEW + [['9799'] + OLD[0][1:]])
    masked_fields = ['Preferred', 'Last', 'Student ID', 'House', 'Advisor', 'Clan']
    row = export(client, meal, format, masked_fields)[0]
    text = '\n'.join(row.values())
    assert all(value not in text for value in ['Alex', 'Avery', 'Original', 'Updated',
                                             'Barn', 'Hall', 'Old Advisor', 'New Advisor', 'Alpha', 'Gamma'])
    # Random hexadecimal labels can contain the same digits as a school ID.
    assert not re.search(r'(?<![a-zA-Z0-9])(?:9701|9799)(?![a-zA-Z0-9])', text)
    assert row['House'] in row['Roster Notes'] and row['Preferred'] in row['Roster Notes']
    assert row['Grade'] == '9' and 'Grade changed: 9 -> 11' in row['Roster Notes']
    assert row['Roster Status'] == 'Current'


def test_legacy_profiles_are_frozen_before_upload_and_uncertainty_is_noted(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    student = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='9701').one()
    owner = db_session.query(User).filter_by(username='greenguys').one()
    record = SessionRecord(school_id=DEFAULT_SCHOOL_ID, session_id=meal, student_id=student.id,
                           category='clean', preferred_name='Historical', last_name='Original',
                           grade='8', house='Barn', recorded_by=owner.id, dedupe_key='id:9701')
    db_session.add(record)
    db_session.commit()
    record_id = record.id
    upload(client, NEW)
    profile = json.loads(db_session.get(SessionRecord, record_id).student_profile)
    assert profile['Preferred'] == 'Historical' and profile['Grade'] == '8'
    assert profile['Advisor'] == 'Old Advisor' and profile['Clan'] == 'Alpha'
    row = export(client, meal, 'single')[0]
    assert row['Advisor'] == 'Old Advisor' and row['Clan'] == 'Alpha'
    assert 'Legacy record' in row['Roster Notes'] and 'may already have changed' in row['Roster Notes']
    upload(client, [['9701', 'More Changes', 'Another Name', '12', 'Third Advisor', 'Other House', 'Third Clan']])
    assert json.loads(db_session.get(SessionRecord, record_id).student_profile) == profile


def test_conflicting_duplicate_upload_rows_are_noted_for_every_field(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    upload(client, [OLD[0], NEW[0]])
    notes = export(client, meal)[0]['Roster Notes']
    for field in ('Preferred', 'Last', 'Grade', 'Advisor', 'House', 'Clan'):
        assert f'duplicate roster rows disagree on {field}' in notes
    assert 'first row retained' in notes
    # A recording made during the conflict retains its warning after it is resolved.
    later = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    upload(client, [OLD[0]])
    assert 'duplicate roster rows disagree on House' in export(client, later)[0]['Roster Notes']


@pytest.mark.parametrize('supporting, expected', [(False, 'Unresolved'), (True, 'Current')])
def test_missing_id_namesakes_are_matched_using_supporting_fields_or_flagged(client, login, supporting, expected):
    login()
    upload(client, [OLD[0], ['9702', 'Original', 'Alex', '10', 'Other Advisor', 'Hall', 'Beta']])
    meal = create_session(client)
    owner = db_session.query(User).filter_by(username='greenguys').one()
    db_session.add(SessionRecord(school_id=DEFAULT_SCHOOL_ID, session_id=meal, category='clean',
                                 preferred_name='Alex', last_name='Original', grade='9' if supporting else '',
                                 house='Barn' if supporting else '', recorded_by=owner.id, dedupe_key='alex|original'))
    db_session.commit()
    row = export(client, meal)[0]
    assert row['Roster Status'] == expected
    assert 'Conflict:' in row['Roster Notes'] and '9701' in row['Roster Notes'] and '9702' in row['Roster Notes']
    assert row['Student ID'] == ''  # Never invent or replace a historical identity.


def test_no_identity_without_name_match_is_unresolved_not_incorrectly_old(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': 'Unknown Person'}).status_code == 200
    row = export(client, meal)[0]
    assert row['Roster Status'] == 'Unresolved' and 'cannot be verified' in row['Roster Notes']


def test_explicit_id_has_priority_over_key_and_supplied_names(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    response = client.post('/api/record/clean', json={
        'student_id': '9701', 'student_key': 'id:9702',
        'preferred_name': 'Jordan', 'last_name': 'Departed',
    })
    assert response.status_code == 200
    assert response.get_json()['student_id'] == '9701'
    row = export(client, meal)[0]
    assert row['Preferred'] == 'Alex' and row['Student ID'] == '9701'
    for field in ('Student ID', 'Preferred', 'Last'):
        assert f'recording supplied a different {field}' in row['Roster Notes']


def test_unknown_explicit_id_does_not_fall_back_to_another_students_name(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    response = client.post('/api/record/clean', json={
        'student_id': '9799', 'preferred_name': 'Alex', 'last_name': 'Original',
    })
    assert response.status_code == 200 and response.get_json()['student_id'] == '9799'
    row = export(client, meal)[0]
    assert row['Roster Status'] == 'Old' and '9701' in row['Roster Notes']
    assert db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='9799').one().is_active == 0


def test_case_changes_in_uploaded_id_keep_original_identity(client, login):
    login()
    upload(client, [['AbC9701'] + OLD[0][1:]])
    original = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='AbC9701').one()
    original_id = original.id
    upload(client, [['abc9701'] + NEW[0][1:]])
    students = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, is_active=1).all()
    assert len(students) == 1 and students[0].id == original_id
    assert students[0].student_identifier == 'AbC9701'
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'student_id': 'ABC9701'}).status_code == 200
    assert export(client, meal)[0]['Student ID'] == 'AbC9701'


def test_roster_comparison_never_matches_another_school(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    upload(client, [OLD[1]])
    school_id = uuid.uuid4().hex
    db_session.add(School(id=school_id, slug=school_id, name='Other school'))
    db_session.flush()
    db_session.add(Student(school_id=school_id, student_identifier='9701', preferred_name='Foreign',
                           last_name='Student', house='Foreign House'))
    db_session.commit()
    row = export(client, meal)[0]
    assert row['Roster Status'] == 'Old' and 'Foreign' not in str(row)


def test_changed_student_link_does_not_replace_recorded_id(client, login):
    login()
    upload(client, OLD)
    meal = create_session(client)
    assert client.post('/api/record/clean', json={'input_value': '9701'}).status_code == 200
    student = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='9701').one()
    damaged_id = 'changed-' + uuid.uuid4().hex
    student.student_identifier = damaged_id  # Simulate damaged/imported legacy data.
    db_session.commit()
    row = export(client, meal)[0]
    assert row['Student ID'] == '9701' and row['Roster Status'] == 'Old'
    assert f'saved student link now has a different Student ID: {damaged_id}' in row['Roster Notes']


def test_legacy_id_preserves_canonical_case_and_records_all_matching_id_conflicts(client, login):
    login()
    upload(client, [['AbC9701'] + OLD[0][1:]])
    meal = create_session(client)
    student = db_session.query(Student).filter_by(school_id=DEFAULT_SCHOOL_ID, student_identifier='AbC9701').one()
    owner = db_session.query(User).filter_by(username='greenguys').one()
    db_session.add(SessionRecord(school_id=DEFAULT_SCHOOL_ID, session_id=meal, student_id=student.id,
                                 category='clean', preferred_name='Alex', last_name='Original',
                                 recorded_by=owner.id, dedupe_key='id:abc9701'))
    db_session.commit()
    assert export(client, meal)[0]['Student ID'] == 'AbC9701'
    db_session.add(Student(school_id=DEFAULT_SCHOOL_ID, student_identifier='ABC9701', preferred_name='Duplicate',
                           last_name='Identity'))
    db_session.commit()
    row = export(client, meal)[0]
    assert row['Student ID'] == 'AbC9701' and row['Roster Status'] == 'Unresolved'
    assert 'multiple current students share Student ID' in row['Roster Notes']


def test_recording_an_ambiguous_name_does_not_assign_an_arbitrary_id(client, login):
    login()
    upload(client, [OLD[0], ['9702', 'Original', 'Alex', '10', 'Other Advisor', 'Hall', 'Beta']])
    meal = create_session(client)
    response = client.post('/api/record/clean', json={'input_value': 'Alex Original'})
    assert response.status_code == 200 and response.get_json()['student_id'] == ''
    row = export(client, meal)[0]
    assert row['Student ID'] == '' and row['Roster Status'] == 'Unresolved'
    assert 'recording had multiple full-name matches' in row['Roster Notes']
    upload(client, [OLD[0]])
    row = export(client, meal)[0]
    assert 'recording had multiple full-name matches' in row['Roster Notes']
    assert row['Student ID'] == ''


def test_alphanumeric_id_input_is_matched_before_name_parsing(client, login):
    login()
    upload(client, [['History-ABC-01'] + OLD[0][1:]])
    meal = create_session(client)
    response = client.post('/api/record/clean', json={'input_value': 'history-abc-01'})
    assert response.status_code == 200 and response.get_json()['student_id'] == 'History-ABC-01'
    assert response.get_json()['preferred_name'] == 'Alex'
    row = export(client, meal)[0]
    assert row['Student ID'] == 'History-ABC-01' and row['Roster Status'] == 'Current'
